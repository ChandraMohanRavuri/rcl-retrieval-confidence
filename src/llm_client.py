"""
llm_client.py — Wraps the Claude API call that actually generates code.

This is the piece that makes the experiment end-to-end rather than
retrieval-only: given a method to reimplement and some retrieved context,
ask Claude to write it, and hand back the raw generated text for parsing
and scoring in pipeline.py.

Requires ANTHROPIC_API_KEY to be set in the environment (see .env.example
and README.md).
"""

import os

import anthropic

MODEL = "claude-sonnet-4-6"  # change if you want to test a different model


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env, add your "
            "key, then `export $(cat .env | xargs)` before running, or set "
            "it directly in your shell."
        )
    return anthropic.Anthropic(api_key=api_key)


def generate_method(
    client: anthropic.Anthropic,
    class_name: str,
    signature: str,
    retrieved_context: list[str],
) -> str:
    """Asks Claude to implement `signature` using only the given retrieved
    context snippets, mirroring what a RAG-based coding assistant would do.
    Returns the raw text of Claude's response (expected to be a Java method
    body / snippet, not necessarily compilable in isolation)."""

    context_block = "\n".join(f"- {c}" for c in retrieved_context) if retrieved_context else "(no context retrieved)"

    prompt = f"""You are implementing a single Java method inside the class `{class_name}`.

Method to implement: {signature}

The only information you have about the rest of the codebase is this
retrieved context (method signatures and what they call, not full source):
{context_block}

Write the method body. If it needs to call another internal method that
you believe exists based on the codebase's naming conventions but which
is NOT listed above, you may call it anyway using your best guess at its
name — but do not invent unrelated third-party libraries. Output ONLY the
Java method code, no explanation, no markdown fences."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
