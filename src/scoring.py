"""
scoring.py — Implements Equations 1-3 from the RCL paper.

  S_cov(q)  = structural coverage (Eq. 1)
  S_nov(q)  = novelty of the uncovered gap (Eq. 2)
  C(q)      = combined confidence (Eq. 3)

novelty() here is the pilot-stage proxy described in the paper's Section
4.2 note: a simple package-based heuristic (is this symbol in an
`*.internal.*` package?), standing in for the fuller corpus-frequency +
naming-pattern + LLM-self-assessment signal described in the paper.
Upgrading this function is the main way to increase RCL's fidelity to the
full design without touching anything else in the pipeline.
"""

from typing import Dict, Set

from call_graph import MethodChunk


def novelty(symbol: str, codebase: Dict[str, MethodChunk]) -> float:
    chunk = codebase.get(symbol)
    if chunk is None:
        return 1.0
    return 1.0 if chunk.is_internal else 0.1


def s_cov(dep_set: Set[str], retrieved: Set[str]) -> float:
    if not dep_set:
        return 1.0
    return len(dep_set & retrieved) / len(dep_set)


def s_nov(dep_set: Set[str], retrieved: Set[str], codebase: Dict[str, MethodChunk]) -> float:
    uncovered = dep_set - retrieved
    if not uncovered:
        return 0.0
    return sum(novelty(s, codebase) for s in uncovered) / len(uncovered)


def confidence(cov: float, nov: float) -> float:
    return cov * (1 - nov)
