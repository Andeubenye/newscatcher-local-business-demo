"""
Skill config for the Hyperlocal Business Intel demo.

SKILL_CONTEXT   — the full skill file, passed as context= to CatchAll.
                  Tells the extraction layer what counts as a valid opening,
                  how to structure queries, and what the fallback protocol is.

VALIDATORS      — boolean checks passed as validators= to CatchAll.
                  Records that fail any validator are excluded from results.

ENRICHMENTS     — fields passed as enrichments= to CatchAll.
                  Defines what structured data to extract from each record.
"""

from pathlib import Path

# Load from skills/ folder relative to project root
SKILL_CONTEXT = (Path(__file__).parent.parent / "skills" / "local-business-openings.md").read_text()

VALIDATORS = [
    {
        "name": "is_business_opening",
        "description": (
            "True only if source text explicitly states one of: "
            "(1) the business is currently open to paying customers, "
            "(2) a grand opening, ribbon cutting, or soft launch event has taken place, "
            "(3) an official opening date within the next 30 days announced by the business "
            "or a named credible source. False for permit filings, construction notices, "
            "undated coming-soon language, rumours, or businesses outside the searched location."
        ),
        "type": "boolean",
    },
    {
        "name": "location_match",
        "description": (
            "True if the business physical address or neighbourhood is within the searched location. "
            "False if the business is located elsewhere and only references the searched location."
        ),
        "type": "boolean",
    },
    {
        "name": "event_in_timeframe",
        "description": (
            "True if the opening occurred or was officially announced within the specified window. "
            "False if the date is outside the window, unconfirmed, or cannot be determined."
        ),
        "type": "boolean",
    },
]

ENRICHMENTS = [
    {"name": "business_name",     "description": "Name of the opening business",                                      "type": "text"},
    {"name": "business_type",     "description": "Category: restaurant, cafe, retail, clinic, gym, etc.",             "type": "text"},
    {"name": "opening_date",      "description": "Confirmed or scheduled opening date in YYYY-MM-DD format",          "type": "date"},
    {"name": "opening_qualifier", "description": "now_open, event_held, or date_announced",                           "type": "text"},
    {"name": "location_details",  "description": "Street address, neighbourhood, or area",                            "type": "text"},
    {"name": "owner_operator",    "description": "Owner, chef, or operating company if mentioned",                    "type": "text"},
    {"name": "evidence_summary",  "description": "One sentence from the source that confirms this is a real opening", "type": "text"},
    {"name": "source_url",        "description": "URL where the opening was reported",                                "type": "text"},
]
