import re
from difflib import SequenceMatcher
from typing import List, Set

_SENT_RE = re.compile(r'(?<=[\.\?\!])\s+')
_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)

def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = [p.strip() for p in _SENT_RE.split(text.strip()) if p.strip()]
    return parts

def _tokens(text: str) -> List[str]:
    if not text:
        return []
    return _WORD_RE.findall(text.lower())

def _unique_tokens(text: str) -> Set[str]:
    return set(_tokens(text))

def _sequence_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = a & b
    union = a | b
    return float(len(inter)) / max(1, len(union))

def _extract_facts(text: str) -> Set[str]:
    """Extract numbers, simple dates, and capitalized multi-word phrases as 'facts'."""
    if not text:
        return set()
    facts = set()
    # numbers, percents, currency
    for m in re.findall(r'\b\d[\d,\.%/-]*\b', text):
        facts.add(m.strip())
    # simple month-day(, year) dates like Nov 15 or November 15, 2025
    for m in re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\.?\s+\d{1,2}(?:,\s*\d{4})?\b', text, flags=re.I):
        facts.add(m.strip())
    # capitalized sequences (proper names/places)
    for m in re.findall(r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3})\b', text):
        if len(m.split()) >= 1:
            facts.add(m.strip())
    # normalize
    return {f.lower() for f in facts if len(f) > 0}

def _fact_preservation_score(article: str, summary: str) -> float:
    """Fraction of extracted facts from article that appear (case-insensitive) in summary."""
    facts = _extract_facts(article)
    if not facts:
        return 1.0
    summary_l = (summary or "").lower()
    matched = 0
    for f in facts:
        if f in summary_l:
            matched += 1
    return float(matched) / float(len(facts))

def compute_summary_similarity(article: str, summary: str) -> float:
    """
    Combined score (0..100):
      - Sentence-level best-match average (70% weight)
      - Jaccard token overlap (20%)
      - Fact-preservation (10%)
    """
    if not article or not summary:
        return 0.0

    art_sents = _split_sentences(article)
    sum_sents = _split_sentences(summary)
    if not sum_sents:
        return 0.0

    # For each summary sentence, best matching article sentence by sequence ratio
    per_sent_scores = []
    for s in sum_sents:
        best = 0.0
        for a in art_sents:
            r = _sequence_ratio(s.lower(), a.lower())
            if r > best:
                best = r
            if best >= 0.999:
                break
        per_sent_scores.append(best)
    avg_seq = sum(per_sent_scores) / max(1, len(per_sent_scores))

    jacc = _jaccard(_unique_tokens(article), _unique_tokens(summary))
    fact_score = _fact_preservation_score(article, summary)

    # weights (tune these in environment or here)
    w_seq = 0.7
    w_jacc = 0.2
    w_fact = 0.1

    combined = w_seq * avg_seq + w_jacc * jacc + w_fact * fact_score
    return round(combined * 100, 2)

def compute_translation_consistency(english_summary: str, back_translated: str) -> float:
    """Compare English summary and back-translated text (0..100)."""
    if not english_summary or not back_translated:
        return 0.0
    seq = _sequence_ratio(english_summary.strip().lower(), back_translated.strip().lower())
    jacc = _jaccard(_unique_tokens(english_summary), _unique_tokens(back_translated))
    combined = 0.7 * seq + 0.3 * jacc
    return round(combined * 100, 2)