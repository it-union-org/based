"""
    Desc: splits long transcripts into sentence-aligned chunks
    Creator: Kirosha
"""

from __future__ import annotations

import re

SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def split_text(text: str, target_size: int = 7000) -> list[str]:
    sentences = SENTENCE_END.split(text)
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for sentence in sentences:
        size = len(sentence)
        if current and current_size + size > target_size:
            chunks.append(" ".join(current))
            current = [sentence]
            current_size = size
        else:
            current.append(sentence)
            current_size += size
    if current:
        chunks.append(" ".join(current))
    return chunks
