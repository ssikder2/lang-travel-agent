import json
import os
import re
from datetime import date as date_type
from pathlib import Path

import requests
from langchain.tools import tool

from tools.profile import get_profile

RAPIDAPI_HOST = "booking-com15.p.rapidapi.com"

CABIN_CLASS_MAP = {
    1: "ECONOMY",
    2: "PREMIUM_ECONOMY",
    3: "BUSINESS",
    4: "FIRST",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso_duration(duration: str) -> str:
    """Convert ISO 8601 duration (e.g. 'PT14H30M', 'P1DT7H17M') to '14h 30m'."""
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", duration or "")
    if not m:
        return duration or ""
    days = int(m.group(1) or 0)
    h = int(m.group(2) or 0) + days * 24
    mins = int(m.group(3) or 0)
    if h and mins:
        return f"{h}h {mins}m"
    return f"{h}h" if h else f"{mins}m"


def _fmt_time(iso_dt: str) -> str:
    """Extract HH:MM from an ISO 8601 datetime string."""
    try:
        return iso_dt[11:16]
    except (IndexError, TypeError):
        return iso_dt or ""


def _price_float(offer: dict) -> float:
    try:
        return float(offer.get("price_value", "9999999"))
    except (ValueError, TypeError):
        return 9_999_999.0


def _offer_score(offer: dict, min_price: float, max_price: float, min_mins: int, max_mins: int) -> float:
    """Lower is better: balance price and total travel time."""
    price = float(offer.get("price_value") or 9_999_999.0)
    mins = int(offer.get("duration_minutes") or max_mins or 9_999_999)
    stops = int(offer.get("stops") or 0)

    if max_price > min_price:
        p_norm = (price - min_price) / (max_price - min_price)
    else:
        p_norm = 0.0
    if max_mins > min_mins:
        t_norm = (mins - min_mins) / (max_mins - min_mins)
    else:
        t_norm = 0.0

    # prioritize cost, but still favor shorter itineraries
    return (0.68 * p_norm) + (0.32 * t_norm) + (0.02 * stops)


def _offer_dedupe_key(offer: dict) -> tuple:
    """Stable key to collapse repeated inventory rows from provider tokens."""
    dep = offer.get("departure", {}) or {}
    arr = offer.get("arrival", {}) or {}
    return (
        str(offer.get("airline") or "").strip().lower(),
        str(dep.get("code") or "").strip().upper(),
        str(dep.get("time") or "").strip(),
        str(arr.get("code") or "").strip().upper(),
        str(arr.get("time") or "").strip(),
        int(offer.get("stops") or 0),
        int(round(float(offer.get("price_value") or 9_999_999.0))),
    )


def _rapid_headers() -> dict | None:
    env_file_key = None
    env_path = Path(__file__).resolve().parents[1] / ".env.local"
    try:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("X-RAPIDAPI-KEY="):
                    env_file_key = line.split("=", 1)[1].strip()
                    break
                if line.startswith("X_RAPIDAPI_KEY="):
                    env_file_key = line.split("=", 1)[1].strip()
                    break
    except OSError:
        pass

    key = (
        os.getenv("X_RAPIDAPI_KEY")
        or os.getenv("X-RAPIDAPI-KEY")
        or os.getenv("RAPIDAPI_KEY")
        or env_file_key
    )
    if not key:
        return None
    return {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }


def _rapid_get(path: str, params: dict) -> dict:
    resp = requests.get(
        f"https://{RAPIDAPI_HOST}{path}",
        headers=_rapid_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_iata(value) -> str:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z]{3}", value.strip()):
        return value.strip().upper()
    return ""


def _first_non_empty(*values):
    for v in values:
        if v not in (None, "", []):
            return v
    return None


def _pick_location_id(candidates: list, requested_iata: str) -> str | None:
    """Prefer exact AIRPORT match for an IATA like HND over city matches."""
    req = (requested_iata or "").strip().upper()
    if not candidates:
        return None

    # 1) exact AIRPORT code (best for HND/NRT disambiguation)
    for c in candidates:
        if not isinstance(c, dict):
            continue
        c_code = str(c.get("code") or "").strip().upper()
        c_type = str(c.get("type") or "").strip().upper()
        if c_code == req and c_type == "AIRPORT" and c.get("id"):
            return str(c["id"])

    # 2) exact code regardless of type
    for c in candidates:
        if not isinstance(c, dict):
            continue
        c_code = str(c.get("code") or "").strip().upper()
        if c_code == req and c.get("id"):
            return str(c["id"])

    # 3) fallback first id
    first = candidates[0] if candidates else {}
    if isinstance(first, dict) and first.get("id"):
        return str(first["id"])
    return None


def _coerce_offer(item: dict, dep_id: str, arr_id: str) -> dict:
    segments = item.get("segments") or []
    outbound = segments[0] if isinstance(segments, list) and segments else {}
    legs = outbound.get("legs") if isinstance(outbound, dict) else []
    if not legs and isinstance(outbound, dict):
        legs = [outbound]

    first_leg = legs[0] if isinstance(legs, list) and legs else {}
    last_leg = legs[-1] if isinstance(legs, list) and legs else {}

    dep_code = _extract_iata(
        _first_non_empty(
            (first_leg.get("departureAirport") or {}).get("code"),
            first_leg.get("departureAirportCode"),
            (outbound.get("departureAirport") or {}).get("code"),
            item.get("from"),
            dep_id,
        )
    ) or dep_id
    arr_code = _extract_iata(
        _first_non_empty(
            (last_leg.get("arrivalAirport") or {}).get("code"),
            last_leg.get("arrivalAirportCode"),
            (outbound.get("arrivalAirport") or {}).get("code"),
            item.get("to"),
            arr_id,
        )
    ) or arr_id

    dep_dt = _first_non_empty(
        first_leg.get("departureTime"),
        first_leg.get("departDateTime"),
        outbound.get("departureTime"),
        item.get("departureTime"),
    ) or ""
    arr_dt = _first_non_empty(
        last_leg.get("arrivalTime"),
        last_leg.get("arrivalDateTime"),
        outbound.get("arrivalTime"),
        item.get("arrivalTime"),
    ) or ""
    airline = _first_non_empty(
        (item.get("carrier") or {}).get("name"),
        item.get("airline"),
        item.get("airline_name"),
        ((first_leg.get("carriersData") or [{}])[0]).get("name"),
        ((outbound.get("carriersData") or [{}])[0]).get("name"),
        (first_leg.get("carrier") or {}).get("name"),
        "Unknown Airline",
    )
    flight_num = _first_non_empty(
        (first_leg.get("flightInfo") or {}).get("flightNumber"),
        first_leg.get("flightNumber"),
        first_leg.get("flightNo"),
        item.get("flight_number"),
        "",
    )
    stops = int(_first_non_empty(
        item.get("stops"),
        item.get("stop_count"),
        max(len(legs) - 1, 0),
    ) or 0)
    duration_secs = _first_non_empty(outbound.get("totalTime"), first_leg.get("totalTime"))
    duration_raw = _first_non_empty(item.get("duration"), item.get("flightDuration"), duration_secs, "")

    price_raw = _first_non_empty(
        item.get("price"),
        item.get("totalAmount"),
        ((item.get("priceBreakdown") or {}).get("total") or {}).get("units"),
        ((item.get("unifiedPriceBreakdown") or {}).get("total") or {}).get("units"),
        "",
    )
    m = re.search(r"(\d+(?:\.\d+)?)", str(price_raw))
    price_val = float(m.group(1)) if m else 9_999_999.0
    currency = (
        _first_non_empty(item.get("currency"), item.get("currency_code"), "USD")
        or "USD"
    )

    return {
        "airline": str(airline),
        "airline_logo": _first_non_empty(
            ((first_leg.get("carriersData") or [{}])[0]).get("logo"),
            ((outbound.get("carriersData") or [{}])[0]).get("logo"),
            (first_leg.get("carrier") or {}).get("logo"),
        ),
        "departure": {
            "code": dep_code,
            "time": _fmt_time(str(dep_dt)),
        },
        "arrival": {
            "code": arr_code,
            "time": _fmt_time(str(arr_dt)),
        },
        "duration": (
            _parse_iso_duration(str(duration_raw))
            if isinstance(duration_raw, str)
            else f"{round(float(duration_raw) / 3600, 1)}h"
        ),
        "duration_minutes": int(duration_secs / 60) if isinstance(duration_secs, (int, float)) else None,
        "stops": stops,
        "price": round(price_val),
        "currency": str(currency),
        "flight_number": str(flight_num),
        "url": item.get("url") or item.get("bookingUrl") or "",
        "price_value": price_val,
    }


def _format_offer(offer: dict, index: int) -> str:
    dep_code = offer.get("departure", {}).get("code", "")
    dep_time = offer.get("departure", {}).get("time", "")
    arr_code = offer.get("arrival", {}).get("code", "")
    arr_time = offer.get("arrival", {}).get("time", "")
    duration = offer.get("duration", "")
    stops = int(offer.get("stops", 0) or 0)
    stop_str = "Nonstop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
    currency = offer.get("currency", "USD")
    total = offer.get("price", "N/A")
    airline_str = offer.get("airline", "Unknown")

    lines = [
        f"  {index}. {airline_str} — {currency} {total}",
        f"     {dep_code} {dep_time}  →  {arr_code} {arr_time}",
        f"     {duration} | {stop_str}",
    ]
    if offer.get("flight_number"):
        lines.append(f"     Flight: {offer['flight_number']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

def _parse_iso_date(s: str) -> date_type | None:
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return date_type(y, m, d)
    except (ValueError, TypeError, AttributeError):
        return None


def _today() -> date_type:
    """Today's date in local time; separate for tests."""
    return date_type.today()


def _normalized_profile_trip_type() -> str | None:
    """Return ``one_way`` / ``round_trip`` only when persisted on the trip profile."""
    raw = get_profile().get("flight_trip_type")
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if s in {"one_way", "oneway"}:
        return "one_way"
    if s in {"round_trip", "roundtrip"}:
        return "round_trip"
    return None


@tool
def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str = None,
    adults: int = 1,
    travel_class: int = 1,
    use_today_as_outbound: bool = False,
    allow_same_calendar_day_return: bool = False,
) -> str:
    """Search for real flights using Booking.com15 via RapidAPI.

    Do not call until the user has provided (or the trip profile already contains)
    a real departure location and real travel dates. Never guess the user's origin
    city from the destination alone. Never use today's date as outbound unless
    the user explicitly wanted today — then pass use_today_as_outbound=True.

    Args:
        departure_id: IATA airport code for departure (e.g. 'JFK', 'LHR').
        arrival_id: IATA airport code for arrival (e.g. 'HND', 'NRT', 'CDG').
        outbound_date: Departure date in YYYY-MM-DD format.
        return_date: Return date in YYYY-MM-DD format. Omit for one-way trips.
        adults: Number of adult passengers. Defaults to 1.
        travel_class: Cabin — 1=Economy (default), 2=Premium Economy, 3=Business, 4=First.
        use_today_as_outbound: Set True only if the user explicitly asked to depart today.
        allow_same_calendar_day_return: Set True only when the user truly wants outbound
            and return on the same calendar day (rare). Otherwise duplicate dates are
            rejected — they usually mean date confusion, not real demand.
    """
    if not _rapid_headers():
        return "Error: X-RAPIDAPI-KEY is not set."

    dep = (departure_id or "").strip().upper()
    arr = (arrival_id or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", dep) or not re.fullmatch(r"[A-Z]{3}", arr):
        return (
            "Invalid airport codes: use 3-letter IATA codes (e.g. JFK, HND). "
            "Ask the user for their departure city if you are not sure which airport."
        )

    out_d = _parse_iso_date((outbound_date or "").strip())
    if out_d is None:
        return (
            "outbound_date must be YYYY-MM-DD. Ask the user for their departure date "
            "before searching."
        )

    today = _today()
    if out_d < today:
        return (
            "outbound_date is in the past. Ask the user for a future departure date."
        )

    if out_d == today and not use_today_as_outbound:
        return (
            "Cannot search with today's date unless the user explicitly asked to leave "
            "today. Ask them which date they want to depart, or confirm they want today "
            "and call again with use_today_as_outbound=True."
        )

    ret_d: date_type | None = None
    if return_date:
        ret_d = _parse_iso_date(return_date.strip())
        if ret_d is None:
            return "return_date must be YYYY-MM-DD when provided."
        if ret_d < out_d:
            return (
                "return_date must be on or after outbound_date. Ask the user to confirm "
                "their return date."
            )
        if ret_d == out_d and not allow_same_calendar_day_return:
            return (
                "return_date is the same as outbound_date — for a usual round-trip you "
                "need a later return day. Confirm when they fly home (or retry with "
                "allow_same_calendar_day_return=True if they insisted on same-day)."
            )

    trip_pref = _normalized_profile_trip_type()
    if trip_pref is None:
        return (
            "Flight trip type is not saved yet (one-way vs round-trip). Offer chips, let "
            "the user answer, call update_trip_profile with flight_trip_type=one_way or "
            "flight_trip_type=round_trip, then search. Do not search before that runs."
        )

    if trip_pref == "one_way" and ret_d is not None:
        return (
            "Profile says flight_trip_type is one_way but return_date was provided. Omit "
            "return_date from this tool for one-way, or fix the profile when they want "
            "round-trip instead."
        )

    if trip_pref == "round_trip":
        prof = get_profile()
        out_saved = _parse_iso_date(str(prof.get("flight_outbound_ymd") or ""))
        if out_saved is None:
            return (
                "Round trip: save when they LEAVE first using update_trip_profile("
                'flight_outbound_ymd="YYYY-MM-DD"). Ask outbound before return — do not '
                "collect return dates until outbound is saved."
            )

        if out_saved.isoformat() != out_d.isoformat():
            return (
                "search_flights outbound_date must match profile flight_outbound_ymd "
                f"({out_saved.isoformat()})."
            )

        if ret_d is None:
            return (
                "Round trip: add return_date after the user answers when they fly home. "
                "Save flight_return_ymd first, then call this tool with both dates."
            )

        ret_saved = _parse_iso_date(str(prof.get("flight_return_ymd") or ""))
        if ret_saved is None:
            return (
                "Save flight_return_ymd=YYYY-MM-DD via update_trip_profile from the "
                "user's return answer before searching."
            )

        if ret_saved.isoformat() != ret_d.isoformat():
            return (
                "search_flights return_date must match profile flight_return_ymd "
                f"({ret_saved.isoformat()})."
            )

    cabin_class = CABIN_CLASS_MAP.get(travel_class, "ECONOMY")
    out_str = out_d.isoformat()

    try:
        from_dest = _rapid_get(
            "/api/v1/flights/searchDestination",
            {"query": dep},
        )
        to_dest = _rapid_get(
            "/api/v1/flights/searchDestination",
            {"query": arr},
        )

        from_candidates = from_dest.get("data") or from_dest.get("result") or []
        to_candidates = to_dest.get("data") or to_dest.get("result") or []
        if not from_candidates or not to_candidates:
            return "Could not resolve one or both airports via Booking flight location search."

        from_id = _pick_location_id(from_candidates, dep)
        to_id = _pick_location_id(to_candidates, arr)
        if not from_id or not to_id:
            return "Booking flight location search did not return usable location IDs."

        query = {
            "fromId": from_id,
            "toId": to_id,
            "departDate": out_str,
            "adults": adults,
            "sort": "BEST",
            "cabinClass": cabin_class,
            "currency_code": "USD",
            "pageNo": 1,
        }
        if ret_d is not None:
            query["returnDate"] = ret_d.isoformat()

        data = _rapid_get("/api/v1/flights/searchFlights", query)
    except requests.exceptions.Timeout:
        return "Flight search timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"Flight search failed: {e}"

    if isinstance(data.get("message"), str) and data.get("status") is False:
        return f"Flight search error: {data.get('message')}"

    raw_offers = (
        ((data.get("data") or {}).get("flightOffers"))
        or ((data.get("data") or {}).get("flights"))
        or (data.get("data") or {}).get("results")
        or data.get("result")
        or []
    )
    offers = [
        _coerce_offer(o, dep, arr)
        for o in raw_offers
        if isinstance(o, dict)
    ]
    offers = [o for o in offers if o.get("price", 0) < 9_999_999]
    # Provider often returns duplicate rows with different tokens.
    deduped: list[dict] = []
    seen_keys: set[tuple] = set()
    for o in offers:
        k = _offer_dedupe_key(o)
        if k in seen_keys:
            continue
        seen_keys.add(k)
        deduped.append(o)
    offers = deduped
    if not offers:
        return "No flights found for the given route and dates."

    # Best overall = balance of price and total travel time.
    prices = [float(o.get("price_value") or 9_999_999.0) for o in offers]
    mins = [int(o.get("duration_minutes") or 9_999_999) for o in offers]
    min_price, max_price = min(prices), max(prices)
    min_mins, max_mins = min(mins), max(mins)
    top_offers = sorted(
        offers,
        key=lambda o: _offer_score(o, min_price, max_price, min_mins, max_mins),
    )[:5]

    class_names = {1: "Economy", 2: "Premium Economy", 3: "Business", 4: "First"}
    trip_label = "Round Trip" if ret_d is not None else "One Way"
    currency = top_offers[0].get("currency", "USD")

    date_line = f"Date: {out_str}" + (
        f" → {ret_d.isoformat()}" if ret_d is not None else ""
    )
    header = (
        f"\nFlights: {dep} → {arr}\n"
        f"{date_line}\n"
        f"{trip_label} | {class_names.get(travel_class, 'Economy')} | "
        f"{adults} passenger(s) | Prices in {currency}\n"
    )
    options = "\n\n".join(_format_offer(o, i) for i, o in enumerate(top_offers, 1))

    cards = [
        {
            "airline": o.get("airline"),
            "airline_logo": o.get("airline_logo"),
            "departure": o.get("departure"),
            "arrival": o.get("arrival"),
            "duration": o.get("duration"),
            "stops": o.get("stops", 0),
            "price": o.get("price", 0),
            "url": o.get("url") or (
                f"https://www.google.com/travel/flights?q=Flights+from+{dep}+to+{arr}+on+{out_str}"
            ),
        }
        for o in top_offers
    ]
    label_suffix = (
        f" · {out_str} ⇄ {ret_d.isoformat()}" if ret_d is not None else f" · {out_str}"
    )
    cards_payload = {
        "kind": "flights",
        "label": f"{dep} → {arr}{label_suffix}",
        "cards": cards,
    }

    result = header + "\n" + options
    if cards:
        result += f"\n\n__WAYFARER_CARDS__:{json.dumps(cards_payload, separators=(',', ':'))}"
    return result
