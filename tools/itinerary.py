import os
from langchain.tools import tool


@tool
def plan_itinerary(
    destination: str,
    num_days: int,
    interests: str = None,
    pace: str = "moderate",
) -> str:
    """Generate a detailed day-by-day travel itinerary for a destination.

    ALWAYS call this tool — never answer from memory — when building a day-by-day
    itinerary. For multi-destination trips, call once per destination.
    Only call once the user has confirmed their interests and preferences.

    Args:
        destination: The city or region to plan activities for (e.g. 'Tokyo', 'Brussels').
        num_days: Number of days in the itinerary.
        interests: Comma-separated traveler interests (e.g. 'food, culture, art, nightlife, nature').
            Use 'general' if the user has no specific preferences.
        pace: Trip pace — 'relaxed' (2-3 activities/day), 'moderate' (3-4, default),
            or 'packed' (5+ activities/day).
    """
    pace_guidance = {
        "relaxed": "2 to 3 activities per day with plenty of downtime and leisure",
        "moderate": "3 to 4 activities per day with a good balance of sightseeing and rest",
        "packed": "5 or more activities per day, maximizing every hour",
    }.get(pace, "3 to 4 activities per day")

    return f"""\
ITINERARY REQUEST — please generate this now using your own knowledge:

Destination: {destination}
Duration: {num_days} days
Interests: {interests or 'general — well-rounded mix'}
Pace: {pace.title()} ({pace_guidance})

Format each day exactly like this:

Day X — [Theme or neighborhood focus]
  Morning: [Specific activity + 1-sentence reason it's worth doing]
  Afternoon: [Specific activity + 1-sentence reason it's worth doing]
  Evening: [Dinner or evening activity + specific local dish or venue recommendation]
  Tip: [One practical tip — best time to visit, booking advice, how to get there, etc.]

Rules:
- Use real, specific place names (landmarks, museums, neighborhoods, restaurants).
- Recommend a local dish or food experience for at least one meal per day.
- Do not add any preamble or closing summary — just the day-by-day plan.
"""
