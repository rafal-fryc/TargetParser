"""LLM-powered text cleanup: strip embedded line numbers from extracted text.

Line numbers embedded in source documents (legal filings, code listings, specs)
leak into extracted PDF text.  Formats vary wildly — too many edge cases for
regex.  This module delegates the cleanup to a small, fast LLM.
"""

from dataclasses import dataclass
from typing import Optional

try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

_SYSTEM_PROMPT = (
    "You are a text-cleaning assistant. Your sole task is to remove line numbers "
    "that were embedded in a source document (legal filings, code listings, "
    "specifications, etc.). Do NOT alter any other content — preserve all "
    "original wording, punctuation, spacing, and paragraph structure exactly. "
    "Return only the cleaned text with line numbers removed. If there are no "
    "line numbers to remove, return the text unchanged."
)


@dataclass
class CleanResult:
    """Result of LLM-based text cleanup.

    Attributes:
        text: The cleaned text (or original if unchanged / on error).
        original_text: The input text before cleaning.
        changed: Whether the LLM modified the text.
        model: The model used for cleanup.
        error: Error message if the cleanup failed (text falls back to original).
    """
    text: str
    original_text: str
    changed: bool
    model: str
    error: Optional[str] = None


def clean_text(
    text: str,
    *,
    model: str = "claude-haiku-4-5-20251001",
    api_key: Optional[str] = None,
    max_tokens: int = 4096,
) -> CleanResult:
    """Remove embedded line numbers from text using an LLM.

    Args:
        text: The text to clean.
        model: Anthropic model ID to use. Defaults to Haiku (fast & cheap).
        api_key: Optional API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
        max_tokens: Maximum tokens for the LLM response.

    Returns:
        CleanResult with cleaned text and metadata.

    Raises:
        NotImplementedError: If the ``anthropic`` package is not installed.
    """
    if not _HAS_ANTHROPIC:
        raise NotImplementedError(
            "LLM cleanup requires the 'anthropic' package. "
            "Install with: pip install targetparser[llm]"
        )

    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        cleaned = response.content[0].text
        return CleanResult(
            text=cleaned,
            original_text=text,
            changed=cleaned != text,
            model=model,
        )
    except Exception as exc:
        return CleanResult(
            text=text,
            original_text=text,
            changed=False,
            model=model,
            error=str(exc),
        )
