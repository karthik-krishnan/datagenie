"""
Prompts for masking.py — convert a plain-English masking instruction into a
structured MaskingOp JSON object.

Usage:
    from prompts.masking_normalize import SYSTEM, TEMPLATE
    prompt = TEMPLATE.format(rule=rule_text.strip())
    raw = llm_provider.generate(prompt, SYSTEM)
"""

SYSTEM = (
    "You are a data-masking rule parser. Convert plain-English masking instructions "
    "into a structured JSON operation. Return ONLY valid JSON, no explanation."
)

TEMPLATE = """Convert this masking rule to a structured operation:

Rule: "{rule}"

Return a JSON object with EXACTLY one of these forms:
  {{"type": "show_last_n_digits",  "n": <integer>}}
  {{"type": "mask_last_n_digits",  "n": <integer>}}
  {{"type": "show_first_n_digits", "n": <integer>}}
  {{"type": "show_last_n_chars",   "n": <integer>}}
  {{"type": "mask_last_n_chars",   "n": <integer>}}
  {{"type": "show_first_n_chars",  "n": <integer>}}
  {{"type": "mask_first_n_chars",  "n": <integer>}}
  {{"type": "partial_email"}}
  {{"type": "date_year_only"}}
  {{"type": "range_bucket", "size": <integer>}}
  {{"type": "redact"}}
  {{"type": "mask_all"}}
  {{"type": "format_preserve_mask"}}

Guidelines:
- "last 4 digits visible" / "show last 4 digits" / "****1234" → show_last_n_digits, n=4
- "mask last 4 digits" / "hide last digit" → mask_last_n_digits, n=<N or 1>
- "show first 6 digits" → show_first_n_digits, n=6
- "mask everything except last character" / "show only last char" → show_last_n_chars, n=1
- "mask everything except last 3 characters" → show_last_n_chars, n=3
- "show last 4 characters" / "reveal last 4 chars" → show_last_n_chars, n=4
- "mask last 3 characters" / "hide last 2 chars" → mask_last_n_chars, n=<N>
- "keep first 3 characters" / "show first 3 chars" → show_first_n_chars, n=3
- "mask first 4 chars" → mask_first_n_chars, n=4
- "mask email" / "obfuscate email" → partial_email
- "year only" / "just the year" → date_year_only
- "age range" / "bucket" / "10-year range" → range_bucket, size=10
- "redact" / "remove" / "blank out" → redact
- "mask everything" / "full mask" / "hide all" (with no exception) → mask_all
- "keep format" / "format-preserving" → format_preserve_mask
- If n is not stated, default to 4 for digit ops, 1 for "last char" ops, 3 for other char ops.
- IMPORTANT: "mask everything except last N chars" means SHOW last N chars → show_last_n_chars

Return ONLY the JSON object.
"""
