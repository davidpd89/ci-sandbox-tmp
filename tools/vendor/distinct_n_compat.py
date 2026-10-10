"""Adapted from neural-dialogue-metrics/Distinct-N, MIT, Cong Feng (2019).

Upstream commit e94edcb2e1d2230ff9e0f1821387d7f6d7af0c4f.
Based on distinct_n/metrics.py and distinct_n/utils.py. Changes: safe short
sequences, corpus-level *pooled* diversity and no dependency on nltk.
See docs/research/reply-candidate-diversity-114.md and LICENSE.distinct-n.txt.
"""
from __future__ import annotations


def ngrams(words: list[str], n: int):
    """Yield contiguous ngrams, including none when text is too short."""
    if type(n) is not int or n < 1:
        raise ValueError("n debe ser un entero positivo")
    for i in range(max(len(words) - n + 1, 0)):
        yield tuple(words[i:i + n])


def distinct_n_sentence_level(words: list[str], n: int) -> float:
    """Upstream sentence metric: unique ngrams divided by word count."""
    grams = set(ngrams(words, n))
    return len(grams) / len(words) if words else 0.0


def distinct_n_corpus_level(sentences: list[list[str]], n: int) -> float:
    """Upstream macro average, made safe for empty input."""
    if not sentences:
        return 0.0
    return sum(distinct_n_sentence_level(s, n) for s in sentences) / len(sentences)


def distinct_n_pooled(sentences: list[list[str]], n: int) -> float:
    """Micro metric: unique ngrams / total ngrams (diagnostic only)."""
    grams = [gram for sentence in sentences for gram in ngrams(sentence, n)]
    return len(set(grams)) / len(grams) if grams else 0.0
