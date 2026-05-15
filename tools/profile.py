import contextvars
import json
import os
import re
from datetime import date as date_type
from langchain.tools import tool

# ---------------------------------------------------------------------------
# Session context — set by the server before each agent invocation.
# Each async request task gets its own copy, so sessions never bleed across
# concurrent users.  Falls back to "default" for the CLI REPL.
# ---------------------------------------------------------------------------
_current_session: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_session", default="default"
)

# On-disk persistence so profiles survive `uvicorn --reload` and process restarts.
_PROFILE_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".wayfarer_profiles.json",
)


def _load_profiles() -> dict[str, dict]:
    try:
        with open(_PROFILE_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_profiles() -> None:
    try:
        with open(_PROFILE_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(_profiles, f, indent=2)
    except OSError:
        pass


# Per-session profile store  { session_id: { field: value, ... } }
_profiles: dict[str, dict] = _load_profiles()


def set_session(session_id: str) -> None:
    """Call this at the start of each request to bind the session."""
    _current_session.set(session_id)


def _active_profile() -> dict:
    sid = _current_session.get()
    if sid not in _profiles:
        _profiles[sid] = {}
    return _profiles[sid]


def reset_profile(session_id: str | None = None) -> None:
    """Clear the profile for a session (defaults to the current session)."""
    sid = session_id if session_id is not None else _current_session.get()
    _profiles.pop(sid, None)
    _save_profiles()


def get_profile() -> dict:
    return _active_profile()


def ensure_destinations_from_hotel_search(location: str) -> None:
    """
    If destinations are not saved yet but we successfully searched hotels,
    persist the search location so Confirmed Trip Details stays aligned with
    the thread (handles models that skip update_trip_profile).
    """
    loc = (location or "").strip()
    if not loc:
        return
    p = _active_profile()
    if p.get("destinations"):
        return
    p["destinations"] = loc
    _save_profiles()


def _parse_ymd(s: str | None) -> date_type | None:
    """Parse calendar date from strict YYYY-MM-DD or return None."""
    if not isinstance(s, str):
        return None
    t = s.strip()
    try:
        y, mo, d = (int(x) for x in t.split("-"))
        return date_type(y, mo, d)
    except (ValueError, TypeError, AttributeError):
        return None


def format_profile() -> str:
    """Return a human-readable summary of confirmed trip details."""
    profile = _active_profile()
    if not profile:
        return ""

    labels = {
        "destinations":     "Destinations",
        "travel_dates":     "Travel dates",
        "num_travelers":    "Number of travelers",
        "traveler_details": "Traveler details (ages, accessibility, etc.)",
        "travel_style":     "Travel style",
        "flight_trip_type": "Flight trip type",
        "flight_departure": "Flight departure city / metro or airport code",
        "flight_outbound_ymd": "Flight outbound date (confirmed, YYYY-MM-DD)",
        "flight_return_ymd": "Flight return date (confirmed, YYYY-MM-DD)",
        "interests":        "Interests / activities",
        "flights":          "Flights",
        "hotels":           "Hotels",
        "transportation":   "Local transportation",
        "budget_estimate":  "Budget estimate",
        "special_notes":    "Special preferences / notes",
    }

    lines = []
    for key, label in labels.items():
        value = profile.get(key)
        if value:
            lines.append(f"  • {label}: {value}")
    return "\n".join(lines)


@tool
def update_trip_profile(
    destinations: str = None,
    travel_dates: str = None,
    num_travelers: int = None,
    traveler_details: str = None,
    travel_style: str = None,
    flight_trip_type: str = None,
    flight_departure: str = None,
    flight_outbound_ymd: str = None,
    flight_return_ymd: str = None,
    interests: str = None,
    flights: str = None,
    hotels: str = None,
    transportation: str = None,
    budget_estimate: str = None,
    special_notes: str = None,
) -> str:
    """Save or update confirmed trip details to persistent memory.

    Call this tool whenever the user confirms or clearly states any of:
    - destination(s) they have decided on
    - travel dates or trip duration
    - number of travelers or traveler details (e.g. family with 2 kids)
    - travel style (budget / moderate / luxury)
    - flight trip type: pass flight_trip_type="round_trip" or flight_trip_type="one_way"
      when the user chooses via chips or prose (gates flight search — see assistant rules)
    - flight_departure: plain language or IATA origin (e.g. "Los Angeles / LAX") as soon
      as the user answers where they're flying FROM — avoids re-asking later
    - flight_outbound_ymd / flight_return_ymd: strict YYYY-MM-DD after the user
      confirms (round-trip outbound MUST be saved before return is allowed — enforced)
    - interests or activity preferences
    - a flight option they have selected or confirmed
    - a hotel they have selected or confirmed
    - transportation choices (e.g. JR Pass, renting a car)
    - a budget estimate they have accepted
    - any special preferences or requirements

    Only save confirmed or clearly stated information.
    Pass ONLY the fields that have new or updated information — leave others as None.
    """
    updates = {
        k: v for k, v in {
            "destinations":     destinations,
            "travel_dates":     travel_dates,
            "num_travelers":    num_travelers,
            "traveler_details": traveler_details,
            "travel_style":     travel_style,
            "flight_trip_type": flight_trip_type,
            "flight_departure": flight_departure,
            "flight_outbound_ymd": flight_outbound_ymd,
            "flight_return_ymd": flight_return_ymd,
            "interests":        interests,
            "flights":          flights,
            "hotels":           hotels,
            "transportation":   transportation,
            "budget_estimate":  budget_estimate,
            "special_notes":    special_notes,
        }.items()
        if v is not None
    }

    if not updates:
        return "No fields provided — nothing saved."

    profile = _active_profile()

    if "flight_outbound_ymd" in updates:
        fo = str(updates["flight_outbound_ymd"]).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fo) or _parse_ymd(fo) is None:
            return "flight_outbound_ymd must be a valid calendar date as YYYY-MM-DD."
        updates["flight_outbound_ymd"] = fo

    if "flight_return_ymd" in updates:
        fr = str(updates["flight_return_ymd"]).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fr) or _parse_ymd(fr) is None:
            return "flight_return_ymd must be a valid calendar date as YYYY-MM-DD."
        updates["flight_return_ymd"] = fr

    out_effective = updates.get("flight_outbound_ymd") or profile.get(
        "flight_outbound_ymd"
    )
    if "flight_return_ymd" in updates and out_effective is None:
        return (
            "Cannot save flight_return_ymd before flight_outbound_ymd — confirm when the "
            "user DEPARTs first, save outbound as YYYY-MM-DD, then collect return."
        )

    if "flight_return_ymd" in updates:
        ou = updates.get("flight_outbound_ymd") or profile.get(
            "flight_outbound_ymd"
        )
        od = _parse_ymd(ou or "")
        rd = _parse_ymd(updates["flight_return_ymd"])
        if od and rd and rd < od:
            return "flight_return_ymd must be on or after flight_outbound_ymd."

    if "flight_outbound_ymd" in updates:
        rr_src = updates.get("flight_return_ymd") or profile.get("flight_return_ymd")
        od = _parse_ymd(updates["flight_outbound_ymd"])
        rd = _parse_ymd(rr_src or "")
        if od and rd and rd < od:
            return (
                "flight_outbound_ymd is after the saved flight_return_ymd — update or "
                "clear return first."
            )

    if "flight_trip_type" in updates:
        raw = str(updates["flight_trip_type"]).strip().lower().replace("-", " ")
        compact = raw.replace(" ", "")
        if raw in {"round trip", "rt"} or compact == "roundtrip":
            updates["flight_trip_type"] = "round_trip"
        elif raw in {"one way", "oneway"} or compact == "oneway":
            updates["flight_trip_type"] = "one_way"

    if updates.get("flight_trip_type") == "one_way":
        profile.pop("flight_return_ymd", None)

    profile.update(updates)
    _save_profiles()
    saved = ", ".join(updates.keys())
    return f"Profile updated ({saved})."
