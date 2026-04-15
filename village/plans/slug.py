"""Slug generation from objective text."""

import re


def slugify(text: str, max_length: int = 50) -> str:
    """Convert objective text to a URL-safe slug.

    - Lowercase alphanumeric and hyphens only
    - Max 50 characters
    - Removes common words for brevity
    """
    common_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        # Common words to filter for brevity
        "new",
        "system",
    }

    text = text.lower()

    text = re.sub(r"[^a-z0-9\s-]", "", text)

    words = text.split()
    # Filter: remove common words or single-char words
    words = [w for w in words if w not in common_words and len(w) > 1]

    slug = "-".join(words)

    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")

    return slug[:max_length]


def generate_slug(objective: str) -> str:
    """Generate a deterministic slug from objective text."""
    return slugify(objective)
