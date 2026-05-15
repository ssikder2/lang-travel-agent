import json
import logging
import os
from datetime import date as date_type
from pathlib import Path

import requests
from langchain.tools import tool

from tools.profile import ensure_destinations_from_hotel_search

logger = logging.getLogger(__name__)

RAPIDAPI_HOST = "booking-com15.p.rapidapi.com"


def _parse_iso_date(s: str) -> date_type | None:
    try:
        return date_type.fromisoformat((s or "").strip())
    except ValueError:
        return None


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
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()


def _hotel_class_number(prop: dict) -> float:
    raw = prop.get("hotel_class")
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _extract_price(prop: dict) -> str:
    """Try every known SerpApi price field in priority order."""
    if os.getenv("DEBUG"):
        price_keys = {k: v for k, v in prop.items()
                      if any(word in k.lower() for word in ("rate", "price", "cost", "fee"))}
        if price_keys:
            logger.debug("[hotel price fields] %s → %s", prop.get("name", ""), price_keys)

    rate = prop.get("rate_per_night", {})
    if isinstance(rate, dict):
        for key in ("lowest", "before_taxes_fees", "extracted_lowest"):
            v = rate.get(key)
            if v and v != "N/A":
                return str(v)
    for key in ("price_per_night", "price", "min_price", "nightly_price"):
        v = prop.get(key)
        if v:
            return str(v)
    return "N/A"


def _coerce_rapid_hotel(item: dict) -> dict:
    """Map Booking.com15 payload to the normalized card/render shape."""
    image_url = (
        item.get("main_photo_url")
        or item.get("max_photo_url")
        or (item.get("property", {}) or {}).get("photoUrls", [None])[0]
    )
    review_score = item.get("review_score") or item.get("reviewScore")
    review_count = item.get("review_nr") or item.get("reviewCount")
    stars = (
        item.get("class")
        or item.get("stars")
        or item.get("property_class")
        or item.get("hotelClass")
    )
    price_text = (
        item.get("price")
        or item.get("min_total_price")
        or (item.get("composite_price_breakdown", {}) or {}).get("all_inclusive_amount")
        or (item.get("price_breakdown", {}) or {}).get("gross_price")
    )

    return {
        "name": item.get("hotel_name") or item.get("name") or item.get("property_name") or "",
        "price_per_night": str(price_text) if price_text else "N/A",
        "total_price": (
            item.get("total_price")
            or (item.get("price_breakdown", {}) or {}).get("all_inclusive_price")
        ),
        "rating": float(review_score) if review_score not in (None, "") else None,
        "reviews": int(review_count) if str(review_count).isdigit() else review_count,
        "free_cancellation": bool(item.get("is_free_cancellable") or item.get("free_cancellation")),
        "amenities": item.get("hotel_facilities", [])[:6] if isinstance(item.get("hotel_facilities"), list) else [],
        "hotel_class": stars,
        "link": item.get("url") or item.get("hotel_url"),
        "image": image_url,
    }


def _search_hotels_rapidapi(location: str, check_in_date: str, check_out_date: str, adults: int) -> list[dict]:
    headers = _rapid_headers()
    if not headers:
        return []

    # 1) destination lookup
    dest_resp = _rapid_get(
        "/api/v1/hotels/searchDestination",
        {"query": location},
    )
    candidates = (
        dest_resp.get("data")
        or dest_resp.get("result")
        or dest_resp.get("destinations")
        or []
    )
    if not candidates:
        return []

    first = candidates[0] if isinstance(candidates, list) else {}
    dest_id = first.get("dest_id") or first.get("destId") or first.get("id")
    search_type = first.get("search_type") or first.get("searchType") or "CITY"
    if not dest_id:
        return []

    # 2) hotel list
    hotels_resp = _rapid_get(
        "/api/v1/hotels/searchHotels",
        {
            "dest_id": dest_id,
            "search_type": search_type,
            "arrival_date": check_in_date,
            "departure_date": check_out_date,
            "adults": adults,
            "room_qty": 1,
            "page_number": 1,
            "currency_code": "USD",
            "languagecode": "en-us",
        },
    )
    items = (
        ((hotels_resp.get("data") or {}).get("hotels"))
        or (hotels_resp.get("data") or {}).get("result")
        or hotels_resp.get("result")
        or []
    )
    if not isinstance(items, list):
        return []

    return [_coerce_rapid_hotel(x) for x in items if isinstance(x, dict)]


def _build_hotel_card(prop: dict) -> dict:
    images = prop.get("images", [])
    return {
        "name": prop.get("name", ""),
        "price_per_night": _extract_price(prop),
        "total_price": (prop.get("total_rate", {}) or {}).get("lowest"),
        "rating": prop.get("overall_rating"),
        "reviews": prop.get("reviews"),
        "free_cancellation": prop.get("free_cancellation", False),
        "amenities": prop.get("amenities", [])[:6],
        "hotel_class": prop.get("hotel_class"),
        "link": prop.get("link"),
        "image": images[0].get("thumbnail") if images else None,
    }


def _format_hotel(prop: dict, index: int) -> str:
    name = prop.get("name", "Unknown")
    prop_type = prop.get("type", "hotel").title()
    description = prop.get("description", "")
    rating = prop.get("overall_rating")
    reviews = prop.get("reviews")
    hotel_class = prop.get("hotel_class", "")
    location_rating = prop.get("location_rating")
    check_in = prop.get("check_in_time", "")
    check_out = prop.get("check_out_time", "")
    free_cancel = prop.get("free_cancellation", False)

    price_str = _extract_price(prop)

    total = prop.get("total_rate", {})
    total_str = total.get("lowest", "")

    amenities = prop.get("amenities", [])

    lines = [f"  {index}. {name}"]

    meta = []
    if hotel_class:
        meta.append(str(hotel_class))
    if prop_type and prop_type != "Hotel":
        meta.append(prop_type)
    if meta:
        lines.append(f"     {' | '.join(meta)}")

    price_line = f"     From {price_str}/night"
    if total_str:
        price_line += f"  (total: {total_str})"
    if free_cancel:
        price_line += "  ✓ Free cancellation"
    lines.append(price_line)

    if rating:
        rating_line = f"     Rating: {rating}/5"
        if reviews:
            rating_line += f" ({reviews:,} reviews)"
        if location_rating:
            rating_line += f" | Location: {location_rating}/5"
        lines.append(rating_line)

    if check_in or check_out:
        lines.append(f"     Check-in: {check_in}  |  Check-out: {check_out}")

    if description:
        lines.append(f"     {description[:120]}{'...' if len(description) > 120 else ''}")

    if amenities:
        lines.append(f"     Amenities: {', '.join(amenities[:6])}")

    return "\n".join(lines)


@tool
def search_hotels(
    location: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 1,
    sort_by: int = 3,
    min_hotel_class: float = 0.0,
    require_pricing: bool = True,
) -> str:
    """Search for real hotels using live provider data.

    Args:
        location: City or destination to search hotels in (e.g. 'Brussels', 'Tokyo', 'New York').
        check_in_date: Check-in date in YYYY-MM-DD format.
        check_out_date: Check-out date in YYYY-MM-DD format.
        adults: Number of adult guests. Defaults to 1.
        sort_by: Sort order for SerpApi — 3=Lowest price, 8=Highest rating, 13=Most reviewed.
        min_hotel_class: Optional star floor (e.g. 4.5 to bias toward 5-star inventory).
        require_pricing: If True, hide entries without a nightly price.
    """
    in_d = _parse_iso_date(check_in_date)
    out_d = _parse_iso_date(check_out_date)
    if not in_d or not out_d:
        return "Hotel dates must be YYYY-MM-DD."
    if out_d <= in_d:
        return "check_out_date must be after check_in_date."

    if not _rapid_headers():
        return "Error: X-RAPIDAPI-KEY is not set."

    try:
        properties = _search_hotels_rapidapi(location, check_in_date, check_out_date, adults)
    except requests.RequestException as e:
        return f"Hotel search failed: {e}"

    used_provider = "rapidapi"

    # Quality guardrails
    if min_hotel_class > 0:
        properties = [p for p in properties if _hotel_class_number(p) >= min_hotel_class]
    if require_pricing:
        properties = [p for p in properties if _extract_price(p) != "N/A"]
    if not properties:
        return f"No hotels found in {location} for the given dates."

    nights = (out_d - in_d).days

    header_lines = [
        f"\nHotels in {location}",
        f"Dates: {check_in_date} → {check_out_date} ({nights} night{'s' if nights != 1 else ''})"
        f" | {adults} guest(s) | Source: {used_provider}",
    ]
    if min_hotel_class > 0:
        header_lines.append(f"Filtered: hotel class ≥ {min_hotel_class:g}")
    if require_pricing:
        header_lines.append("Filtered: nightly price required")

    header = "\n".join(header_lines) + "\n"
    options = "\n\n".join(
        _format_hotel(p, i) for i, p in enumerate(properties[:5], 1)
    )

    cards = [_build_hotel_card(p) for p in properties[:5]]
    cards_payload = {
        "kind": "hotels",
        "label": f"{location} · {check_in_date} – {check_out_date}",
        "cards": cards,
    }

    result = header + "\n" + options
    if cards:
        ensure_destinations_from_hotel_search(location)
        result += f"\n\n__WAYFARER_CARDS__:{json.dumps(cards_payload, separators=(',', ':'))}"
    return result
