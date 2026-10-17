from __future__ import annotations

import re
from collections import Counter

from .models import EvidenceUnit


# Latin words, CJK, kana, and hangul. This is still a character/word overlap baseline.
_TOKEN = re.compile(r"[a-z0-9]+|[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]")


def tokenize(text: str) -> list[str]:
    """Transparent lexical tokens. Not stems, embeddings, or a semantic parser."""
    return _TOKEN.findall(text.casefold())


def retrieve(claim: str, units: list[EvidenceUnit], top_k: int = 5) -> list[EvidenceUnit]:
    """Rank chunks by token overlap. An exact casefolded substring always outranks a partial overlap.

    Paraphrases, changed word forms, and passages that share no tokens are missed.
    A relevant chunk can also fall outside top-k when it only shares common tokens
    with the claim, or when a long exact passage is not an exact substring of one chunk.
    """
    folded = claim.strip().casefold()
    words = Counter(tokenize(claim))
    if not words and not folded:
        return []
    ranked: list[tuple[float, str, EvidenceUnit]] = []
    claim_size = sum(words.values())
    for unit in units:
        unit_words = Counter(tokenize(unit.text))
        overlap = sum(min(count, unit_words.get(word, 0)) for word, count in words.items())
        exact = bool(folded) and folded in unit.text.casefold()
        if not overlap and not exact:
            continue
        lexical = 0.0
        if claim_size:
            # Longer chunks need more than a few shared tokens to rank first.
            lexical = overlap / (claim_size + 0.05 * sum(unit_words.values()))
        score = lexical + (1.0 if exact else 0.0)
        ranked.append((score, unit.id, unit))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]))
    return [unit for _, _, unit in ranked[:top_k]]
