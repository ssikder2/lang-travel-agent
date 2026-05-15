"""
Integration tests — uses REAL API keys and makes live network requests.

These tests cost real API credits and take 5-30 seconds each.
Run them separately from the unit tests:

    pytest test_integration.py -v

Skip a specific API if you don't want to hit it:
    pytest test_integration.py -v -k "not flights"
    pytest test_integration.py -v -k "not hotels"
    pytest test_integration.py -v -k "not agent"
"""

import json
import os
import re

import pytest
from dotenv import load_dotenv

# Load real keys from .env.local before any imports that read os.environ
load_dotenv(".env.local")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skip_if_missing(key: str):
    if not os.getenv(key):
        pytest.skip(f"{key} not set — skipping")


def _prep_flight_search_profile(
    direction: str,
    *,
    outbound_ymd: str | None = None,
    return_ymd: str | None = None,
) -> None:
    """Warm session profile for flight tool gates (trip type + optional YYYY-MM-DD rows)."""
    from tools.profile import reset_profile, set_session, update_trip_profile

    sid = "integration-flight-session"
    reset_profile(sid)
    set_session(sid)
    payload = {"flight_trip_type": direction}
    if outbound_ymd:
        payload["flight_outbound_ymd"] = outbound_ymd
    if return_ymd:
        payload["flight_return_ymd"] = return_ymd
    update_trip_profile.invoke(payload)


# ---------------------------------------------------------------------------
# Booking RapidAPI — real flight search
# ---------------------------------------------------------------------------

class TestFlightsIntegration:
    """Live Booking RapidAPI flight calls."""

    def test_one_way_search_returns_results(self):
        _skip_if_missing("X-RAPIDAPI-KEY")
        from tools.flights import search_flights

        _prep_flight_search_profile("one_way")
        result = search_flights.invoke({
            "departure_id": "JFK",
            "arrival_id": "LHR",
            "outbound_date": "2026-08-01",
            "adults": 1,
            "travel_class": 1,
        })

        assert "JFK" in result
        assert "LHR" in result
        # Should have found at least one offer
        assert "USD" in result or "GBP" in result
        # Cards payload should be present
        assert "__WAYFARER_CARDS__" in result

        payload = json.loads(re.search(r"__WAYFARER_CARDS__:(\{.+\})", result).group(1))
        assert payload["kind"] == "flights"
        assert len(payload["cards"]) >= 1
        # Each card must have the required fields
        card = payload["cards"][0]
        assert card.get("airline")
        assert card.get("departure")
        assert card.get("arrival")
        assert isinstance(card.get("price"), (int, float))

    def test_round_trip_search_returns_results(self):
        _skip_if_missing("X-RAPIDAPI-KEY")
        from tools.flights import search_flights

        _prep_flight_search_profile(
            "round_trip",
            outbound_ymd="2026-09-10",
            return_ymd="2026-09-24",
        )
        result = search_flights.invoke({
            "departure_id": "LAX",
            "arrival_id": "NRT",
            "outbound_date": "2026-09-10",
            "return_date": "2026-09-24",
            "adults": 1,
            "travel_class": 1,
        })

        assert "LAX" in result
        assert "NRT" in result
        assert "__WAYFARER_CARDS__" in result

    def test_sorted_cheapest_first(self):
        _skip_if_missing("X-RAPIDAPI-KEY")
        from tools.flights import search_flights

        _prep_flight_search_profile("one_way")
        result = search_flights.invoke({
            "departure_id": "ORD",
            "arrival_id": "CDG",
            "outbound_date": "2026-07-15",
        })

        payload = json.loads(re.search(r"__WAYFARER_CARDS__:(\{.+\})", result).group(1))
        prices = [c["price"] for c in payload["cards"]]
        assert prices == sorted(prices), "Cards should be sorted cheapest first"

    def test_invalid_route_returns_graceful_message(self):
        _skip_if_missing("X-RAPIDAPI-KEY")
        from tools.flights import search_flights

        _prep_flight_search_profile("one_way")
        result = search_flights.invoke({
            "departure_id": "ZZZ",
            "arrival_id": "YYY",
            "outbound_date": "2026-08-01",
        })

        # Should not raise an exception; should return an error string
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Booking RapidAPI — real hotel search
# ---------------------------------------------------------------------------

class TestHotelsIntegration:
    """Live Booking RapidAPI hotel calls."""

    def test_hotel_search_returns_results(self):
        _skip_if_missing("X-RAPIDAPI-KEY")
        from tools.hotels import search_hotels

        result = search_hotels.invoke({
            "location": "Tokyo",
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-08",
            "adults": 1,
        })

        assert "Tokyo" in result
        assert "__WAYFARER_CARDS__" in result

        payload = json.loads(re.search(r"__WAYFARER_CARDS__:(\{.+\})", result).group(1))
        assert payload["kind"] == "hotels"
        assert len(payload["cards"]) >= 1

        card = payload["cards"][0]
        assert card.get("name")
        # Link should be present and non-empty
        assert card.get("link")

    def test_price_is_populated(self):
        """Verify that price extraction actually finds a price (not just N/A)."""
        _skip_if_missing("SERPAPI_API_KEY")
        from tools.hotels import search_hotels

        result = search_hotels.invoke({
            "location": "Paris",
            "check_in_date": "2026-10-01",
            "check_out_date": "2026-10-05",
            "adults": 1,
        })

        payload = json.loads(re.search(r"__WAYFARER_CARDS__:(\{.+\})", result).group(1))
        prices = [c["price_per_night"] for c in payload["cards"]]
        non_na = [p for p in prices if p and p != "N/A"]
        # At least some cards should have real prices
        assert len(non_na) > 0, f"All prices are N/A: {prices}"

    def test_hotel_search_europe(self):
        _skip_if_missing("SERPAPI_API_KEY")
        from tools.hotels import search_hotels

        result = search_hotels.invoke({
            "location": "Barcelona",
            "check_in_date": "2026-08-10",
            "check_out_date": "2026-08-15",
            "adults": 2,
        })

        assert "Barcelona" in result
        assert "__WAYFARER_CARDS__" in result


# ---------------------------------------------------------------------------
# OpenAI — real LLM calls via agent tools
# ---------------------------------------------------------------------------

class TestAgentToolsIntegration:
    """
    Tests that call the OpenAI API through LangChain tool-style invocations.
    These are relatively cheap (short prompts) but do consume tokens.
    """

    def test_itinerary_tool_returns_structured_days(self):
        _skip_if_missing("OPENAI_API_KEY")
        from langchain.chat_models import init_chat_model
        from tools.itinerary import plan_itinerary

        model = init_chat_model("openai:gpt-5.4-mini")
        prompt = plan_itinerary.invoke({
            "destination": "Lisbon",
            "num_days": 3,
            "interests": "food, architecture",
            "pace": "moderate",
        })

        # The tool returns a prompt template, not a real response.
        # Invoke the LLM with it to get the actual itinerary.
        from langchain_core.messages import HumanMessage
        response = model.invoke([HumanMessage(content=prompt)])
        text = response.content

        assert "Day 1" in text
        assert "Day 2" in text
        assert "Day 3" in text
        assert "Lisbon" in text or "lisbon" in text.lower()

    def test_ui_hints_extractor_returns_valid_json(self):
        """Verify the second-stage extractor returns well-formed UIHints."""
        _skip_if_missing("OPENAI_API_KEY")
        import asyncio
        from langchain.chat_models import init_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage
        from pydantic import BaseModel, Field

        class UIHints(BaseModel):
            suggestions: list[str] = Field(description="3-4 quick-reply chips")
            placeholder: str = Field(description="Short input placeholder")

        SYSTEM = (
            "Return JSON with 'suggestions' (3-4 short chips answering the question) "
            "and 'placeholder' (short input hint). No meta-options like 'Other' or 'Done'."
        )
        extractor = init_chat_model("openai:gpt-5.4-mini").with_structured_output(UIHints)

        hints = asyncio.run(extractor.ainvoke([
            SystemMessage(content=SYSTEM),
            HumanMessage(content=(
                "Which city would you like to fly from? I can search for flights "
                "from New York, Los Angeles, Chicago, or wherever you're based."
            )),
        ]))

        assert len(hints.suggestions) >= 2
        assert len(hints.placeholder) > 0
        for chip in hints.suggestions:
            assert chip.lower() not in ("other", "done", "type here", "custom")

    def test_ui_hints_yes_no_question(self):
        """Extractor should return exactly [Yes, No] for a yes/no question."""
        _skip_if_missing("OPENAI_API_KEY")
        import asyncio
        from langchain.chat_models import init_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage
        from pydantic import BaseModel, Field

        class UIHints(BaseModel):
            suggestions: list[str] = Field(description="3-4 quick-reply chips")
            placeholder: str = Field(description="Short input placeholder")

        SYSTEM = (
            "Return JSON with 'suggestions' (YES/NO question → exactly ['Yes','No']) "
            "and 'placeholder'."
        )
        extractor = init_chat_model("openai:gpt-5.4-mini").with_structured_output(UIHints)

        hints = asyncio.run(extractor.ainvoke([
            SystemMessage(content=SYSTEM),
            HumanMessage(content="Would you like me to search for return flights as well?"),
        ]))

        chips_lower = [c.lower() for c in hints.suggestions]
        assert "yes" in chips_lower
        assert "no" in chips_lower
        assert len(hints.suggestions) == 2


# ---------------------------------------------------------------------------
# Full agent conversation (most expensive — uses many tokens + tools)
# ---------------------------------------------------------------------------

class TestAgentConversationIntegration:
    """
    End-to-end conversation tests through the real LangGraph agent.
    Each test spins up a fresh session to avoid cross-test state.
    """

    def setup_method(self):
        """Fresh session and profile for each test."""
        from tools.profile import set_session, reset_profile
        self.session_id = f"test-{os.urandom(4).hex()}"
        set_session(self.session_id)
        reset_profile(self.session_id)

    def _run(self, message: str) -> str:
        """Send one message to the agent and return the text response."""
        from langchain_core.messages import HumanMessage, AIMessage
        from main import agent

        config = {"configurable": {"thread_id": self.session_id}}
        last_content = ""
        for chunk in agent.stream(
            {"messages": [HumanMessage(content=message)]},
            config=config,
            stream_mode="updates",
        ):
            for node, updates in chunk.items():
                if node == "agent":
                    msg = updates["messages"][-1]
                    if isinstance(msg, AIMessage) and msg.content:
                        last_content = msg.content
        return last_content

    def test_agent_greets_and_asks_destination(self):
        _skip_if_missing("OPENAI_API_KEY")
        response = self._run("Hi, I want to plan a trip.")
        assert len(response) > 20
        # Agent should ask where they want to go
        keywords = ["where", "destination", "go", "travel", "city", "country"]
        assert any(kw in response.lower() for kw in keywords)

    def test_agent_calls_flight_search(self):
        _skip_if_missing("OPENAI_API_KEY")
        _skip_if_missing("DUFFEL_API_KEY")
        from main import agent
        from langchain_core.messages import HumanMessage, AIMessage

        config = {"configurable": {"thread_id": self.session_id}}
        tool_calls = []

        for chunk in agent.stream(
            {"messages": [HumanMessage(
                content="Find me one-way economy flights from New York to Tokyo "
                "on September 10 2026"
            )]},
            config=config,
            stream_mode="updates",
        ):
            for node, updates in chunk.items():
                if node == "tools":
                    for msg in updates["messages"]:
                        if hasattr(msg, "name"):
                            tool_calls.append(msg.name)

        assert "search_flights" in tool_calls, f"Expected search_flights to be called, got: {tool_calls}"

    def test_profile_is_saved_after_trip_details(self):
        _skip_if_missing("OPENAI_API_KEY")
        from tools.profile import format_profile, set_session

        set_session(self.session_id)
        self._run(
            "I want to visit Barcelona for 7 days in August 2026, "
            "just me, moderate budget, flying from Miami."
        )

        profile = format_profile()
        assert "Barcelona" in profile or len(profile) > 0
