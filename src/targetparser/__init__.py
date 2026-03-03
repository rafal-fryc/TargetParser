"""TargetParser — Generalized PDF line extraction and verification.

An anti-hallucination toolkit: an LLM returns line numbers, Python
deterministically extracts the exact text, and optionally verifies it.
"""

from .reader import read_pdf, ReadResult, OCRRequiredError
from .extractor import extract_lines, resolve_items, ExtractionResult
from .verifier import Verifier, VerificationResult, verify_text
from .cleaner import clean_text, CleanResult

__all__ = [
    "read_pdf",
    "ReadResult",
    "OCRRequiredError",
    "extract_lines",
    "resolve_items",
    "ExtractionResult",
    "Verifier",
    "VerificationResult",
    "verify_text",
    "clean_text",
    "CleanResult",
]
