"""
Wayfarer tool registry.

All agent-callable tools are importable from this package.
Import the list directly when wiring up the LangGraph agent:

    from tools import ALL_TOOLS
"""

from tools.flights import search_flights
from tools.hotels import search_hotels
from tools.itinerary import plan_itinerary
from tools.budget import estimate_budget
from tools.packing import suggest_packing_list
from tools.advisory import get_travel_advisory
from tools.transportation import get_transportation_guide
from tools.profile import update_trip_profile
from tools.report import generate_trip_report

ALL_TOOLS = [
    search_flights,
    search_hotels,
    plan_itinerary,
    estimate_budget,
    suggest_packing_list,
    get_travel_advisory,
    get_transportation_guide,
    update_trip_profile,
    generate_trip_report,
]

__all__ = [
    "ALL_TOOLS",
    "search_flights",
    "search_hotels",
    "plan_itinerary",
    "estimate_budget",
    "suggest_packing_list",
    "get_travel_advisory",
    "get_transportation_guide",
    "update_trip_profile",
    "generate_trip_report",
]
