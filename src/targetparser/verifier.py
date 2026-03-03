"""6-tier text verification engine.

Checks whether a quoted string actually appears in a source document,
using progressively looser matching strategies:

1. Exact (standard normalization)
2. Exact (aggressive normalization — no punctuation)
3. Substring containment
4. Multi-line fuzzy (SequenceMatcher + sliding window)
5. N-gram overlap
6. Keyword anchor
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from ._normalize import normalize, detect_doubled_chars, fix_doubled_chars


@dataclass
class VerificationResult:
    """Result of a text verification.

    Attributes:
        valid: Whether the text was found in the document.
        found_text: The matching text found (if any).
        confidence: Confidence score (0.0 to 1.0).
        error: Error message if verification failed.
        line_numbers: Line numbers where the text was found (1-based).
        match_type: Strategy that matched ("exact", "fuzzy_multiline", etc.).
    """
    valid: bool
    found_text: Optional[str] = None
    confidence: float = 0.0
    error: Optional[str] = None
    line_numbers: Optional[tuple[int, int]] = None
    match_type: str = "none"

    def to_dict(self) -> dict:
        """Convert to a plain dictionary."""
        return {
            "valid": self.valid,
            "found_text": self.found_text,
            "confidence": self.confidence,
            "error": self.error,
            "line_numbers": list(self.line_numbers) if self.line_numbers else None,
            "match_type": self.match_type,
        }


class Verifier:
    """Verifies quoted text against a source document.

    Pre-computes normalized forms and sliding-window blocks on init so
    that many quotes can be verified against the same document cheaply.
    """

    def __init__(self, document_text: str):
        if detect_doubled_chars(document_text):
            document_text = fix_doubled_chars(document_text)

        self.document_text = document_text
        self.lines = document_text.split("\n")

        self.normalized_text = normalize(document_text, level="standard")
        self.normalized_lines = [normalize(line, level="standard") for line in self.lines]

        self.aggressive_text = normalize(document_text, level="aggressive")

        self.joined_paragraphs = self._create_joined_blocks()

    # ── Block construction ────────────────────────────────────────────

    def _create_joined_blocks(self) -> list[tuple[str, int, int]]:
        blocks: list[tuple[str, int, int]] = []

        for window_size in [2, 3, 4, 5, 6, 7, 8]:
            for i in range(len(self.normalized_lines) - window_size + 1):
                window_lines = self.normalized_lines[i:i + window_size]
                window_text = " ".join(ln.strip() for ln in window_lines if ln.strip())
                if window_text and len(window_text) > 20:
                    blocks.append((window_text, i + 1, i + window_size))

        current_block: list[str] = []
        start_line = 0

        for i, line in enumerate(self.normalized_lines):
            if not line.strip():
                if current_block:
                    joined = " ".join(current_block)
                    if len(joined) > 20:
                        blocks.append((joined, start_line + 1, i))
                    current_block = []
                start_line = i + 1
            else:
                if not current_block:
                    start_line = i
                current_block.append(line.strip())

        if current_block:
            joined = " ".join(current_block)
            if len(joined) > 20:
                blocks.append((joined, start_line + 1, len(self.normalized_lines)))

        return blocks

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _similarity(text1: str, text2: str) -> float:
        return SequenceMatcher(None, text1, text2).ratio()

    def _position_to_lines(self, start_pos: int, length: int) -> tuple[int, int]:
        current_pos = 0
        start_line = 1
        end_line = 1

        for i, line in enumerate(self.normalized_lines):
            line_len = len(line) + 1  # +1 for the space that replaced newline
            if current_pos <= start_pos < current_pos + line_len:
                start_line = i + 1
            if current_pos <= start_pos + length <= current_pos + line_len:
                end_line = i + 1
                break
            current_pos += line_len

        return (start_line, max(end_line, start_line))

    def _find_line_numbers(self, normalized_text: str) -> tuple[int, int]:
        # Single-line match
        for i, line in enumerate(self.normalized_lines):
            if normalized_text in line:
                return (i + 1, i + 1)

        # Position-based lookup (TechRegParser improvement)
        pos = self.normalized_text.find(normalized_text)
        if pos != -1:
            return self._position_to_lines(pos, len(normalized_text))

        # Joined-block fallback
        for block_text, start_line, end_line in self.joined_paragraphs:
            if normalized_text in block_text:
                return (start_line, end_line)

        return (0, 0)

    def _find_line_numbers_aggressive(self, aggressive_text: str) -> tuple[int, int]:
        for i, line in enumerate(self.lines):
            line_agg = normalize(line, level="aggressive")
            if aggressive_text in line_agg:
                return (i + 1, i + 1)

        pos = self.aggressive_text.find(aggressive_text)
        if pos != -1:
            return self._position_to_lines(pos, len(aggressive_text))

        return (0, 0)

    # ── Matching strategies ───────────────────────────────────────────

    def _try_exact_match(self, quoted_text: str) -> Optional[tuple[str, int, int, str, float]]:
        nq = normalize(quoted_text, level="standard")
        if nq in self.normalized_text:
            sl, el = self._find_line_numbers(nq)
            return (quoted_text, sl, el, "exact", 1.0)
        return None

    def _try_normalized_exact_match(self, quoted_text: str) -> Optional[tuple[str, int, int, str, float]]:
        aq = normalize(quoted_text, level="aggressive")
        if len(aq) < 15:
            return None
        if aq in self.aggressive_text:
            sl, el = self._find_line_numbers_aggressive(aq)
            return (quoted_text, sl, el, "exact_normalized", 0.95)
        return None

    def _try_substring_match(self, quoted_text: str) -> Optional[tuple[str, int, int, str, float]]:
        nq = normalize(quoted_text, level="standard")

        for block_text, sl, el in self.joined_paragraphs:
            if nq in block_text:
                return (quoted_text, sl, el, "substring", 0.98)

        if len(nq) > 50:
            for block_text, sl, el in self.joined_paragraphs:
                if len(block_text) > 30 and block_text in nq:
                    return (block_text, sl, el, "contains", 0.85)

        return None

    def _try_multiline_fuzzy_match(self, quoted_text: str) -> Optional[tuple[str, int, int, str, float]]:
        nq = normalize(quoted_text, level="standard")
        qlen = len(nq)

        if qlen < 20:
            return None

        best_match: Optional[str] = None
        best_score = 0.0
        best_lines = (0, 0)

        for block_text, sl, el in self.joined_paragraphs:
            blen = len(block_text)
            if blen < qlen * 0.4 or blen > qlen * 2.5:
                continue
            score = self._similarity(nq, block_text)
            if score > best_score:
                best_score = score
                best_match = block_text
                best_lines = (sl, el)

        window_result = self._sliding_window_fuzzy(nq)
        if window_result and window_result[1] > best_score:
            best_score = window_result[1]
            best_match = window_result[0]
            best_lines = window_result[2]

        if best_score >= 0.70 and best_match:
            return (best_match, best_lines[0], best_lines[1], "fuzzy_multiline", best_score)

        return None

    def _try_ngram_match(self, quoted_text: str) -> Optional[tuple[str, int, int, str, float]]:
        nq = normalize(quoted_text, level="aggressive")
        words = nq.split()

        if len(words) < 5:
            return None

        quote_ngrams = {" ".join(words[i:i + 4]) for i in range(len(words) - 3)}
        if not quote_ngrams:
            return None

        best_overlap = 0.0
        best_block: Optional[str] = None
        best_lines = (0, 0)

        for block_text, sl, el in self.joined_paragraphs:
            bn = normalize(block_text, level="aggressive")
            bw = bn.split()
            if len(bw) < 5:
                continue

            block_ngrams = {" ".join(bw[i:i + 4]) for i in range(len(bw) - 3)}
            if not block_ngrams:
                continue

            intersection = len(quote_ngrams & block_ngrams)
            min_size = min(len(quote_ngrams), len(block_ngrams))

            if min_size > 0:
                overlap = intersection / min_size
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_block = block_text
                    best_lines = (sl, el)

        if best_overlap >= 0.40 and best_block:
            confidence = 0.55 + (best_overlap * 0.40)
            return (best_block, best_lines[0], best_lines[1], "ngram", min(confidence, 0.85))

        return None

    def _try_keyword_anchor_match(self, quoted_text: str) -> Optional[tuple[str, int, int, str, float]]:
        nq = normalize(quoted_text, level="standard")
        words = nq.split()

        anchor_words = [w for w in words if len(w) >= 7 and w.isalpha()]
        if len(anchor_words) < 2:
            return None

        best_block: Optional[str] = None
        best_score = 0.0
        best_lines = (0, 0)

        for block_text, sl, el in self.joined_paragraphs:
            anchor_hits = sum(1 for a in anchor_words if a in block_text)
            hit_ratio = anchor_hits / len(anchor_words)

            if hit_ratio >= 0.5:
                similarity = self._similarity(nq, block_text)
                combined = (hit_ratio * 0.4) + (similarity * 0.6)

                if combined > best_score:
                    best_score = combined
                    best_block = block_text
                    best_lines = (sl, el)

        if best_score >= 0.50 and best_block:
            return (best_block, best_lines[0], best_lines[1], "anchor", min(best_score, 0.70))

        return None

    def _sliding_window_fuzzy(self, normalized_quote: str) -> Optional[tuple[str, float, tuple[int, int]]]:
        qlen = len(normalized_quote)
        if qlen < 30:
            return None

        best_match: Optional[str] = None
        best_score = 0.0
        best_position = 0

        for window_mult in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
            window_size = int(qlen * window_mult)
            if window_size < 25 or window_size > len(self.normalized_text):
                continue

            step = max(10, window_size // 10)
            for i in range(0, len(self.normalized_text) - window_size, step):
                window = self.normalized_text[i:i + window_size]
                score = self._similarity(normalized_quote, window)
                if score > best_score:
                    best_score = score
                    best_match = window
                    best_position = i

        if best_score >= 0.70 and best_match:
            sl, el = self._position_to_lines(best_position, len(best_match))
            return (best_match, best_score, (sl, el))

        return None

    def _find_closest_match(self, quoted_text: str) -> Optional[tuple[str, float, tuple[int, int]]]:
        nq = normalize(quoted_text, level="standard")
        best_match: Optional[str] = None
        best_score = 0.0
        best_lines = (0, 0)

        for block_text, sl, el in self.joined_paragraphs:
            score = self._similarity(nq, block_text)
            if score > best_score:
                best_score = score
                best_match = block_text
                best_lines = (sl, el)

        if best_score >= 0.25 and best_match:
            return (best_match, best_score, best_lines)

        return None

    def _adjust_confidence(
        self,
        original_quote: str,
        found_text: str,
        match_type: str,
        base_confidence: float,
    ) -> float:
        confidence = base_confidence

        len_ratio = min(len(original_quote), len(found_text)) / max(len(original_quote), len(found_text), 1)
        if len_ratio > 0.85:
            confidence += 0.03

        if len(original_quote) < 30:
            confidence -= 0.05

        if match_type in ("exact", "exact_normalized", "substring"):
            confidence = min(confidence + 0.02, 1.0)

        return max(0.0, min(1.0, confidence))

    # ── Public API ────────────────────────────────────────────────────

    def verify(self, quoted_text: str) -> VerificationResult:
        """Verify that *quoted_text* appears in the document.

        Args:
            quoted_text: Plain string to look for.

        Returns:
            VerificationResult with match details.
        """
        if not quoted_text or not quoted_text.strip():
            return VerificationResult(
                valid=False,
                error="Empty quoted text",
                confidence=0.0,
            )

        for strategy in (
            self._try_exact_match,
            self._try_normalized_exact_match,
            self._try_substring_match,
            self._try_multiline_fuzzy_match,
            self._try_ngram_match,
            self._try_keyword_anchor_match,
        ):
            result = strategy(quoted_text)
            if result:
                found_text, sl, el, match_type, confidence = result
                confidence = self._adjust_confidence(
                    quoted_text, found_text, match_type, confidence,
                )
                return VerificationResult(
                    valid=confidence >= 0.55,
                    found_text=found_text,
                    confidence=confidence,
                    line_numbers=(sl, el),
                    match_type=match_type,
                )

        close = self._find_closest_match(quoted_text)
        if close:
            snippet = close[0][:200] + "..." if len(close[0]) > 200 else close[0]
            return VerificationResult(
                valid=False,
                found_text=snippet,
                confidence=close[1],
                line_numbers=close[2],
                match_type="close_no_match",
                error=f"Best match ({close[1]:.0%} similar) found but below threshold",
            )

        return VerificationResult(
            valid=False,
            error=f"Could not find quoted text: '{quoted_text[:50]}...'",
            confidence=0.0,
        )


def verify_text(document_text: str, quoted_text: str) -> dict:
    """One-shot convenience: verify *quoted_text* against *document_text*.

    Returns a plain dict (same shape as ``VerificationResult.to_dict()``).
    """
    return Verifier(document_text).verify(quoted_text).to_dict()
