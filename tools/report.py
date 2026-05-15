from langchain.tools import tool

from tools.profile import format_profile


@tool
def generate_trip_report() -> str:
    """Compile instructions — your NEXT assistant message MUST be Markdown for the USER.

    Call after the traveler asked for a trip report, dossier, or “everything compiled”.

    Prerequisites (unless the traveler only wants a partial report):

    BEFORE you send the Markdown to the USER, scan **this conversation’s ToolMessages** for:

    • `estimate_budget`
    • `suggest_packing_list`
    • `get_transportation_guide`
    • `get_travel_advisory`
    • `plan_itinerary`

    If something is requested or implied (e.g. “full practical report”) and ANY of these
    have **never** appeared in-tool in this thread, call the missing ones **that same turn**
    (multiple tools allowed); only then finalize Markdown.

    If the user answered **yes** to adding transport, budget, packing, AND entry/advisory —
    merge **every** populated section in **one reply**. Do NOT ask “which section first?”
    or “shall I add budget next?” — synthesize unless they explicitly asked for a single part.
    """
    profile = format_profile()
    profile_section = (
        f"\n### Confirmed profile (prefer these specifics where they exist):\n{profile}\n"
        if profile
        else "\n### Profile is empty — rely on validated chat context.\n"
    )

    return f"""\
## TRIP REPORT — YOUR NEXT MESSAGE IS THE FINAL MARKDOWN DOCUMENT

You are handing the traveler one polished reference — not a roadmap of future edits.

### Step 1 — Pull content from ToolMessages same thread

Search upward for recent tool outputs matching these names:

- `get_transportation_guide` → **Getting Around**
- `estimate_budget` → **Budget Summary** (reuse numbers/explanations verbatim or tightly summarized — never fabricated)
- `suggest_packing_list` → **Packing List** (reuse categories/items)
- `get_travel_advisory` → **Before You Go**
- `plan_itinerary` → itinerary section
- Flight / hotel details from earlier turns when searches ran (ignore `__WAYFARER_CARDS__` JSON blobs)

### Step 2 — Forbidden placeholder lies

Never write any of:

- \"Budget not yet estimated\"
- \"Packing list not yet generated\"
- \"before you go … not yet added\"
- \"Entry … not yet …\"

if the corresponding tool has **already** returned substantive text in THIS thread above.

When a tool DID run → that section MUST contain real summarized content drawn from its output.

If a tool NEVER ran → **omit** that heading entirely **or** one honest line (“Budget breakdown not requested yet.”).

### Step 3 — Structure (skip empty headings)

Mirror this outline — only headings you can fill honestly:

```markdown
# ✈️ Trip Report: [Destination(s)]
**[Dates] · [travelers + style shorthand]**

## Trip Overview

## ✈️ Flights

## 🏨 Accommodation

## 🗓 Day-by-Day Itinerary

## 🚇 Getting Around

## 💰 Budget Summary

## 🎒 Packing List

## 📋 Before You Go

## 💡 Quick Reference
```

Tone: factual, traveler-facing, Markdown clean.
{profile_section}
"""
