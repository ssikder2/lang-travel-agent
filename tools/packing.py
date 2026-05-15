from langchain.tools import tool


@tool
def suggest_packing_list(
    destination: str,
    travel_month: str,
    num_days: int,
    activities: str = None,
    travel_style: str = "moderate",
    travelers: str = "solo",
) -> str:
    """Generate a smart, context-aware packing list for a trip.

    Call this when the user asks what to pack, or when enough trip context is known
    (destination, dates, and ideally activities from the itinerary).

    Args:
        destination: The trip destination (e.g. 'Brussels', 'Tokyo', 'Costa Rica').
        travel_month: The month of travel (e.g. 'July', 'December').
        num_days: Duration of the trip in days.
        activities: Comma-separated activities planned (e.g. 'museums, hiking, fine dining, beach').
            Pull this from any itinerary already discussed. Use 'general sightseeing' if unknown.
        travel_style: 'budget' (hostels, backpack), 'moderate' (default), or 'luxury' (hotels, dress up).
        travelers: Who is traveling — e.g. 'solo', 'couple', 'family with kids', 'group of friends'.
    """
    activities_line = activities or "general sightseeing and city exploration"

    return f"""\
PACKING LIST REQUEST — please generate this now using your knowledge of the destination, \
season, and planned activities:

Destination: {destination}
Travel month: {travel_month}
Trip length: {num_days} days
Activities: {activities_line}
Travel style: {travel_style.title()}
Travelers: {travelers.title()}

Generate a practical, well-organized packing list using this format:

🌤 Weather & What to Expect
[2-3 sentences on typical {travel_month} weather in {destination} — temperature range, rain, humidity, etc.]

👔 Clothing
- [Item — include quantity where helpful, e.g. "3-4 t-shirts"]
- ...
[Tailor to weather, activities, and travel style. Flag if anything needs to be dress-code appropriate.]

👟 Footwear
- [Item — note why, e.g. "comfortable walking shoes — expect 10k+ steps daily"]
- ...

🧴 Toiletries & Health
- [Essentials only — skip things everyone always packs]
- [Include any destination-specific health items, e.g. mosquito repellent, altitude sickness meds]

🔌 Tech & Gadgets
- [Include correct plug adapter type for {destination}]
- ...

📄 Documents & Money
- [Passport, visas, travel insurance, etc. — flag any specific requirements for {destination}]
- [Currency tips — whether cash or card is preferred in {destination}]

🎒 Destination-Specific Tips
- [2-3 items or tips unique to {destination} that travelers often forget or don't know about]

Rules:
- Be specific and practical — skip obvious items (toothbrush, underwear) unless there's a real reason to call them out.
- Flag anything that needs to be arranged in advance (e.g. visas, vaccinations).
- Keep the tone helpful and conversational, not a wall of bullet points.
- Add a one-line note at the end about checking the weather forecast 5-7 days before departure for any last-minute adjustments.
"""
