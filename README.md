# RCL

This runs the actual end-to-end experiment: retrieve context from a small
synthetic "enterprise" Java codebase, then **really call Claude** to
generate each method, then check whether the generated code correctly
used the internal methods it needed — or hallucinated ones that don't
exist. Three strategies are compared per query (see below).

## What this measures, honestly

This is a **small-scale** (16 methods, 9 held-out queries in the
included synthetic codebase). It's real — every number comes from an
actual Claude call and actual parsing of what was generated — but it's
small. Treat results as directional, not conclusive, until you scale up
the codebase (see "Scaling up" below).

## 1. Setup

```bash
cd rcl_project
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your real Anthropic API key
export $(cat .env | xargs)
```

## 2. Run

```bash
cd src
python3 run_experiment.py
```

This runs all 9 queries × 3 strategies = 27 Claude calls by default.
**To limit API spend while testing**, run a smaller batch first:

```bash
python3 run_experiment.py --max-queries 3
```

Other flags:
```bash
python3 run_experiment.py --k-small 2 --k-large 5 --tau 0.6
```
- `--k-small`: retrieval size for the similarity-only and RCL-initial pass
- `--k-large`: retrieval size for the fixed-k-expanded baseline
- `--tau`: confidence threshold below which RCL triggers a follow-up retrieval

## 3. What you get

- Console output: per-query progress and a final summary (mean coverage,
  mean confidence, mean recall of required calls in the generated code,
  hallucination counts, RCL follow-up trigger rate).
- `results/results.json`: full detail per query per strategy, including
  the **actual generated code** from Claude for each strategy, so you can
  manually inspect exactly what happened on any query.

## 4. How to read the results honestly

- **`recall`**: of the internal methods a correct implementation needed,
  what fraction did Claude's generated code actually call? Higher is better.
- **`hallucination_count`**: how many methods Claude called that don't
  exist anywhere in the real codebase — i.e., it invented a plausible-
  sounding internal API that isn't real. This is the concrete version of
  the paper's "confident but wrong" failure mode. Zero is the goal.
- Compare these across the three strategies. The hypothesis RCL is meant
  to test: when confidence is low and RCL does a targeted follow-up
  retrieval, does recall go up and/or hallucination go down, compared to
  similarity-only retrieval at the same k? Whether that actually holds is
  an empirical question — this project answers it, it doesn't assume it.

## 5. Scaling up (recommended next step)

The included `javasrc/` folder has 7 tiny synthetic files — enough to
prove the pipeline works, not enough for a statistically meaningful
result. To get a real result:

1. Add real open-source Java files to `javasrc/` (50-100+ files ideally).
2. Pick a handful of common utility methods and move them into a package
   containing `.internal.` (e.g. `com.yourorg.internal.*`) to mark them
   as the synthetic "private API" condition — mirrors what's already done
   for the included sample files.
3. Re-run. More files → more queries → a much more meaningful `results.json`.

## 6. Known limitations of this pilot (be upfront about these)

- `novelty()` in `scoring.py` is a simple package-name heuristic, not the
  fuller corpus-frequency + naming-pattern signal described in the paper.
- Call-graph resolution is by simple method name (no type resolution),
  which is fine for this synthetic codebase but would need a real Java
  type-resolving parser (e.g. via `javac`'s own AST, or a tool like
  JavaParser with symbol solving) for a real, larger codebase with
  overloaded/same-named methods across classes.
- Generated-code correctness is checked by regex-extracted method calls,
  not compilation. It's a reasonable proxy for this experiment's question
  (did it call the right things) but is not the same as "the code compiles
  and passes tests" — a further step if you want full correctness numbers.
- Costs real API credits — budget accordingly before scaling up the query count.

## File structure

```
rcl_project/
├── requirements.txt
├── .env.example
├── README.md
├── javasrc/              # the synthetic codebase (add more files to scale up)
├── src/
│   ├── call_graph.py     # parses Java, builds the true dependency graph
│   ├── retriever.py      # TF-IDF retrieval
│   ├── scoring.py        # Equations 1-3 (coverage, novelty, confidence)
│   ├── llm_client.py     # the actual Claude API call
│   ├── generated_code_check.py  # checks what the generated code calls
│   └── run_experiment.py # orchestrates everything, entry point
└── results/
    └── results.json      # written after each run
```
