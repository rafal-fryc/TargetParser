"""Core anti-hallucination mechanism: deterministic line extraction.

An LLM returns line numbers; this module extracts the exact text from
those lines so no hallucinated quotes are possible.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractionResult:
    """Result of a line-range extraction.

    Attributes:
        text: The extracted text (lines joined with spaces).
        start_line: Actual start line used (1-based).
        end_line: Actual end line used (1-based, inclusive).
        num_lines: Number of content lines extracted (excluding page markers).
    """
    text: str
    start_line: int
    end_line: int
    num_lines: int


_PAGE_MARKER = re.compile(r"^---\s*Page\s+\d+\s*---$")


def extract_lines(
    document_text: str,
    start_line: int,
    end_line: int,
    *,
    join: str = " ",
    keep_page_markers: bool = False,
) -> ExtractionResult:
    """Extract text from a line range in a document.

    Args:
        document_text: Full document text (as returned by ``read_pdf``).
        start_line: First line to extract (1-based, inclusive).
        end_line: Last line to extract (1-based, inclusive).
        join: String used to join extracted lines. Default is a single space.
        keep_page_markers: If False (default), ``--- Page N ---`` lines are
            stripped from the output.

    Returns:
        ExtractionResult with the extracted text and metadata.
    """
    lines = document_text.split("\n")
    total = len(lines)

    # Clamp to valid range (convert 1-based to 0-based)
    start_idx = max(0, start_line - 1)
    end_idx = min(total, end_line)

    if start_idx >= end_idx:
        return ExtractionResult(text="", start_line=start_line, end_line=end_line, num_lines=0)

    extracted: list[str] = []
    for line in lines[start_idx:end_idx]:
        stripped = line.strip()
        if not keep_page_markers and _PAGE_MARKER.match(stripped):
            continue
        if stripped:
            extracted.append(stripped)

    return ExtractionResult(
        text=join.join(extracted),
        start_line=start_idx + 1,
        end_line=end_idx,
        num_lines=len(extracted),
    )


def resolve_items(
    document_text: str,
    items: list[dict],
    start_key: str = "quote_start_line",
    end_key: str = "quote_end_line",
    output_key: str = "quoted_text",
) -> list[dict]:
    """Batch-resolve line numbers in LLM JSON output.

    For each dict in *items* that contains *start_key* and *end_key*,
    deterministically extract the text from those lines and store it
    under *output_key*.

    Args:
        document_text: Full document text.
        items: List of dicts (typically parsed from LLM JSON output).
        start_key: Key holding the start line number.
        end_key: Key holding the end line number.
        output_key: Key to write the extracted text into.

    Returns:
        The same *items* list, mutated with *output_key* filled in.
    """
    for item in items:
        start = item.get(start_key)
        end = item.get(end_key)

        if start is None or end is None:
            continue

        result = extract_lines(document_text, int(start), int(end))
        if result.text:
            item[output_key] = result.text

    return items
