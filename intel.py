"""
intel.py

Deterministic intelligence layer for Hyperlocal Business Intel.

Use this file after CatchAll returns structured business-opening records.
It calculates a safe, non-hallucinated readout from the records:

- total records
- top business type
- most common opening signal
- source-backed records
- records with opening dates
- records with owner/operator details
- high-confidence records
- top areas
- actionability score
- recommended review priority

Optional: call generate_ai_readout() to narrate the deterministic stats with an LLM.
The core facts are still calculated deterministically.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


Record = Dict[str, Any]


@dataclass
class TopValue:
    value: str
    count: int


@dataclass
class IntelSummary:
    total_records: int
    actionability_score: int
    top_business_type: Optional[TopValue]
    top_opening_signal: Optional[TopValue]
    top_areas: List[TopValue]
    source_backed_records: int
    records_with_opening_dates: int
    records_with_owner_operator: int
    records_with_location: int
    high_confidence_records: int
    review_priority: str
    readout: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)

        # dataclasses turn nested objects into dicts already,
        # but keep this method explicit for FastAPI/JSON use.
        return data


def _clean(value: Any) -> str:
    """Return a safe, stripped string."""
    if value is None:
        return ""
    return str(value).strip()


def _normalize(value: Any) -> str:
    """Normalize values for counting/deduping."""
    return _clean(value).lower().replace("_", " ")


def _title(value: Any) -> str:
    """Light title casing for UI output."""
    cleaned = _clean(value).replace("_", " ")
    if not cleaned:
        return "Unknown"
    return " ".join(word.capitalize() for word in cleaned.split())


def _has_value(record: Record, field: str) -> bool:
    return bool(_clean(record.get(field)))


def _is_high_confidence(record: Record) -> bool:
    """
    Supports common confidence formats:
    - "high"
    - "High confidence"
    - "82%"
    - 0.82
    - 82
    """
    raw = record.get("confidence")
    if raw is None:
        return False

    if isinstance(raw, (int, float)):
        score = float(raw)
        if 0 <= score <= 1:
            return score >= 0.70
        return score >= 70

    text = _normalize(raw)
    if not text:
        return False

    if "high" in text:
        return True

    try:
        score = float(text.replace("%", ""))
        if 0 <= score <= 1:
            return score >= 0.70
        return score >= 70
    except ValueError:
        return False


def _top_value(records: List[Record], field: str) -> Optional[TopValue]:
    counts: Counter[str] = Counter()

    for record in records:
        value = _normalize(record.get(field))
        if value:
            counts[value] += 1

    if not counts:
        return None

    value, count = counts.most_common(1)[0]
    return TopValue(value=_title(value), count=count)


def _top_areas(records: List[Record], limit: int = 3) -> List[TopValue]:
    """
    Uses location_details as the area source.

    This stays simple on purpose. If you later add a normalized area/neighborhood
    field, update this function to prefer that field.
    """
    counts: Counter[str] = Counter()

    for record in records:
        location = _clean(record.get("location_details"))
        if not location:
            continue

        # Use the first comma-separated part as a lightweight area label.
        area = location.split(",")[0].strip()
        if area:
            counts[_normalize(area)] += 1

    return [
        TopValue(value=_title(value), count=count)
        for value, count in counts.most_common(limit)
    ]


def calculate_actionability_score(records: List[Record]) -> int:
    """
    Scores how usable the returned dataset is.

    This is not a market opportunity score.
    It only measures how complete and reviewable the records are.
    """
    total = len(records)
    if total == 0:
        return 0

    source_backed = sum(_has_value(r, "source_url") for r in records) / total
    with_dates = sum(_has_value(r, "opening_date") for r in records) / total
    with_owner = sum(_has_value(r, "owner_operator") for r in records) / total
    with_location = sum(_has_value(r, "location_details") for r in records) / total
    high_confidence = sum(_is_high_confidence(r) for r in records) / total

    # Source and location matter most because they make the record verifiable/actionable.
    weighted_score = (
        source_backed * 0.30
        + with_location * 0.25
        + with_dates * 0.20
        + high_confidence * 0.15
        + with_owner * 0.10
    )

    return round(max(0, min(100, weighted_score * 100)))


def choose_review_priority(
    records_with_owner_operator: int,
    records_with_opening_dates: int,
    source_backed_records: int,
) -> str:
    if records_with_owner_operator > 0:
        return "Prioritize records with owner/operator details for outreach or deeper research."
    if records_with_opening_dates > 0:
        return "Prioritize records with opening dates to understand what is recent and actionable."
    if source_backed_records > 0:
        return "Start with source-backed records and verify the most relevant businesses."
    return "Review the returned records manually and confirm source quality before acting."


def build_readout(
    *,
    total_records: int,
    top_business_type: Optional[TopValue],
    top_opening_signal: Optional[TopValue],
    source_backed_records: int,
    records_with_opening_dates: int,
    records_with_owner_operator: int,
    review_priority: str,
) -> str:
    if total_records == 0:
        return "No records were returned yet. Try expanding the timeframe, location, or business type."

    if top_business_type:
        category_sentence = (
            f"The strongest category signal is {top_business_type.value}, "
            f"appearing in {top_business_type.count} record"
            f"{'' if top_business_type.count == 1 else 's'}."
        )
    else:
        category_sentence = "No dominant business type was returned yet."

    if top_opening_signal:
        signal_sentence = (
            f"The most common opening signal is {top_opening_signal.value}, "
            f"appearing in {top_opening_signal.count} record"
            f"{'' if top_opening_signal.count == 1 else 's'}."
        )
    else:
        signal_sentence = "The records do not share a common opening signal yet."

    quality_sentence = (
        f"{source_backed_records}/{total_records} records include source URLs, "
        f"{records_with_opening_dates}/{total_records} include opening dates, and "
        f"{records_with_owner_operator}/{total_records} include owner/operator details."
    )

    return f"{category_sentence} {signal_sentence} {quality_sentence} Next step: {review_priority}"


def build_opening_intel(records: List[Record]) -> IntelSummary:
    """
    Main function to call from your backend.

    Example:
        intel = build_opening_intel(results)
        return intel.to_dict()
    """
    total = len(records)

    top_business_type = _top_value(records, "business_type")
    top_opening_signal = _top_value(records, "opening_qualifier")
    top_areas = _top_areas(records)

    source_backed_records = sum(_has_value(r, "source_url") for r in records)
    records_with_opening_dates = sum(_has_value(r, "opening_date") for r in records)
    records_with_owner_operator = sum(_has_value(r, "owner_operator") for r in records)
    records_with_location = sum(_has_value(r, "location_details") for r in records)
    high_confidence_records = sum(_is_high_confidence(r) for r in records)

    actionability_score = calculate_actionability_score(records)

    review_priority = choose_review_priority(
        records_with_owner_operator=records_with_owner_operator,
        records_with_opening_dates=records_with_opening_dates,
        source_backed_records=source_backed_records,
    )

    readout = build_readout(
        total_records=total,
        top_business_type=top_business_type,
        top_opening_signal=top_opening_signal,
        source_backed_records=source_backed_records,
        records_with_opening_dates=records_with_opening_dates,
        records_with_owner_operator=records_with_owner_operator,
        review_priority=review_priority,
    )

    return IntelSummary(
        total_records=total,
        actionability_score=actionability_score,
        top_business_type=top_business_type,
        top_opening_signal=top_opening_signal,
        top_areas=top_areas,
        source_backed_records=source_backed_records,
        records_with_opening_dates=records_with_opening_dates,
        records_with_owner_operator=records_with_owner_operator,
        records_with_location=records_with_location,
        high_confidence_records=high_confidence_records,
        review_priority=review_priority,
        readout=readout,
    )


def build_llm_prompt(intel: IntelSummary, user_query: Optional[str] = None) -> str:
    """
    Optional: pass this prompt to your existing LLM layer.

    The LLM should only narrate the deterministic stats.
    It should not invent demand, market size, hiring intent, revenue, or trends.

    user_query is optional:
    - If provided, the LLM answers that question using only the stats.
    - If omitted, the LLM writes a general 2–3 sentence readout.
    """
    query = _clean(user_query)

    if query:
        task = f"""
User question:
{query}

Answer the user's question using only the stats below.
If the stats are not enough to answer confidently, say what is missing.
Keep the answer short and practical.
"""
    else:
        task = """
Write 2 short insights and 1 recommended next step from the stats below.
Keep the answer short and practical.
"""

    return f"""
You are analyzing structured business opening records.

Use only the stats below. Do not invent market trends, demand, revenue, foot traffic,
hiring intent, or opportunity claims.

{task}

Stats:
{intel.to_dict()}
""".strip()


async def generate_ai_readout(
    intel: IntelSummary,
    *,
    user_query: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    model: str = "google/gemini-flash-1.5",
    site_url: str = "http://localhost",
    app_name: str = "Hyperlocal Business Intel",
) -> str:
    """
    Optional LLM narrator for the deterministic intel summary.

    This function does NOT ask the LLM to calculate facts.
    It only asks the model to explain the already-calculated stats.

    Usage:
        intel = build_opening_intel(results)
        ai_readout = await generate_ai_readout(
            intel,
            user_query="Which records should I review first?",
            openrouter_api_key=os.environ["OPENROUTER_API_KEY"],
        )

    Returns:
        A short, UI-ready readout string.

    If no API key is passed, it returns the deterministic readout instead.
    """
    if not openrouter_api_key:
        return intel.readout

    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError(
            "httpx is required for generate_ai_readout(). Install it with: pip install httpx"
        ) from exc

    prompt = build_llm_prompt(intel, user_query=user_query)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful market-intelligence narrator. "
                    "Use only the provided structured stats. "
                    "Do not invent trends, demand, revenue, hiring intent, market size, "
                    "foot traffic, or claims not supported by the stats. "
                    "Keep the response short, specific, and useful."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 180,
    }

    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url,
        "X-Title": app_name,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    message = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    return message or intel.readout


async def build_opening_intel_with_ai(
    records: List[Record],
    *,
    user_query: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    model: str = "google/gemini-flash-1.5",
) -> Dict[str, Any]:
    """
    Convenience function for FastAPI routes.

    Returns both:
    - deterministic intel
    - optional AI readout

    Example:
        payload = await build_opening_intel_with_ai(
            results,
            user_query="Which records should I review first?",
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
        )

        return {
            "results": results,
            **payload,
        }
    """
    intel = build_opening_intel(records)
    ai_readout = await generate_ai_readout(
        intel,
        user_query=user_query,
        openrouter_api_key=openrouter_api_key,
        model=model,
    )

    return {
        "intel": intel.to_dict(),
        "user_query": _clean(user_query) or None,
        "ai_readout": ai_readout,
    }


def compact_records_for_llm(records: List[Record], limit: int = 40) -> List[Dict[str, Any]]:
    """
    Convert raw opening records into a compact, safer context for dataset chat.

    Keep this compact so the LLM receives enough useful evidence without sending
    huge payloads or unnecessary fields.
    """
    compact: List[Dict[str, Any]] = []

    for record in records[:limit]:
      compact.append({
          "business_name": _clean(record.get("business_name")),
          "business_type": _clean(record.get("business_type")),
          "opening_qualifier": _clean(record.get("opening_qualifier")),
          "location_details": _clean(record.get("location_details")),
          "opening_date": _clean(record.get("opening_date")),
          "owner_operator": _clean(record.get("owner_operator")),
          "evidence_summary": _clean(record.get("evidence_summary")),
          "source_url": _clean(record.get("source_url")),
          "confidence": _clean(record.get("confidence")),
      })

    return compact


def build_dataset_chat_prompt(
    *,
    user_query: str,
    records: List[Record],
    intel: Optional[IntelSummary] = None,
    record_limit: int = 40,
) -> str:
    """
    Build a grounded prompt for chatting with one search result dataset.

    The model can answer questions about the returned records, but it should not
    invent facts that are not in the records.
    """
    compact_records = compact_records_for_llm(records, limit=record_limit)
    summary = intel.to_dict() if intel else build_opening_intel(records).to_dict()

    return f"""
You are answering questions about a structured dataset of business-opening records.

Use only the dataset and deterministic summary below.
Do not invent market demand, revenue, foot traffic, hiring intent, business performance,
or facts not present in the records.
If the data is not enough to answer confidently, say what is missing.
When possible, point the user toward source-backed records.
Keep the answer practical and concise.

User question:
{_clean(user_query)}

Deterministic summary:
{summary}

Records:
{compact_records}
""".strip()


async def chat_with_opening_records(
    records: List[Record],
    user_query: str,
    *,
    openrouter_api_key: Optional[str] = None,
    model: str = "google/gemini-flash-1.5",
    site_url: str = "http://localhost",
    app_name: str = "Hyperlocal Business Intel",
    record_limit: int = 40,
) -> Dict[str, Any]:
    """
    Chat with the returned business-opening dataset.

    This is for user-driven questions like:
    - "Which records should I review first?"
    - "Which businesses have owner/operator info?"
    - "Are there more restaurants or gyms?"
    - "Which records are strongest for sales outreach?"

    If no API key is provided, returns the deterministic readout instead.
    """
    query = _clean(user_query)
    intel = build_opening_intel(records)

    if not query:
        return {
            "answer": intel.readout,
            "used_llm": False,
            "warning": "No question was provided, so the deterministic readout was returned.",
        }

    if not openrouter_api_key:
        return {
            "answer": intel.readout,
            "used_llm": False,
            "warning": "No OpenRouter API key was provided, so the deterministic readout was returned.",
        }

    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError(
            "httpx is required for chat_with_opening_records(). Install it with: pip install httpx"
        ) from exc

    prompt = build_dataset_chat_prompt(
        user_query=query,
        records=records,
        intel=intel,
        record_limit=record_limit,
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful dataset assistant for a business-opening intelligence app. "
                    "Answer only from the provided records and deterministic summary. "
                    "Be useful, but do not overclaim. If the data is incomplete, say so."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 350,
    }

    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url,
        "X-Title": app_name,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    answer = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    return {
        "answer": answer or intel.readout,
        "used_llm": bool(answer),
        "warning": "AI answers can be wrong. Verify important records with the source links.",
    }


if __name__ == "__main__":
    sample_records = [
        {
            "business_name": "Example Bistro",
            "business_type": "restaurant",
            "opening_qualifier": "now_open",
            "location_details": "Orchard Road, Singapore",
            "opening_date": "2026-06-01",
            "owner_operator": "Example Group",
            "source_url": "https://example.com",
            "confidence": "high",
        },
        {
            "business_name": "Example Gym",
            "business_type": "gym",
            "opening_qualifier": "date_announced",
            "location_details": "Tanjong Pagar, Singapore",
            "source_url": "https://example.com/gym",
            "confidence": "72%",
        },
    ]

    summary = build_opening_intel(sample_records)
    print(summary.to_dict())
