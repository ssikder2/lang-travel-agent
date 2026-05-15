from langchain.tools import tool


@tool
def get_transportation_guide(
    destination: str,
    num_days: int,
    cities: str = None,
    travel_style: str = "moderate",
    travelers: str = "solo",
) -> str:
    """Get a practical local transportation guide for a destination.

    ALWAYS call this tool — never answer from memory — when the user asks:
    how to get around, what transport to use, airport transfers, train vs. flight
    for ground travel, intercity routes, transit passes, or local commuting.
    Call this after the itinerary is set so recommendations match planned stops.

    Args:
        destination: The destination country or primary city (e.g. 'Japan', 'Paris', 'Italy').
        num_days: Total trip length in days.
        cities: Comma-separated list of cities/areas being visited if it's a multi-city trip
            (e.g. 'Tokyo, Kyoto, Osaka'). Leave blank for single-city trips.
        travel_style: 'budget', 'moderate' (default), or 'luxury' — affects recommendations
            (e.g. budget favors transit passes, luxury may favor private transfers).
        travelers: Who is traveling — e.g. 'solo', 'couple', 'family with kids', 'group of 4'.
            Groups sometimes make taxis cheaper than passes.
    """
    cities_line = f"Cities/areas to cover: {cities}" if cities else f"Primary destination: {destination}"
    trip_scope = "multi-city trip" if cities else "single destination trip"

    return f"""\
TRANSPORTATION GUIDE REQUEST — please generate this now using your knowledge of {destination}:

Destination: {destination}
{cities_line}
Trip type: {trip_scope}
Trip length: {num_days} days
Travel style: {travel_style.title()}
Travelers: {travelers.title()}

Generate a practical transportation guide using this format:

✈️ Airport to City
[Best options for getting from the main airport(s) into the city — include:
- Recommended option (train, express rail, shuttle, taxi, rideshare)
- Approximate cost and travel time
- Any tips (e.g. avoid airport taxis in X city, book in advance, etc.)]

🚇 Getting Around the City
[Day-to-day transport within the city/cities:
- Primary modes used by locals and savvy tourists (metro, tram, bus, bike, walking)
- Whether a transit card/pass is worth it and what it's called (e.g. Oyster Card, Navigo, IC Card)
- Approximate cost for a day pass or per-ride
- App recommendations for navigation (Google Maps, Citymapper, local apps)]

🚆 Intercity Travel (if applicable)
[Only include if {cities} is set or if {destination} warrants it:
- Best way to travel between cities (high-speed rail, regional train, bus, domestic flight)
- Whether a rail pass is worth it vs. point-to-point tickets (e.g. JR Pass, Eurail)
- Booking tips — how far in advance, where to book, any discount cards]

🚗 Car Rental
[Is renting a car recommended for {destination}?
- When it makes sense (rural areas, road trips) vs. when to skip it (cities with good transit)
- Driving side, license requirements, toll considerations if relevant
- Keep this brief — only expand if it's genuinely useful for this destination]

🛺 Taxis & Rideshare
[Local taxi/rideshare norms:
- Which apps work (Uber, Grab, Bolt, local alternatives)
- Whether taxis are metered and trustworthy or if rideshare is strongly preferred
- Any known scams or overcharging situations to avoid]

💡 Transportation Tips
[3-4 specific tips for {destination} that save time, money, or hassle — things not obvious from a standard travel guide]

Rules:
- Be specific to {destination} — not generic advice that applies everywhere.
- Include real pass names, app names, and price ballparks where you know them.
- If {travelers} is a group, note whether splitting a taxi/rideshare beats transit passes.
- Keep it practical and scannable.
"""
