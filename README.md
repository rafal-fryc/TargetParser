# TargetParser

Anti-hallucination PDF line extraction and verification toolkit.

An LLM returns line numbers, Python deterministically extracts the exact text — no hallucinated quotes possible.

## The Problem

When LLMs extract information from PDFs, they often hallucinate quotes — returning text that *looks* right but doesn't actually appear in the document. TargetParser eliminates this by splitting the job into deterministic steps:

1. **Read** the PDF into line-numbered text
2. **LLM identifies** the relevant line numbers (not the text itself)
3. **Python extracts** the exact text from those lines
4. **Verify** that any quoted text actually exists in the source

## Installation

```bash
pip install targetparser
```

For MCP server support:

```bash
pip install targetparser[mcp]
```

## Python API

### Read a PDF

```python
from targetparser import read_pdf

result = read_pdf("document.pdf")
print(result.text)       # Full text with "--- Page N ---" markers
print(result.num_pages)  # Total page count
```

### Extract Lines

After an LLM identifies line numbers, extract the exact text:

```python
from targetparser import extract_lines

result = extract_lines(document_text, start_line=42, end_line=45)
print(result.text)       # Exact text from lines 42-45
print(result.num_lines)  # Number of content lines extracted
```

### Batch Resolve LLM Output

When your LLM returns structured JSON with line references, resolve them all at once:

```python
from targetparser import resolve_items

# LLM returned these items with line numbers
items = [
    {"finding": "Non-compliant clause", "quote_start_line": 42, "quote_end_line": 44},
    {"finding": "Missing definition", "quote_start_line": 87, "quote_end_line": 89},
]

# Python fills in the actual text deterministically
resolve_items(document_text, items)
# Each item now has a "quoted_text" key with the exact text from those lines
```

### Verify Quotes

Check whether text actually appears in the document using a 6-tier matching engine (exact, normalized, substring, fuzzy multiline, n-gram overlap, keyword anchor):

```python
from targetparser import Verifier

verifier = Verifier(document_text)

result = verifier.verify("some quoted text from the document")
print(result.valid)       # True/False
print(result.confidence)  # 0.0 to 1.0
print(result.match_type)  # "exact", "fuzzy_multiline", "ngram", etc.
print(result.line_numbers) # (start_line, end_line) where found
```

Or as a one-shot:

```python
from targetparser import verify_text

result = verify_text(document_text, "some quoted text")
# Returns a plain dict with valid, confidence, match_type, etc.
```

## MCP Server

TargetParser includes an MCP (Model Context Protocol) server so any LLM agent can use it as a tool. It exposes three tools:

| Tool | Description |
|------|-------------|
| `read_pdf` | Read a PDF and cache its text server-side |
| `extract_lines` | Extract text from a cached document by line range |
| `verify_text` | Verify whether quoted text appears in a cached document |

### Claude Desktop Configuration

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

### Run Standalone

```bash
targetparser-mcp
```

## How It Works

```
PDF File
  │
  ▼
read_pdf()          →  Line-numbered text with page markers
  │
  ▼
LLM                 →  "The relevant clause is on lines 42-45"
  │
  ▼
extract_lines()     →  Exact text from lines 42-45 (deterministic)
  │
  ▼
Verifier.verify()   →  Confirms the text exists in the source (optional)
```

The key insight: the LLM never produces the quoted text — it only identifies *where* the text is. Python handles the extraction, making hallucinated quotes impossible.

## License

MIT
