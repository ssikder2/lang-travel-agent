import uuid
from main import agent
from tools.profile import reset_profile

SEPARATOR = "=" * 60


def run_conversation(title, turns):
    print(f"\n{SEPARATOR}")
    print(f"TEST: {title}")
    print(SEPARATOR)

    # Each test gets its own isolated thread so memory doesn't bleed between tests
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    reset_profile()

    tools_called = []
    errors = []

    for turn in turns:
        print(f"\n  USER: {turn}")
        try:
            for chunk in agent.stream(
                {"messages": [{"role": "user", "content": turn}]},
                config=config,
                stream_mode="updates",
            ):
                for node, updates in chunk.items():
                    if node == "tools":
                        for msg in updates["messages"]:
                            print(f"    [TOOL]: {msg.name}")
                            tools_called.append(msg.name)
                    elif node == "agent":
                        msg = updates["messages"][-1]
                        if msg.content:
                            preview = msg.content[:400].replace("\n", " ")
                            print(f"    AGENT: {preview}...")
        except Exception as e:
            err = f"ERROR on turn '{turn[:50]}': {e}"
            print(f"    !! {err}")
            errors.append(err)

    print(f"\n  TOOLS CALLED: {tools_called}")
    print(f"  ERRORS: {errors if errors else 'None'}")
    return tools_called, errors


# ── TEST 1: Full single-city flow, Paris ─────────────────────────
run_conversation("Paris 7-day leisure trip — full sequential flow", [
    "I want to go to Paris for 7 days in September, flying from New York.",
    "Can you find me hotels around Le Marais for those dates?",
    "Build me an itinerary — I love art, food, and architecture.",
    "How do I get around Paris?",
    "What is the budget for this whole trip?",
    "What should I pack?",
    "What do I need to know before I go?",
])

# ── TEST 2: Multi-destination Asia trip ──────────────────────────
run_conversation("Multi-destination Asia — Bangkok, Bali, Singapore (14 days)", [
    "Planning a 2-week trip in November: Bangkok (4 days), Bali (6 days), Singapore (4 days). I'm flying from LA.",
    "Find me flights from LA to Bangkok and a return from Singapore.",
    "Suggest hotels in Bali, somewhere near Ubud.",
    "Build a full itinerary for all 3 destinations.",
    "How do I travel between them?",
    "Estimate the full budget for this trip.",
])

# ── TEST 3: Visa-required destination — India ─────────────────────
run_conversation("Visa-required destination — India, 10 days", [
    "I want to visit India for 10 days, focusing on Delhi, Agra, and Jaipur (Golden Triangle).",
    "Do I need a visa? I'm from the US.",
    "Find me flights from Chicago to Delhi.",
    "What should I be aware of safety-wise?",
])

# ── TEST 4: Family trip edge case ─────────────────────────────────
run_conversation("Family with kids — Disney Paris + Loire Valley, 8 days", [
    "Planning a family trip to France, 2 adults and 2 kids (ages 7 and 10). 8 days, flying from Boston.",
    "We want to do Disneyland Paris and also see some castles in the Loire Valley.",
    "Find hotels near Disneyland Paris.",
    "Build an itinerary suitable for kids.",
    "How should we get around with kids?",
    "What should we pack for the kids?",
])

# ── TEST 5: Vague/incomplete user inputs ──────────────────────────
run_conversation("Vague input handling — no dates, no specifics", [
    "I want to go somewhere warm.",
    "Maybe Europe?",
    "Ok let's do Greece.",
    "I don't know how many days yet.",
    "Just show me some flights from Miami.",
])

# ── TEST 6: Budget trip, solo backpacker ──────────────────────────
run_conversation("Budget backpacker — Southeast Asia, 3 weeks", [
    "I'm a solo backpacker on a tight budget, planning 3 weeks in Southeast Asia. Thinking Vietnam, Cambodia, Thailand.",
    "I'm flying from London. Find the cheapest flights.",
    "What's the cheapest way to get around between countries?",
    "Give me a realistic total budget for 3 weeks on a shoestring.",
])

# ── TEST 7: Short weekend trip edge case ──────────────────────────
run_conversation("Short weekend trip — NYC to Montreal, 3 days", [
    "Quick weekend trip from New York to Montreal, just 3 days in July.",
    "Should I fly or take the train?",
    "Find me a central hotel in Old Montreal.",
    "What's fun to do there in summer?",
    "Do I need anything special as a US citizen to enter Canada?",
])

# ── TEST 8: Conversation memory test ─────────────────────────────
run_conversation("Memory continuity — references back to earlier details", [
    "I'm going to Tokyo for 10 days in March, flying from San Francisco.",
    "Find me a hotel in Shinjuku.",
    "Now build an itinerary, I like anime, tech, and street food.",
    "Based on everything we've discussed so far, estimate my total budget.",
    "What do I need to pack for the trip we've been planning?",
])

print(f"\n{SEPARATOR}")
print("ALL TESTS COMPLETE")
print(SEPARATOR)
