import os
from langchain.tools import tool


@tool
def estimate_budget(
    destination: str,
    num_days: int,
    num_travelers: int = 1,
    travel_style: str = "moderate",
    flight_cost_per_person: float = None,
    hotel_cost_per_night: float = None,
) -> str:
    """Estimate a detailed trip budget broken down by category.

    Call this ONCE per trip — even for multi-city trips, call it once using the
    full destination (e.g. 'Bangkok, Bali, Singapore') and total days combined.
    Never call it separately per city. Call after flights/hotels have been
    searched when possible so real prices can be passed in for accuracy.

    Args:
        destination: The trip destination (e.g. 'Brussels', 'Tokyo').
        num_days: Duration of the trip in days.
        num_travelers: Number of travelers. Defaults to 1.
        travel_style: 'budget', 'moderate' (default), or 'luxury'.
        flight_cost_per_person: Actual round-trip flight cost per person in USD if already known.
            Omit if unknown — the tool will estimate it.
        hotel_cost_per_night: Actual hotel cost per night in USD if already known.
            Omit if unknown — the tool will estimate it.
    """
    known_costs = []
    if flight_cost_per_person:
        known_costs.append(f"- Flights: ${flight_cost_per_person:.0f}/person (actual — use this exact figure)")
    if hotel_cost_per_night:
        known_costs.append(f"- Hotel: ${hotel_cost_per_night:.0f}/night (actual — use this exact figure)")

    known_block = (
        "Real costs already found (use these exactly):\n" + "\n".join(known_costs)
        if known_costs
        else "No real costs provided — estimate all categories based on typical costs for this destination."
    )

    return f"""\
BUDGET REQUEST — please generate this now using your own knowledge:

Destination: {destination}
Duration: {num_days} days
Travelers: {num_travelers}
Travel style: {travel_style.title()}
{known_block}

Generate a detailed budget breakdown using this exact format:

BUDGET BREAKDOWN — {destination} ({num_days} days, {num_travelers} traveler(s), {travel_style.title()} style)

Category            Per Person      Total ({num_travelers} traveler(s))
─────────────────────────────────────────────────────
Flights             $X,XXX          $X,XXX
Accommodation       $X,XXX          $X,XXX
Food & Dining       $XXX            $XXX
Local Transport     $XXX            $XXX
Activities          $XXX            $XXX
Miscellaneous       $XXX            $XXX
─────────────────────────────────────────────────────
TOTAL               $X,XXX          $X,XXX

Local currency equivalent: ~[total in local currency] [currency name]

Assumptions:
- [3-5 key assumptions, e.g. accommodation type, meals per day, etc.]

Tips to save money:
- [2-3 practical tips specific to this destination and travel style]

Rules:
- Use realistic, destination-specific estimates for {destination} — not generic averages.
- Base accommodation on {num_days - 1} nights.
- All numbers should be round figures (no cents).
"""
