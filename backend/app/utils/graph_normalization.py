"""
Helpers for cleaning local graph data before it reaches the UI or persona pipeline.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


GENERIC_EDGE_NAMES = {
    "",
    "RELATES_TO",
    "RELATED_TO",
    "RELATED",
    "ASSOCIATED_WITH",
    "CONNECTED_TO",
    "UNKNOWN",
}

CORP_SUFFIXES = {
    "inc",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "llc",
    "plc",
    "group",
    "holdings",
}

ENTITY_TYPE_PRIORITY = {
    "Entity": 0,
    "Organization": 1,
    "Community": 2,
    "MediaOutlet": 3,
    "GovernmentAgency": 3,
    "University": 3,
    "Person": 3,
    "Company": 4,
}


def clean_display_name(name: str) -> str:
    value = re.sub(r"\s+", " ", (name or "").replace("\n", " ")).strip()
    return value.strip(" ,;:-")


def canonicalize_entity_name(name: str) -> str:
    cleaned = clean_display_name(name).lower()
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    tokens = [token for token in cleaned.split() if token and token not in CORP_SUFFIXES]
    return " ".join(tokens)


def preferred_display_name(names: Iterable[str]) -> str:
    candidates = [clean_display_name(name) for name in names if clean_display_name(name)]
    if not candidates:
        return "Unnamed"
    candidates.sort(key=lambda value: (len(value) > 48, len(value), value.lower()))
    return candidates[0]


def infer_entity_type(
    labels: List[str] | None,
    attributes: Dict[str, Any] | None,
    name: str = "",
    summary: str = "",
) -> str:
    for label in labels or []:
        if label not in {"Entity", "Node"}:
            return label

    attrs = attributes or {}
    for key in ("entity_type", "type", "category", "kind"):
        value = attrs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    clean_name = clean_display_name(name).lower()
    text = f"{name} {summary}".lower()
    if re.search(r"\b(users|members|member|community|forum|subreddit|audience)\b", clean_name):
        return "Community"
    if re.search(r"\b(team|editorial|desk)\b", clean_name):
        return "MediaOutlet"
    if re.search(r"\b(stock|shares|revenue|earnings|operating margin|market cap|cloud|semiconductor|software|ai services)\b", text):
        return "Company"
    if re.search(r"\b(microsoft|google|alphabet|amazon|apple|nvidia|intel|amd|meta|tesla|openai)\b", text):
        return "Company"
    if re.search(r"\b(university|college|school|institute)\b", text):
        return "University"
    if re.search(r"\b(government|ministry|agency|department|senate|congress|regulator)\b", text):
        return "GovernmentAgency"
    if re.search(r"\b(news|media|press|journal|times|post|herald|outlet|publication|editorial)\b", text):
        return "MediaOutlet"
    if re.search(r"\b(forum|community|subreddit|plaza|network|platform)\b", text):
        return "Community"
    if re.search(r"\b(bank|fund|capital|ventures|partners)\b", text):
        return "Organization"
    if re.search(r"\b(ceo|founder|investor|analyst|journalist|reporter|author|person|executive)\b", text):
        return "Person"
    if re.search(r"\b(inc|corp|corporation|company|ltd|llc|semiconductor|technologies|systems)\b", text):
        return "Company"
    if re.fullmatch(r"[A-Z]{2,6}", clean_display_name(name)):
        return "Company"
    return "Entity"


def choose_stronger_entity_type(current_type: str, candidate_type: str) -> str:
    current_priority = ENTITY_TYPE_PRIORITY.get(current_type or "Entity", 0)
    candidate_priority = ENTITY_TYPE_PRIORITY.get(candidate_type or "Entity", 0)
    return candidate_type if candidate_priority >= current_priority else current_type


def normalize_edge_name(name: str, fact: str = "") -> str:
    base = clean_display_name((name or "").replace("_", " ").replace("-", " "))
    generic_key = base.upper().replace(" ", "_")
    if generic_key not in GENERIC_EDGE_NAMES and base:
        return re.sub(r"\s+", " ", base)

    snippet = clean_display_name(fact)
    if not snippet:
        return "Related"

    snippet = re.split(r"[.;]|, and |, but ", snippet, maxsplit=1)[0].strip()
    words = snippet.split()
    if len(words) > 5:
        snippet = " ".join(words[:5]) + "..."
    return snippet or "Related"


def canonical_relation_key(name: str, fact_type: str = "", fact: str = "") -> str:
    label = normalize_edge_name(name or fact_type, fact).lower()
    return re.sub(r"[^a-z0-9]+", "_", label).strip("_") or "related"
