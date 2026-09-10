"""
call_graph.py — Parses Java source into methods and builds a static call graph.

This is the ground-truth layer: for any method, it tells you (a) the full
source of the method, and (b) which other methods it actually calls, by
walking the real AST (not regex). That call graph is the "true dependency
set" D(q) used throughout scoring.py.
"""

import glob
import os
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

import javalang


@dataclass
class MethodChunk:
    qualified_name: str
    package: str
    class_name: str
    method_name: str
    signature: str          # e.g. "processPayment(String, BigDecimal)"
    source_text: str        # human-readable stub used for retrieval + as LLM context
    calls: Set[str] = field(default_factory=set)
    is_internal: bool = False


def _walk(node):
    """Recursively yield every javalang AST node under `node`."""
    yield node
    if hasattr(node, "children"):
        for child in node.children:
            if isinstance(child, (list, tuple)):
                for item in child:
                    if isinstance(item, javalang.ast.Node):
                        yield from _walk(item)
            elif isinstance(child, javalang.ast.Node):
                yield from _walk(child)


def parse_java_file(path: str) -> List[MethodChunk]:
    with open(path, "r") as f:
        src = f.read()
    tree = javalang.parse.parse(src)
    package = tree.package.name if tree.package else ""
    chunks = []

    for _, class_decl in tree.filter(javalang.tree.ClassDeclaration):
        class_name = class_decl.name
        for method in class_decl.methods:
            method_name = method.name
            qualified = f"{package}.{class_name}.{method_name}"

            calls = set()
            for node in _walk(method):
                if isinstance(node, javalang.tree.MethodInvocation):
                    calls.add(node.member)

            params = ", ".join(
                p.type.name if hasattr(p.type, "name") else str(p.type)
                for p in method.parameters
            )
            signature = f"{method_name}({params})"
            calls_str = ", ".join(sorted(calls)) if calls else "none"
            source_text = f"{class_name}.{signature} — calls: {calls_str}"

            chunks.append(MethodChunk(
                qualified_name=qualified,
                package=package,
                class_name=class_name,
                method_name=method_name,
                signature=signature,
                source_text=source_text,
                calls=calls,
                is_internal=".internal." in package,
            ))
    return chunks


def build_codebase(src_dir: str) -> Dict[str, MethodChunk]:
    """Returns {simple_method_name: MethodChunk}. javalang only resolves
    simple invoked names (no type resolution), so the call graph and the
    codebase index both key on simple method name. Fine for a codebase
    with no name collisions, which this synthetic benchmark guarantees."""
    by_name: Dict[str, MethodChunk] = {}
    for path in sorted(glob.glob(os.path.join(src_dir, "*.java"))):
        for chunk in parse_java_file(path):
            by_name[chunk.method_name] = chunk
    return by_name


def dependency_closure(root_method: str, codebase: Dict[str, MethodChunk], depth: int = 2) -> Set[str]:
    """BFS over the call graph up to `depth` hops — this is D(q), the true
    dependency set a correct reimplementation of root_method must respect."""
    frontier = {root_method}
    seen: Set[str] = set()
    for _ in range(depth):
        next_frontier = set()
        for m in frontier:
            chunk = codebase.get(m)
            if not chunk:
                continue
            for callee in chunk.calls:
                if callee in codebase and callee not in seen:
                    next_frontier.add(callee)
        seen |= next_frontier
        frontier = next_frontier
    return seen
