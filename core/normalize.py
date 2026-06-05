"""
core/normalize.py

Single source of truth for record shape and deduplication.

normalize_record() flattens raw CatchAll responses into consistent dicts.
deduplicate() removes duplicates across multiple signal-term queries
using rapidfuzz for fuzzy name + location matching.

Handles two real-world cases:
- Translated names: "LONGJING Restaurant" vs "LONGJING Restaurant 绿茶餐厅"
- Address variations: "6th floor Lucky Plaza" vs "sixth floor, Lucky Plaza"

A record is only dropped if BOTH name AND location match —
two different businesses at the same address won't be merged.
"""

from rapidfuzz import fuzz


# Tunable thresholds for fuzzy matching
NAME_THRESHOLD     = 70  # names vary across punctuation, translations, and aliases
LOCATION_THRESHOLD = 65  # locations vary across abbreviations and formatting


def normalize_record(record: dict) -> dict:
    """Flatten a raw CatchAll record into a consistent flat dict."""
    enrichment = record.get("enrichment", {})
    citations  = record.get("citations", [])

    return {
        "record_id":         record.get("record_id"),
        "record_title":      record.get("record_title"),
        "business_name":     enrichment.get("business_name"),
        "business_type":     enrichment.get("business_type"),
        "opening_date":      enrichment.get("opening_date"),
        "opening_qualifier": enrichment.get("opening_qualifier"),
        "location_details":  enrichment.get("location_details"),
        "owner_operator":    enrichment.get("owner_operator"),
        "evidence_summary":  enrichment.get("evidence_summary"),
        "source_url":        enrichment.get("source_url") or (
            citations[0].get("link") if citations else None
        ),
        "citations":         citations,
        "confidence":        enrichment.get("enrichment_confidence"),
    }


def deduplicate(records: list) -> list:
    """Remove records where both name and location fuzzy-match a previous entry."""
    seen, seen_urls, result = [], set(), []

    for record in records:
        name     = record.get("business_name") or ""
        location = record.get("location_details") or ""
        source_url = record.get("source_url") or ""

        if not name or not location:
            continue

        is_dup = bool(source_url and source_url in seen_urls) or any(
            max(fuzz.token_sort_ratio(name, s_name), fuzz.WRatio(name, s_name)) >= NAME_THRESHOLD
            and max(fuzz.token_sort_ratio(location, s_loc), fuzz.WRatio(location, s_loc)) >= LOCATION_THRESHOLD
            for s_name, s_loc in seen
        )

        if not is_dup:
            seen.append((name, location))
            if source_url:
                seen_urls.add(source_url)
            result.append(record)

    return result


# ── Optional filter helpers — used by dashboard and exports ──

def filter_by_qualifier(records: list, qualifiers: list) -> list:
    return [r for r in records if r.get("opening_qualifier") in qualifiers]


def filter_by_confidence(records: list, level: str = "high") -> list:
    return [r for r in records if r.get("confidence") == level]


def filter_by_business_type(records: list, business_type: str) -> list:
    target = business_type.lower()
    return [r for r in records if target in str(r.get("business_type") or "").lower()]
