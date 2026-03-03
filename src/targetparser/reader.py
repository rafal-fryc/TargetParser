"""PDF text extraction with line-numbered output."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# Optional PDF library imports
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False


class OCRRequiredError(Exception):
    """Raised when a PDF is scanned/image-based and no text can be extracted."""


@dataclass
class ReadResult:
    """Result of reading a PDF.

    Attributes:
        text: Full extracted text with ``--- Page N ---`` markers.
        num_pages: Total number of pages in the PDF.
        path: Original file path.
    """
    text: str
    num_pages: int
    path: str


def read_pdf(path: str | Path) -> ReadResult:
    """Read and extract text from a PDF file.

    Tries pdfplumber first (better for complex layouts), falls back to pypdf.
    Each page is prefixed with a ``--- Page N ---`` marker line.

    Args:
        path: Path to the PDF file.

    Returns:
        ReadResult with extracted text and metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        NotImplementedError: If no PDF library is installed.
        OCRRequiredError: If the PDF is scanned/image-based.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    if not (_HAS_PDFPLUMBER or _HAS_PYPDF):
        raise NotImplementedError(
            "PDF parsing requires 'pdfplumber' or 'pypdf'. "
            "Install with: pip install targetparser[pdf]"
        )

    text_parts: list[str] = []
    num_pages = 0

    # Try pdfplumber first
    if _HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(path) as pdf:
                num_pages = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")

            if text_parts:
                log.info("PDF parsed with pdfplumber (%d pages)", num_pages)
                return ReadResult(
                    text="\n\n".join(text_parts),
                    num_pages=num_pages,
                    path=str(path),
                )
        except Exception as exc:
            log.warning("pdfplumber failed (%s), trying pypdf...", exc)

    # Fall back to pypdf
    if _HAS_PYPDF:
        try:
            reader = PdfReader(str(path))
            num_pages = len(reader.pages)
            for page_num, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {page_num} ---\n{page_text}")

            if text_parts:
                log.info("PDF parsed with pypdf (%d pages)", num_pages)
                return ReadResult(
                    text="\n\n".join(text_parts),
                    num_pages=num_pages,
                    path=str(path),
                )
        except Exception as exc:
            log.warning("pypdf failed (%s)", exc)

    raise OCRRequiredError(f"No text extracted (scanned PDF): {path.name}")
