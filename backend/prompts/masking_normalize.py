"""
Prompts for masking.py — convert a plain-English masking instruction into a
Python lambda that masks a string value.

Usage:
    from prompts.masking_normalize import SYSTEM, TEMPLATE
    prompt = TEMPLATE.format(rule=rule_text.strip())
    raw = llm_provider.generate(prompt, SYSTEM)
"""

SYSTEM = (
    "You are a data-masking code generator. Convert plain-English masking instructions "
    "into a Python lambda. Return ONLY valid JSON, no explanation."
)

TEMPLATE = """Convert this masking rule into a Python lambda that takes a string and returns the masked string.

Rule: "{rule}"

Return a JSON object with exactly this form:
  {{"fn": "lambda v: <expression>"}}

Requirements:
- The lambda takes a single string argument `v`
- Returns a string with the masking applied
- Use `*` as the masking character
- No imports, no function calls outside of built-ins (len, str, etc.)
- Handle edge cases (e.g. string shorter than expected)

Examples:
- "mask last 4 characters" → {{"fn": "lambda v: v[:-4] + '****' if len(v) > 4 else '*' * len(v)"}}
- "show only last 4 digits" → {{"fn": "lambda v: '*' * (len(v) - 4) + v[-4:] if len(v) > 4 else v"}}
- "mask first and last character" → {{"fn": "lambda v: '*' + v[1:-1] + '*' if len(v) > 2 else '*' * len(v)"}}
- "redact" → {{"fn": "lambda v: '[REDACTED]'"}}
- "mask all" → {{"fn": "lambda v: '*' * len(v)"}}

Return ONLY the JSON object.
"""
