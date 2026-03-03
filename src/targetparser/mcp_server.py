"""MCP tool server for TargetParser.

Exposes three tools so any LLM/agent can call the pipeline:
- read_pdf: Read a PDF and cache text server-side.
- extract_lines: Extract text from cached document by line range.
- verify_text: Verify quoted text against a cached document.

Documents are cached by absolute path so the full text only transits
the wire once.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .reader import read_pdf as _read_pdf
from .extractor import extract_lines as _extract_lines
from .verifier import Verifier

server = FastMCP("targetparser")

# In-memory document cache: absolute path -> (text, num_pages)
_cache: dict[str, tuple[str, int]] = {}


def _get_or_read(path: str) -> tuple[str, int]:
    """Return cached document text, reading the PDF if needed."""
    key = str(Path(path).resolve())
    if key not in _cache:
        result = _read_pdf(key)
        _cache[key] = (result.text, result.num_pages)
    return _cache[key]


@server.tool()
def read_pdf(path: str) -> str:
    """Read a PDF and cache its text. Returns metadata and the line-numbered text.

    Args:
        path: Absolute or relative path to a PDF file.
    """
    text, num_pages = _get_or_read(path)
    total_lines = len(text.split("\n"))
    return (
        f"Document loaded: {num_pages} pages, {total_lines} lines.\n"
        f"Path: {path}\n\n"
        f"{text}"
    )


@server.tool()
def extract_lines(path: str, start_line: int, end_line: int) -> str:
    """Extract text from a previously-read document by line range.

    Args:
        path: Path used in a prior read_pdf call.
        start_line: First line to extract (1-based, inclusive).
        end_line: Last line to extract (1-based, inclusive).
    """
    text, _ = _get_or_read(path)
    result = _extract_lines(text, start_line, end_line)
    if not result.text:
        return f"No content found in lines {start_line}-{end_line}."
    return (
        f"Lines {result.start_line}-{result.end_line} ({result.num_lines} content lines):\n\n"
        f"{result.text}"
    )


@server.tool()
def verify_text(path: str, quoted_text: str) -> str:
    """Verify whether quoted text appears in a previously-read document.

    Args:
        path: Path used in a prior read_pdf call.
        quoted_text: The text to search for in the document.
    """
    text, _ = _get_or_read(path)
    verifier = Verifier(text)
    result = verifier.verify(quoted_text)

    parts = [
        f"Valid: {result.valid}",
        f"Confidence: {result.confidence:.0%}",
        f"Match type: {result.match_type}",
    ]
    if result.line_numbers:
        parts.append(f"Lines: {result.line_numbers[0]}-{result.line_numbers[1]}")
    if result.found_text:
        snippet = result.found_text[:300]
        parts.append(f"Found text: {snippet}")
    if result.error:
        parts.append(f"Error: {result.error}")

    return "\n".join(parts)


@server.tool()
def clean_text(path: str, start_line: int, end_line: int) -> str:
    """Extract text from a document by line range and clean embedded line numbers using an LLM.

    This combines extraction with LLM-powered cleanup: extracts the specified
    lines, then uses a small language model to strip any embedded line numbers
    from the text (common in legal filings, code listings, and specifications).

    Requires the ``anthropic`` package (install with ``pip install targetparser[llm]``).

    Args:
        path: Path used in a prior read_pdf call.
        start_line: First line to extract (1-based, inclusive).
        end_line: Last line to extract (1-based, inclusive).
    """
    text, _ = _get_or_read(path)
    result = _extract_lines(text, start_line, end_line)
    if not result.text:
        return f"No content found in lines {start_line}-{end_line}."

    try:
        from .cleaner import clean_text as _clean_text
        clean_result = _clean_text(result.text)
    except NotImplementedError:
        return (
            f"Lines {result.start_line}-{result.end_line} ({result.num_lines} content lines):\n\n"
            f"{result.text}\n\n"
            f"Note: LLM cleanup unavailable. Install with: pip install targetparser[llm]"
        )

    status = "cleaned" if clean_result.changed else "unchanged"
    header = f"Lines {result.start_line}-{result.end_line} ({result.num_lines} content lines, {status}):"
    parts = [header, "", clean_result.text]
    if clean_result.error:
        parts.append(f"\nWarning: cleanup error ({clean_result.error}), showing original text.")
    return "\n".join(parts)


def main():
    """Entry point for ``targetparser-mcp`` console script."""
    server.run()


if __name__ == "__main__":
    main()
