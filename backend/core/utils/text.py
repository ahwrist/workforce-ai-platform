import re


def clean_html(html: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, max_tokens: int = 2000, chars_per_token: int = 4) -> list[str]:
    """Split text into chunks of approximately max_tokens each."""
    max_chars = max_tokens * chars_per_token
    if len(text) <= max_chars:
        return [text]
    chunks = []
    while text:
        chunk = text[:max_chars]
        last_break = max(chunk.rfind("\n"), chunk.rfind(". "), chunk.rfind(" "))
        if last_break > max_chars // 2:
            chunk = text[:last_break]
        chunks.append(chunk.strip())
        text = text[len(chunk):].strip()
    return chunks
