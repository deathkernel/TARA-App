"""Optional OpenAI tokenizer utility. Counts are encoding-specific estimates."""
from __future__ import annotations

class TokenizerUnavailable(RuntimeError):
    pass

def count_tokens(text: str, *, encoding_name: str = "o200k_base") -> int:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if not isinstance(encoding_name, str) or not encoding_name.strip():
        raise ValueError("encoding_name must be non-empty")
    try:
        import tiktoken
    except ImportError:
        raise TokenizerUnavailable("install the optional 'tiktoken' package") from None
    try:
        encoding = tiktoken.get_encoding(encoding_name)
    except (KeyError, ValueError):
        raise ValueError("unknown tokenizer encoding") from None
    return len(encoding.encode(text))
