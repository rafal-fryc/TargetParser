# TargetParser

Anti-hallucination PDF line extraction and verification toolkit.

An LLM returns line numbers, Python deterministically extracts the exact text — no hallucinated quotes possible.

## The Problem

When LLMs extract information from PDFs, they often hallucinate quotes — returning text that *looks* right but doesn't actually appear in the document. TargetParser eliminates this by splitting the job into deterministic steps:

1. **Read** the PDF into line-numbered text
2. **LLM identifies** the relevant line numbers (not the text itself)
3. **Python extracts** the exact text from those lines
4. **Verify** that any quoted text actually exists in the source

## Where It Fits

TargetParser is a building block, not a standalone application. It sits between your PDF ingestion and your LLM output, providing the deterministic extraction and verification layer that prevents hallucinated quotes.

A typical pipeline looks like this:

```
Your PDF source (any format)
  │
  ▼
read_pdf()              →  Line-numbered text with page markers
  │
  ▼
Your LLM / agent        →  "The relevant clause is on lines 42-45"
  │
  ▼
extract_lines()         →  Exact text from lines 42-45 (deterministic)
  │
  ▼
Verifier.verify()       →  Confirms the text exists in the source (optional)
  │
  ▼
Your downstream system   →  Search index, report, database, UI, etc.
```

The key insight: the LLM never produces the quoted text — it only identifies *where* the text is. Python handles the extraction, making hallucinated quotes impossible.

### Example: Contract Review Pipeline

```python
from targetparser import read_pdf, resolve_items, Verifier

# 1. Ingest the PDF
doc = read_pdf("contract.pdf")

# 2. Send line-numbered text to your LLM, get structured output back
#    (use whatever LLM client / framework you already have)
llm_findings = call_your_llm(doc.text)
# [{"finding": "Non-compliant clause", "quote_start_line": 42, "quote_end_line": 44},
#  {"finding": "Missing definition",   "quote_start_line": 87, "quote_end_line": 89}]

# 3. TargetParser fills in the actual text deterministically
resolve_items(doc.text, llm_findings)
# Each item now has a "quoted_text" key with the exact text from those lines

# 4. Optionally verify any LLM-generated quotes you don't fully trust
verifier = Verifier(doc.text)
for item in llm_findings:
    result = verifier.verify(item["quoted_text"])
    item["verified"] = result.valid
    item["confidence"] = result.confidence

# 5. Pass the verified results to whatever comes next in your system
store_findings(llm_findings)
```

### Example: Single Extraction

```python
from targetparser import extract_lines

# You already have document text from any source — TargetParser doesn't
# care how you got it, as long as it's line-delimited text
result = extract_lines(document_text, start_line=42, end_line=45)
print(result.text)       # Exact text from lines 42-45
print(result.num_lines)  # Number of content lines extracted
```

### Verification Engine

The `Verifier` uses a 6-tier matching strategy to handle the messy reality of PDF text extraction (encoding quirks, smart quotes, line breaks mid-sentence):

1. **Exact** — standard normalization
2. **Exact normalized** — aggressive normalization (no punctuation)
3. **Substring** — containment check across joined lines
4. **Fuzzy multiline** — SequenceMatcher with sliding window
5. **N-gram overlap** — 4-gram intersection scoring
6. **Keyword anchor** — long-word anchoring with similarity

```python
from targetparser import Verifier

verifier = Verifier(document_text)
result = verifier.verify("some quoted text")
result.valid        # True/False
result.confidence   # 0.0 to 1.0
result.match_type   # "exact", "fuzzy_multiline", "ngram", etc.
result.line_numbers # (start_line, end_line) where found
```

## MCP Server

TargetParser includes an MCP (Model Context Protocol) server so any LLM agent can call the pipeline directly. It exposes three tools:

| Tool | Description |
|------|-------------|
| `read_pdf` | Read a PDF and cache its text server-side |
| `extract_lines` | Extract text from a cached document by line range |
| `verify_text` | Verify whether quoted text appears in a cached document |

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "targetparser": {
      "command": "targetparser-mcp"
    }
  }
}
```

## License

MIT
