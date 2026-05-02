from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool

load_dotenv(".env.local")


@tool
def search_flights(origin: str, destination: str, departure_date: str, return_date: str = None) -> str:
    """Search for flights between two locations.

    Args:
        origin: Departure city or airport code.
        destination: Arrival city or airport code.
        departure_date: Departure date in YYYY-MM-DD format.
        return_date: Optional return date in YYYY-MM-DD format for round trips.
    """
    return (
        f"[Flight Finder] Searching flights from {origin} to {destination} "
        f"on {departure_date}"
        f"{f', returning {return_date}' if return_date else ' (one-way)'}. "
        f"No real data yet — placeholder results."
    )


@tool
def search_hotels(location: str, check_in: str, check_out: str, guests: int = 1) -> str:
    """Search for hotels at a destination.

    Args:
        location: City or area to search for hotels.
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
        guests: Number of guests.
    """
    return (
        f"[Hotel Finder] Searching hotels in {location} "
        f"from {check_in} to {check_out} for {guests} guest(s). "
        f"No real data yet — placeholder results."
    )


@tool
def plan_itinerary(destination: str, num_days: int, interests: str = None) -> str:
    """Plan a day-by-day itinerary for a destination.

    Args:
        destination: The city or region to plan activities for.
        num_days: Number of days to plan.
        interests: Optional comma-separated list of traveler interests (e.g., culture, food, adventure).
    """
    return (
        f"[Itinerary Planner] Planning a {num_days}-day itinerary for {destination}"
        f"{f' focused on: {interests}' if interests else ''}. "
        f"No real data yet — placeholder results."
    )


@tool
def estimate_budget(destination: str, num_days: int, num_travelers: int = 1, travel_style: str = "moderate") -> str:
    """Estimate the total budget for a trip.

    Args:
        destination: The trip destination.
        num_days: Duration of the trip in days.
        num_travelers: Number of travelers.
        travel_style: Budget level — 'budget', 'moderate', or 'luxury'.
    """
    return (
        f"[Budget Estimator] Estimating budget for {num_travelers} traveler(s) "
        f"spending {num_days} days in {destination} ({travel_style} style). "
        f"No real data yet — placeholder results."
    )

SYSTEM_PROMPT = """\
You are a professional travel planning assistant. You are friendly, approachable, \
and easy to communicate with — like a knowledgeable travel consultant who genuinely \
enjoys helping people plan great trips.

Scope:
You only help with travel-related topics. If a user asks about something unrelated \
to travel planning, politely let them know you're focused on travel and redirect \
the conversation.

Your capabilities:
You help users plan trips by finding flights, finding hotels, building itineraries, \
and estimating budgets. You can handle multi-destination trips — if a user wants to \
visit multiple cities or countries in one trip, coordinate across all legs seamlessly.

How you interact:
- Make smart assumptions for common parameters (e.g., economy class, 1 traveler, \
standard hotel) so users don't face a wall of questions. Always let them know what \
you assumed and offer to adjust if they want something different.
- Be proactive — share helpful tips, travel insights, and suggestions (e.g., \
"December is peak season in Tokyo, so booking early is a good idea"). But always \
prioritize what the user is asking for over unsolicited advice.
- When a user asks for an itinerary, don't jump straight into a full day-by-day \
plan. First share some highlights and notable things about the destination, then ask \
what kinds of experiences they're looking for (culture, food, adventure, relaxation, \
nightlife, etc.). If they're not sure, walk them through a few questions to help \
them figure out what they'd enjoy.

Currency:
Default to USD for all budget estimates and pricing. When presenting costs, also \
mention the equivalent in the local currency of the destination. If the user \
requests a different currency, switch to that.

Tool usage:
You have access to tools for searching flights, searching hotels, planning \
itineraries, and estimating budgets. Use them when the user's request calls for \
real data. Don't fabricate flight numbers, prices, or hotel names — use your tools \
to get actual information.

Conversation style:
- Keep responses well-organized and scannable (use bullet points, short paragraphs).
- Be concise but thorough — don't overwhelm, but don't leave out important details.
- Remember context from earlier in the conversation so users don't have to repeat \
themselves.
"""

tools = [search_flights, search_hotels, plan_itinerary, estimate_budget]

agent = create_agent(
    "openai:gpt-4o-mini",
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
)


WELCOME_MESSAGE = (
    "Hello! I'm your travel planning assistant. I can help you find flights, "
    "book hotels, build itineraries, and estimate budgets for your next trip — "
    "whether it's a quick getaway or a multi-destination adventure.\n\n"
    "Just tell me where you'd like to go, and we'll get started!"
)


def main():
    print(f"\nAgent: {WELCOME_MESSAGE}")
    print("-" * 40)

    history = []

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        history.append({"role": "user", "content": user_input})

        for chunk in agent.stream(
            {"messages": history},
            stream_mode="updates",
        ):
            for node, updates in chunk.items():
                if node == "tools":
                    for msg in updates["messages"]:
                        print(f"  Calling: {msg.name}")
                elif node == "model":
                    msg = updates["messages"][-1]
                    if msg.content:
                        print(f"\nAgent: {msg.content}")
                        history.append({"role": "assistant", "content": msg.content})


if __name__ == "__main__":
    main()
