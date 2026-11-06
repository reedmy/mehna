"""Arabic text utilities: normalisation for search, slugs, and snippets.

Arabic search fails when you compare raw strings: أ/إ/آ vs ا, ة vs ه, ى vs ي,
tashkeel, tatweel, and Arabic-Indic digits all need folding first.
"""

from __future__ import annotations

import re
import unicodedata

TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
TATWEEL = "\u0640"
DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Iraqi colloquial → formal, for search synonyms.
SYNONYMS = {
    "سواق": "سائق",
    "سوگ": "سوق",
    "چ": "ك",
    "گ": "ك",
    "هسه": "الآن",
    "شغل": "وظيفة",
    "وظايف": "وظائف",
    "راتب": "راتب",
    "مهندس": "مهندس",
    "محاسب": "محاسب",
    "مبيعات": "مبيعات",
}


def normalize_ar(text: str | None) -> str:
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", str(text))
    out = out.translate(DIGIT_MAP)
    out = TASHKEEL.sub("", out)
    out = out.replace(TATWEEL, "")
    out = re.sub("[أإآٱ]", "ا", out)
    out = out.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    out = re.sub(r"\s+", " ", out)
    return out.strip().lower()


def search_terms(query: str | None) -> list[str]:
    """Split a user query into normalised terms with synonym expansion."""
    return [term for group in search_groups(query) for term in group]


def search_groups(query: str | None) -> list[list[str]]:
    """Terms grouped so that synonyms are OR-ed and tokens are AND-ed."""
    base = normalize_ar(query)
    if not base:
        return []
    groups: list[list[str]] = []
    for token in base.split()[:6]:
        variants = [token]
        synonym = SYNONYMS.get(token)
        if synonym:
            synonym = normalize_ar(synonym)
            if synonym not in variants:
                variants.append(synonym)
        groups.append(variants)
    return groups


_AR_KEEP = re.compile(r"[^\w\u0600-\u06FF]+", re.UNICODE)


def slugify(text: str, fallback: str = "job") -> str:
    base = _AR_KEEP.sub("-", (text or "").strip().lower())
    base = re.sub(r"-{2,}", "-", base).strip("-")
    return base or fallback


def strip_markup(text: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", text or "")


def snippet(text: str | None, length: int = 160) -> str:
    plain = re.sub(r"<[^>]+>", " ", text or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain if len(plain) <= length else plain[: length - 1].rstrip() + "…"
