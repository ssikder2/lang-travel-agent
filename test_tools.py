"""
Unit tests for Wayfarer tools and profile module.

All external API calls (Duffel, SerpApi) are mocked so these tests
never make real network requests or incur API costs.

Run with:
    pytest test_tools.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# tools/profile.py
# ---------------------------------------------------------------------------

class TestProfile:
    def setup_method(self):
        """Reset profile state before each test."""
        from tools.profile import reset_profile, set_session
        set_session("test-session")
        reset_profile("test-session")

    def test_update_and_format(self):
        from tools.profile import update_trip_profile, format_profile
        update_trip_profile.invoke({"destinations": "Tokyo", "travel_dates": "June 2026"})
        profile_text = format_profile()
        assert "Tokyo" in profile_text
        assert "June 2026" in profile_text

    def test_cannot_save_return_ymd_before_outbound(self):
        from tools.profile import update_trip_profile
        result = update_trip_profile.invoke({"flight_return_ymd": "2026-06-20"})
        assert "before flight_outbound" in result.lower()

    def test_can_save_outbound_then_return(self):
        from tools.profile import update_trip_profile, format_profile
        assert "Profile updated" in update_trip_profile.invoke(
            {"flight_outbound_ymd": "2026-06-10"}
        )
        assert "Profile updated" in update_trip_profile.invoke(
            {"flight_return_ymd": "2026-06-20"}
        )
        text = format_profile()
        assert "2026-06-10" in text
        assert "2026-06-20" in text

    def test_can_save_both_ymd_in_one_update(self):
        from tools.profile import update_trip_profile, format_profile
        r = update_trip_profile.invoke({
            "flight_outbound_ymd": "2026-06-10",
            "flight_return_ymd": "2026-06-24",
        })
        assert "Profile updated" in r
        assert "2026-06-10" in format_profile()

    def test_flight_departure_persists_and_formats(self):
        from tools.profile import update_trip_profile, format_profile
        update_trip_profile.invoke({"flight_departure": "Los Angeles (LAX)"})
        text = format_profile()
        assert "LAX" in text or "Los Angeles" in text

    def test_empty_profile_returns_empty_string(self):
        from tools.profile import format_profile
        assert format_profile() == ""

    def test_partial_update_preserves_existing_fields(self):
        from tools.profile import update_trip_profile, format_profile
        update_trip_profile.invoke({"destinations": "Paris"})
        update_trip_profile.invoke({"travel_style": "luxury"})
        text = format_profile()
        assert "Paris" in text
        assert "luxury" in text

    def test_session_isolation(self):
        """Two sessions must not share profile data."""
        from tools.profile import update_trip_profile, format_profile, set_session, reset_profile

        set_session("session-a")
        reset_profile("session-a")
        update_trip_profile.invoke({"destinations": "Rome"})

        set_session("session-b")
        reset_profile("session-b")
        # session-b should have no profile
        assert format_profile() == ""

        # Switch back: session-a data should still be there
        set_session("session-a")
        assert "Rome" in format_profile()

    def test_reset_clears_specific_session(self):
        from tools.profile import update_trip_profile, format_profile, reset_profile
        update_trip_profile.invoke({"destinations": "Bali"})
        reset_profile("test-session")
        assert format_profile() == ""

    def test_no_fields_provided(self):
        from tools.profile import update_trip_profile
        result = update_trip_profile.invoke({})
        assert "No fields provided" in result


# ---------------------------------------------------------------------------
# tools/flights.py helpers (pure functions, no API call)
# ---------------------------------------------------------------------------

class TestFlightHelpers:
    def test_parse_iso_duration_hours_minutes(self):
        from tools.flights import _parse_iso_duration
        assert _parse_iso_duration("PT14H30M") == "14h 30m"

    def test_parse_iso_duration_days(self):
        from tools.flights import _parse_iso_duration
        assert _parse_iso_duration("P1DT7H17M") == "31h 17m"

    def test_parse_iso_duration_hours_only(self):
        from tools.flights import _parse_iso_duration
        assert _parse_iso_duration("PT6H") == "6h"

    def test_fmt_time(self):
        from tools.flights import _fmt_time
        assert _fmt_time("2026-06-15T14:35:00Z") == "14:35"

    def test_fmt_time_short_string(self):
        from tools.flights import _fmt_time
        # A string shorter than 16 chars returns an empty slice, not the original
        assert _fmt_time("bad") == ""

    def test_fmt_time_none(self):
        from tools.flights import _fmt_time
        assert _fmt_time(None) == ""

    def test_price_float(self):
        from tools.flights import _price_float
        assert _price_float({"price_value": "299.50"}) == pytest.approx(299.50)

    def test_price_float_fallback(self):
        from tools.flights import _price_float
        assert _price_float({}) == 9_999_999.0


class TestSearchFlights:
    """Tests for Booking RapidAPI flight search integration logic."""

    def setup_method(self):
        from tools.profile import reset_profile, set_session, update_trip_profile

        sid = "unit-test-search-flights"
        reset_profile(sid)
        set_session(sid)
        update_trip_profile.invoke({"flight_trip_type": "one_way"})

    def _dest_response(self, code: str):
        return {"data": [{"id": f"{code}.AIRPORT", "code": code}]}

    def _flight_item(self, price: str, dep_code="JFK", arr_code="CDG", airline="Air France"):
        return {
            "price": f"USD {price}",
            "currency": "USD",
            "airline": airline,
            "stops": 0,
            "duration": "PT7H30M",
            "departureTime": "2026-06-15T10:00:00Z",
            "arrivalTime": "2026-06-15T17:30:00Z",
            "from": dep_code,
            "to": arr_code,
            "url": "https://example.com/f",
        }

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_happy_path_returns_text_and_cards(self, mock_get):
        from tools.flights import search_flights

        r1 = MagicMock(); r1.raise_for_status.return_value = None; r1.json.return_value = self._dest_response("JFK")
        r2 = MagicMock(); r2.raise_for_status.return_value = None; r2.json.return_value = self._dest_response("CDG")
        r3 = MagicMock(); r3.raise_for_status.return_value = None; r3.json.return_value = {
            "data": {"flightOffers": [self._flight_item("450"), self._flight_item("520")]}
        }
        mock_get.side_effect = [r1, r2, r3]

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "CDG",
            "outbound_date": "2026-06-15",
        })

        assert "JFK" in result
        assert "CDG" in result
        assert "__WAYFARER_CARDS__" in result
        payload = json.loads(__import__("re").search(r"__WAYFARER_CARDS__:(\{.+\})", result).group(1))
        assert payload["kind"] == "flights"
        assert len(payload["cards"]) == 2

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_sorted_cheapest_first(self, mock_get):
        from tools.flights import search_flights

        r1 = MagicMock(); r1.raise_for_status.return_value = None; r1.json.return_value = self._dest_response("JFK")
        r2 = MagicMock(); r2.raise_for_status.return_value = None; r2.json.return_value = self._dest_response("NRT")
        r3 = MagicMock(); r3.raise_for_status.return_value = None; r3.json.return_value = {
            "data": {"flightOffers": [self._flight_item("900"), self._flight_item("300"), self._flight_item("600")]}
        }
        mock_get.side_effect = [r1, r2, r3]

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "NRT",
            "outbound_date": "2026-07-01",
        })
        assert result.index("USD 300") < result.index("USD 600")

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_dedupes_identical_offers(self, mock_get):
        from tools.flights import search_flights
        r1 = MagicMock(); r1.raise_for_status.return_value = None; r1.json.return_value = self._dest_response("LAX")
        r2 = MagicMock(); r2.raise_for_status.return_value = None; r2.json.return_value = self._dest_response("HND")
        dup = self._flight_item("1614", "LAX", "HND", "American Airlines")
        r3 = MagicMock(); r3.raise_for_status.return_value = None; r3.json.return_value = {
            "data": {"flightOffers": [dup, dict(dup), dict(dup)]}
        }
        mock_get.side_effect = [r1, r2, r3]
        result = search_flights.invoke({
            "departure_id": "LAX",
            "arrival_id": "HND",
            "outbound_date": "2026-06-14",
        })
        payload = json.loads(__import__("re").search(r"__WAYFARER_CARDS__:(\{.+\})", result).group(1))
        assert len(payload["cards"]) == 1

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_no_offers_returns_friendly_message(self, mock_get):
        from tools.flights import search_flights
        r1 = MagicMock(); r1.raise_for_status.return_value = None; r1.json.return_value = self._dest_response("JFK")
        r2 = MagicMock(); r2.raise_for_status.return_value = None; r2.json.return_value = self._dest_response("CDG")
        r3 = MagicMock(); r3.raise_for_status.return_value = None; r3.json.return_value = {"data": {"flightOffers": []}}
        r4 = MagicMock(); r4.raise_for_status.return_value = None; r4.json.return_value = {"data": {"flightOffers": []}}
        mock_get.side_effect = [r1, r2, r3, r4]
        result = search_flights.invoke({"departure_id": "JFK", "arrival_id": "CDG", "outbound_date": "2026-06-15"})
        assert "No flights found" in result

    @patch("tools.flights._rapid_headers", return_value=None)
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key(self, _mock_headers):
        from tools.flights import search_flights
        result = search_flights.invoke({"departure_id": "JFK", "arrival_id": "CDG", "outbound_date": "2026-06-15"})
        assert "X-RAPIDAPI-KEY" in result

    @patch("tools.flights._today")
    def test_rejects_today_without_explicit_flag(self, mock_today):
        from datetime import date
        from tools.flights import search_flights

        mock_today.return_value = date(2026, 5, 6)
        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "HND",
            "outbound_date": "2026-05-06",
        })

        assert "today" in result.lower()
        assert "Cannot search" in result or "explicitly" in result

    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    @patch("tools.flights.requests.get")
    @patch("tools.flights._today")
    def test_allows_today_when_flag_set(self, mock_today, mock_get):
        from datetime import date
        from tools.flights import search_flights

        mock_today.return_value = date(2026, 5, 6)
        r1 = MagicMock(); r1.raise_for_status.return_value = None; r1.json.return_value = self._dest_response("JFK")
        r2 = MagicMock(); r2.raise_for_status.return_value = None; r2.json.return_value = self._dest_response("HND")
        r3 = MagicMock(); r3.raise_for_status.return_value = None; r3.json.return_value = {"data": {"flightOffers": [self._flight_item("400", "JFK", "HND")]}}
        mock_get.side_effect = [r1, r2, r3]

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "HND",
            "outbound_date": "2026-05-06",
            "use_today_as_outbound": True,
        })

        assert "JFK" in result

    def test_rejects_bad_iata_codes(self):
        from tools.flights import search_flights

        result = search_flights.invoke({
            "departure_id": "JF",
            "arrival_id": "HND",
            "outbound_date": "2026-06-15",
        })
        assert "Invalid airport" in result

    def test_rejects_return_before_outbound(self):
        from tools.profile import update_trip_profile
        from tools.flights import search_flights

        update_trip_profile.invoke({"flight_trip_type": "round_trip"})
        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "HND",
            "outbound_date": "2026-06-20",
            "return_date": "2026-06-10",
        })
        assert "return_date must be on or after" in result

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_api_error_returns_message(self, mock_get):
        from tools.flights import search_flights
        import requests as req

        mock_get.side_effect = req.exceptions.Timeout()
        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "CDG",
            "outbound_date": "2026-06-15",
        })
        assert "timed out" in result.lower()

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_profile_round_trip_skips_api_without_return(self, mock_get):
        from tools.profile import set_session, reset_profile, update_trip_profile
        from tools.flights import search_flights

        sid = "profile-rt-no-return"
        reset_profile(sid)
        set_session(sid)
        update_trip_profile.invoke({
            "flight_trip_type": "round_trip",
            "flight_outbound_ymd": "2026-06-15",
        })

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "CDG",
            "outbound_date": "2026-06-15",
        })

        assert "return_date" in result.lower() or "flight_return_ymd" in result.lower()
        mock_get.assert_not_called()

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_profile_round_trip_calls_api_when_return_present(self, mock_get):
        from tools.profile import set_session, reset_profile, update_trip_profile
        from tools.flights import search_flights

        sid = "profile-rt-with-return"
        reset_profile(sid)
        set_session(sid)
        update_trip_profile.invoke({
            "flight_trip_type": "round_trip",
            "flight_outbound_ymd": "2026-06-15",
            "flight_return_ymd": "2026-06-25",
        })

        r1 = MagicMock(); r1.raise_for_status.return_value = None; r1.json.return_value = self._dest_response("JFK")
        r2 = MagicMock(); r2.raise_for_status.return_value = None; r2.json.return_value = self._dest_response("CDG")
        r3 = MagicMock(); r3.raise_for_status.return_value = None; r3.json.return_value = {
            "data": {"flightOffers": [self._flight_item("450", "JFK", "CDG")]}
        }
        mock_get.side_effect = [r1, r2, r3]

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "CDG",
            "outbound_date": "2026-06-15",
            "return_date": "2026-06-25",
        })
        assert mock_get.call_count == 3
        assert "__WAYFARER_CARDS__" in result

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_round_trip_blocks_when_return_ymd_missing_from_profile(self, mock_get):
        from tools.profile import set_session, reset_profile, update_trip_profile
        from tools.flights import search_flights

        sid = "profile-rt-missing-ret-ymd"
        reset_profile(sid)
        set_session(sid)
        update_trip_profile.invoke({
            "flight_trip_type": "round_trip",
            "flight_outbound_ymd": "2026-06-15",
        })

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "CDG",
            "outbound_date": "2026-06-15",
            "return_date": "2026-06-25",
        })
        assert "flight_return_ymd" in result.lower()
        mock_get.assert_not_called()

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_blocked_without_saved_trip_direction(self, mock_get):
        from tools.profile import reset_profile, set_session
        from tools.flights import search_flights

        sid = "flight-no-trip-pref"
        reset_profile(sid)
        set_session(sid)

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "CDG",
            "outbound_date": "2026-06-15",
        })
        assert "trip type is not saved" in result.lower()
        mock_get.assert_not_called()

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_same_day_return_rejected_by_default_round_trip(self, mock_get):
        from tools.profile import update_trip_profile
        from tools.flights import search_flights

        update_trip_profile.invoke({"flight_trip_type": "round_trip"})
        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "HND",
            "outbound_date": "2026-06-14",
            "return_date": "2026-06-14",
        })
        assert "same" in result.lower()
        mock_get.assert_not_called()

    @patch("tools.flights.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_same_day_return_allowed_when_flag_set(self, mock_get):
        from tools.profile import update_trip_profile
        from tools.flights import search_flights

        update_trip_profile.invoke({
            "flight_trip_type": "round_trip",
            "flight_outbound_ymd": "2026-06-14",
            "flight_return_ymd": "2026-06-14",
        })
        r1 = MagicMock(); r1.raise_for_status.return_value = None; r1.json.return_value = self._dest_response("JFK")
        r2 = MagicMock(); r2.raise_for_status.return_value = None; r2.json.return_value = self._dest_response("HND")
        r3 = MagicMock(); r3.raise_for_status.return_value = None; r3.json.return_value = {"data": {"flightOffers": [self._flight_item("400", "JFK", "HND")]}}
        mock_get.side_effect = [r1, r2, r3]

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "HND",
            "outbound_date": "2026-06-14",
            "return_date": "2026-06-14",
            "allow_same_calendar_day_return": True,
        })
        assert mock_get.call_count == 3
        assert "JFK" in result

    def test_one_way_profile_conflicts_if_return_given(self):
        from tools.flights import search_flights

        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "CDG",
            "outbound_date": "2026-06-15",
            "return_date": "2026-06-20",
        })
        assert "one_way" in result


# ---------------------------------------------------------------------------
# tools/hotels.py
# ---------------------------------------------------------------------------

class TestHotelPriceExtraction:
    def test_rate_per_night_lowest(self):
        from tools.hotels import _extract_price
        prop = {"name": "Hotel A", "rate_per_night": {"lowest": "$120", "before_taxes_fees": "$110"}}
        assert _extract_price(prop) == "$120"

    def test_falls_back_to_top_level_price(self):
        from tools.hotels import _extract_price
        prop = {"name": "Hotel B", "price": "95"}
        assert _extract_price(prop) == "95"

    def test_returns_na_when_no_price(self):
        from tools.hotels import _extract_price
        assert _extract_price({"name": "Hotel C"}) == "N/A"


class TestSearchHotels:
    @patch("tools.hotels.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_happy_path(self, mock_get):
        from tools.hotels import search_hotels

        mock_dest = MagicMock()
        mock_dest.raise_for_status.return_value = None
        mock_dest.json.return_value = {"data": [{"dest_id": "20088325", "search_type": "CITY"}]}
        mock_hotels = MagicMock()
        mock_hotels.raise_for_status.return_value = None
        mock_hotels.json.return_value = {
            "data": {"hotels": [
                {"hotel_name": "Grand Hotel", "price": "$200", "class": 5, "review_score": 8.9},
                {"hotel_name": "Budget Inn", "price": "$80", "class": 4, "review_score": 8.1},
            ]}
        }
        mock_get.side_effect = [mock_dest, mock_hotels]

        result = search_hotels.invoke({
            "location": "Tokyo",
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-22",
        })

        assert "Grand Hotel" in result
        assert "Budget Inn" in result
        assert "__WAYFARER_CARDS__" in result

        cards_match = __import__("re").search(r"__WAYFARER_CARDS__:(\{.+\})", result)
        assert cards_match
        payload = json.loads(cards_match.group(1))
        assert payload["kind"] == "hotels"
        assert len(payload["cards"]) == 2
        assert payload["cards"][0]["price_per_night"] == "$200"

    @patch("tools.hotels.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_no_results(self, mock_get):
        from tools.hotels import search_hotels

        mock_dest = MagicMock()
        mock_dest.raise_for_status.return_value = None
        mock_dest.json.return_value = {"data": [{"dest_id": "x", "search_type": "CITY"}]}
        mock_hotels = MagicMock()
        mock_hotels.raise_for_status.return_value = None
        mock_hotels.json.return_value = {"data": {"hotels": []}}
        mock_get.side_effect = [mock_dest, mock_hotels]

        result = search_hotels.invoke({
            "location": "Nowhere",
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-17",
        })
        assert "No hotels found" in result

    @patch("tools.hotels._rapid_headers", return_value=None)
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key(self, _mock_headers):
        from tools.hotels import search_hotels
        result = search_hotels.invoke({
            "location": "Tokyo",
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-22",
        })
        assert "X-RAPIDAPI-KEY" in result

    @patch("tools.hotels.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_rapidapi_happy_path(self, mock_get):
        from tools.hotels import search_hotels

        # destination lookup, then hotel search
        mock_dest = MagicMock()
        mock_dest.json.return_value = {"data": [{"dest_id": "20088325", "search_type": "CITY"}]}
        mock_dest.raise_for_status.return_value = None

        mock_hotels = MagicMock()
        mock_hotels.json.return_value = {
            "data": {
                "hotels": [
                    {
                        "hotel_name": "Imperial Tokyo",
                        "price": "$512",
                        "review_score": 9.1,
                        "review_nr": 1250,
                        "class": 5,
                        "hotel_facilities": ["WiFi", "Pool"],
                        "url": "https://example.com/imperial",
                    }
                ]
            }
        }
        mock_hotels.raise_for_status.return_value = None
        mock_get.side_effect = [mock_dest, mock_hotels]

        result = search_hotels.invoke({
            "location": "Tokyo",
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-22",
            "min_hotel_class": 4.5,
        })
        assert "Imperial Tokyo" in result
        assert "__WAYFARER_CARDS__" in result

    @patch("tools.hotels.requests.get")
    @patch.dict("os.environ", {"X-RAPIDAPI-KEY": "rapid-test"})
    def test_requires_pricing_filter(self, mock_get):
        from tools.hotels import search_hotels

        mock_dest = MagicMock()
        mock_dest.raise_for_status.return_value = None
        mock_dest.json.return_value = {"data": [{"dest_id": "x", "search_type": "CITY"}]}
        mock_hotels = MagicMock()
        mock_hotels.raise_for_status.return_value = None
        mock_hotels.json.return_value = {
            "data": {"hotels": [
                {"hotel_name": "No Price", "class": 5},
                {"hotel_name": "Priced", "price": "$240", "class": 5},
            ]}
        }
        mock_get.side_effect = [mock_dest, mock_hotels]

        result = search_hotels.invoke({
            "location": "Tokyo",
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-18",
            "require_pricing": True,
        })
        assert "Priced" in result
        assert "No Price" not in result


# ---------------------------------------------------------------------------
# tools/itinerary.py and other LLM-delegation tools
# ---------------------------------------------------------------------------

class TestItinerary:
    def test_returns_llm_prompt_with_destination(self):
        from tools.itinerary import plan_itinerary
        result = plan_itinerary.invoke({
            "destination": "Barcelona",
            "num_days": 5,
            "interests": "food, architecture",
        })
        assert "Barcelona" in result
        assert "5" in result
        assert "food" in result.lower()

    def test_moderate_pace_is_default(self):
        from tools.itinerary import plan_itinerary
        result = plan_itinerary.invoke({"destination": "Lisbon", "num_days": 3})
        assert "Moderate" in result or "moderate" in result

    def test_packed_pace(self):
        from tools.itinerary import plan_itinerary
        result = plan_itinerary.invoke({"destination": "Tokyo", "num_days": 7, "pace": "packed"})
        assert "packed" in result.lower() or "5 or more" in result


# ---------------------------------------------------------------------------
# FastAPI endpoints (mocked agent — no LLM call)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """Ensure required env vars exist so server.py can import without errors."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("X-RAPIDAPI-KEY", "test-rapidapi-key")


class TestServerEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from server import app
        return TestClient(app)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_reset(self, client):
        resp = client.post("/api/reset", json={"session_id": "test-abc"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @patch("server.chat_agent")
    @patch("server.resolve_ui_hints")
    def test_chat_done_reply_from_canonical_state(self, mock_resolve, mock_agent, client):
        """Verify /api/chat emits done with canonical reply (no streamed tokens)."""
        from langchain_core.messages import AIMessageChunk, AIMessage
        from tools.profile import set_session, reset_profile

        set_session("stream-test")
        reset_profile("stream-test")

        chunk = AIMessageChunk(content="Hello, traveller!")

        async def fake_astream(*args, **kwargs):
            yield chunk, {"langgraph_node": "agent"}

        async def fake_aget_state(*args, **kwargs):
            state = MagicMock()
            state.values = {"messages": [AIMessage(content="Hello, traveller!")]}
            return state

        mock_agent.astream = fake_astream
        mock_agent.aget_state = fake_aget_state

        from server import UIHints

        async def fake_resolve(raw):
            return "Hello, traveller!", UIHints(
                suggestions=["Find flights", "Book hotel"],
                placeholder="e.g. Tokyo in June",
            )

        mock_resolve.side_effect = fake_resolve

        resp = client.post(
            "/api/chat",
            json={"message": "Hi", "session_id": "stream-test"},
        )

        assert resp.status_code == 200
        body = resp.text

        events = []
        for line in body.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        event_types = [e["type"] for e in events]
        assert "token" not in event_types
        assert "done" in event_types

        done_event = next(e for e in events if e["type"] == "done")
        assert "Hello" in done_event["reply"]
        assert "Find flights" in done_event["suggestions"]
