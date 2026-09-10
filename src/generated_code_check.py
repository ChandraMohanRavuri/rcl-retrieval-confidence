"""
generated_code_check.py — Extracts method invocations from Claude's raw
generated text so we can compare them against the true dependency set.

Generated snippets are often not valid standalone Java (missing class
wrapper, imports, etc.), so javalang's parser is too strict here. We use
a regex-based extraction instead: good enough to answer "did the generated
code call the methods it needed, and did it invent any methods that don't
exist anywhere in the real codebase" (hallucination check).
"""

import re
from typing import Dict, Set

from call_graph import MethodChunk

# Matches `something.methodName(` or bare `methodName(` — a reasonable
# proxy for "this identifier is being called as a method" in a Java snippet.
CALL_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")

# Java keywords / control structures that match the pattern but aren't
# real method calls — filtered out so they don't pollute the call set.
JAVA_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "synchronized", "return",
    "new", "this", "super",
}


def extract_called_methods(generated_text: str) -> Set[str]:
    calls = set(CALL_PATTERN.findall(generated_text))
    return calls - JAVA_KEYWORDS


def evaluate_generation(
    generated_text: str,
    dep_set: Set[str],
    codebase: Dict[str, MethodChunk],
) -> dict:
    """Compares what the generated code actually calls against the true
    dependency set. Returns:
      - correct_calls: dependencies that were correctly invoked
      - missed_calls: dependencies that were needed but never called
      - hallucinated_calls: called names that don't exist ANYWHERE in the
        real codebase (i.e. Claude invented an API that isn't real) —
        this is the concrete, checkable "confident but wrong" failure mode
        the paper's introduction describes.
    """
    called = extract_called_methods(generated_text)
    known_methods = set(codebase.keys())

    correct_calls = called & dep_set
    missed_calls = dep_set - called
    hallucinated_calls = called - known_methods - JAVA_KEYWORDS

    return {
        "called": sorted(called),
        "correct_calls": sorted(correct_calls),
        "missed_calls": sorted(missed_calls),
        "hallucinated_calls": sorted(hallucinated_calls),
        "recall": len(correct_calls) / len(dep_set) if dep_set else 1.0,
        "hallucination_count": len(hallucinated_calls),
    }
