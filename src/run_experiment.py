"""
run_experiment.py — End-to-end RCL experiment, with real Claude API calls.

For each held-out query (a method with real dependencies), this runs THREE
strategies, and for each one, actually asks Claude to generate the method
body using only what was retrieved — then checks whether the generated
code correctly used the required internal methods, or hallucinated ones
that don't exist. That's the real, checkable "does insufficient retrieval
actually cause bad generations" test.

  A. similarity-only   — top-k TF-IDF, fixed small k, no gating
  B. fixed-k-expanded  — top-k TF-IDF, larger fixed k, no gating
  C. RCL                — starts like A; if confidence < tau, does ONE
                          targeted follow-up retrieval on the uncovered
                          dependency names before generating

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 run_experiment.py
    python3 run_experiment.py --k-small 2 --k-large 5 --tau 0.6 --max-queries 5

Costs real API credits — one Claude call per query per strategy (3 calls
per query). Use --max-queries to limit spend while testing.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from call_graph import build_codebase, dependency_closure
from retriever import Retriever
from scoring import s_cov, s_nov, confidence
from llm_client import get_client, generate_method
from generated_code_check import evaluate_generation


def run(src_dir: str, k_small: int, k_large: int, tau: float, max_queries: int | None):
    codebase = build_codebase(src_dir)
    retriever = Retriever(codebase)
    client = get_client()

    queries = [n for n in codebase if dependency_closure(n, codebase)]
    if max_queries:
        queries = queries[:max_queries]

    print(f"Codebase: {len(codebase)} methods. Running {len(queries)} queries x 3 strategies "
          f"= {len(queries) * 3} Claude calls.\n")

    rows = []
    for i, q in enumerate(queries, 1):
        chunk = codebase[q]
        dep_set = dependency_closure(q, codebase)
        query_text = chunk.source_text
        print(f"[{i}/{len(queries)}] {chunk.class_name}.{chunk.signature}  (needs: {sorted(dep_set)})")

        strategies = {}

        # --- A: similarity-only ---
        retrieved_a = set(retriever.top_k(query_text, k_small, exclude=q))
        cov_a, nov_a = s_cov(dep_set, retrieved_a), s_nov(dep_set, retrieved_a, codebase)
        conf_a = confidence(cov_a, nov_a)
        context_a = [codebase[r].source_text for r in retrieved_a]
        gen_a = generate_method(client, chunk.class_name, chunk.signature, context_a)
        eval_a = evaluate_generation(gen_a, dep_set, codebase)
        strategies["A_similarity_only"] = {
            "retrieved": sorted(retrieved_a), "cov": round(cov_a, 3), "nov": round(nov_a, 3),
            "conf": round(conf_a, 3), "generated": gen_a, **eval_a,
        }

        # --- B: fixed-k-expanded ---
        retrieved_b = set(retriever.top_k(query_text, k_large, exclude=q))
        cov_b, nov_b = s_cov(dep_set, retrieved_b), s_nov(dep_set, retrieved_b, codebase)
        conf_b = confidence(cov_b, nov_b)
        context_b = [codebase[r].source_text for r in retrieved_b]
        gen_b = generate_method(client, chunk.class_name, chunk.signature, context_b)
        eval_b = evaluate_generation(gen_b, dep_set, codebase)
        strategies["B_fixed_k_expanded"] = {
            "retrieved": sorted(retrieved_b), "cov": round(cov_b, 3), "nov": round(nov_b, 3),
            "conf": round(conf_b, 3), "generated": gen_b, **eval_b,
        }

        # --- C: RCL (gated, with targeted follow-up if low confidence) ---
        retrieved_c = set(retrieved_a)
        cov_c, nov_c, conf_c = cov_a, nov_a, conf_a
        triggered = conf_c < tau
        if triggered:
            uncovered = dep_set - retrieved_c
            followup_query = " ".join(uncovered)
            followup_hits = set(retriever.top_k(followup_query, k_small, exclude=q))
            retrieved_c |= followup_hits
            cov_c = s_cov(dep_set, retrieved_c)
            nov_c = s_nov(dep_set, retrieved_c, codebase)
            conf_c = confidence(cov_c, nov_c)
            context_c = [codebase[r].source_text for r in retrieved_c]
            gen_c = generate_method(client, chunk.class_name, chunk.signature, context_c)
            eval_c = evaluate_generation(gen_c, dep_set, codebase)
        else:
            # RCL retrieved identical context to strategy A and did not
            # trigger a follow-up — reuse A's generation rather than
            # calling Claude again with the same input. Two separate calls
            # with identical prompts only differ by sampling noise, which
            # would falsely look like a "difference" between A and RCL on
            # queries where RCL's mechanism did nothing. Reusing A's result
            # here keeps the comparison honest: RCL vs A only differs where
            # RCL's gate actually changed what was retrieved.
            gen_c, eval_c = gen_a, eval_a
        strategies["C_RCL"] = {
            "retrieved": sorted(retrieved_c), "cov": round(cov_c, 3), "nov": round(nov_c, 3),
            "conf": round(conf_c, 3), "triggered_followup": triggered, "generated": gen_c, **eval_c,
        }

        rows.append({"query": q, "class": chunk.class_name, "dep_set": sorted(dep_set), "strategies": strategies})

        # brief pacing to be polite to the API
        time.sleep(0.3)

    return rows


def summarize(rows):
    def mean(system, key):
        vals = [r["strategies"][system][key] for r in rows]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    summary = {}
    for system in ["A_similarity_only", "B_fixed_k_expanded", "C_RCL"]:
        summary[system] = {
            "mean_coverage": mean(system, "cov"),
            "mean_confidence": mean(system, "conf"),
            "mean_recall_in_generated_code": mean(system, "recall"),
            "total_hallucinated_calls": sum(r["strategies"][system]["hallucination_count"] for r in rows),
            "queries_with_hallucination": sum(1 for r in rows if r["strategies"][system]["hallucination_count"] > 0),
        }
    summary["RCL_followup_trigger_rate"] = round(
        sum(1 for r in rows if r["strategies"]["C_RCL"]["triggered_followup"]) / len(rows), 3
    ) if rows else 0.0

    # Fair, noise-free comparison: only queries where RCL's gate actually
    # did something different from strategy A. On non-triggered queries,
    # RCL == A by construction (see run_experiment's reuse logic), so
    # including them would dilute a real effect with zero-difference rows.
    triggered_rows = [r for r in rows if r["strategies"]["C_RCL"]["triggered_followup"]]
    if triggered_rows:
        def mean_triggered(system, key):
            vals = [r["strategies"][system][key] for r in triggered_rows]
            return round(sum(vals) / len(vals), 3) if vals else 0.0

        summary["triggered_only_comparison"] = {
            "note": f"{len(triggered_rows)} of {len(rows)} queries triggered RCL's follow-up retrieval. "
                    "This is the fair comparison: differences elsewhere are LLM sampling noise, not RCL's effect.",
            "A_similarity_only": {
                "mean_recall": mean_triggered("A_similarity_only", "recall"),
                "total_hallucinations": sum(r["strategies"]["A_similarity_only"]["hallucination_count"] for r in triggered_rows),
            },
            "C_RCL": {
                "mean_recall": mean_triggered("C_RCL", "recall"),
                "total_hallucinations": sum(r["strategies"]["C_RCL"]["hallucination_count"] for r in triggered_rows),
            },
        }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src-dir", default=os.path.join(os.path.dirname(__file__), "..", "javasrc"))
    parser.add_argument("--k-small", type=int, default=2)
    parser.add_argument("--k-large", type=int, default=5)
    parser.add_argument("--tau", type=float, default=0.6)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "results", "results.json"))
    args = parser.parse_args()

    rows = run(args.src_dir, args.k_small, args.k_large, args.tau, args.max_queries)
    summary = summarize(rows)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(json.dumps(summary, indent=2))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"config": vars(args), "per_query": rows, "summary": summary}, f, indent=2)
    print(f"\nFull results (including generated code) written to {args.out}")
