import json
import os
import re
from datetime import date, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv(".env.local")

from langchain_core.messages import (
    HumanMessage, SystemMessage, AIMessage, AIMessageChunk, ToolMessage
)
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from main import model, tools, checkpointer, SYSTEM_PROMPT
from tools.profile import format_profile, get_profile, reset_profile, set_session

app = FastAPI(title="Wayfarer Travel Agent API")

# Build origin allowlist from env + sensible defaults.
# ALLOWED_ORIGINS can be a comma-separated list of extra origins
# (e.g. your specific Vercel production URL).
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
_ORIGIN_REGEX = (
    r"http://localhost:\d+"              # any local port
    r"|https://[a-zA-Z0-9\-]+\.vercel\.app"  # all *.vercel.app preview/prod URLs
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_extra_origins or [],
    allow_origin_regex=_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Two-stage UI hints extractor
# ---------------------------------------------------------------------------

class UIHints(BaseModel):
    suggestions: list[str] = Field(
        description="3-4 quick-reply chips that directly answer the question asked"
    )
    placeholder: str = Field(
        description="Short input placeholder hint matching the question asked"
    )

_extractor_llm = init_chat_model("openai:gpt-5.4-mini").with_structured_output(UIHints)

EXTRACTOR_SYSTEM = """\
You generate quick-reply chips and an input placeholder for a travel planning chat UI.

Given the assistant's latest message, return:

suggestions — 3-4 short chips (1-6 words each) that directly answer \
the question asked. Rules:
  • YES/NO question → exactly ["Yes", "No"], nothing else.
  • Question requiring local knowledge (neighbourhood, area, district, \
    activity type) → real named options + "Help me decide" as the last chip.
  • **Dates / departure or return day:** chips must sound **human**, e.g. \
    "June 14th", "Memorial Day weekend", "July 4th week" — **never** raw ISO \
    like 2026-06-01. Vary the **day of month** — do not offer three different \
    months all on the **1st**. When the trip is clearly in the U.S., prefer at \
    least one **holiday-adjacent** chip when it fits the season (Memorial Day, \
    July 4th, Labor Day, Thanksgiving, etc.).
  • Other open questions (city not date, cabin, budget) → 3-4 realistic examples.
  • No question asked (just information) → logical next travel-planning \
    steps, e.g. ["Find hotels", "Plan itinerary", "Estimate budget"].
  • NEVER use: "Other", "Done", "Finish", "Type here", "Custom", \
    "Something else", or any meta-instruction.
  • NEVER mix answers to different questions in the same chip set.

placeholder — one short input hint under 8 words that matches the question \
asked, written as an example, e.g. "e.g. June 15th – June 22nd" or \
"e.g. Shinjuku or Ginza". If no question was asked use \
"ask me anything about your trip…".
"""


async def extract_ui_hints(assistant_message: str) -> UIHints:
    """Call the extractor model to get chips + placeholder for a given message."""
    try:
        result = await _extractor_llm.ainvoke([
            SystemMessage(content=EXTRACTOR_SYSTEM),
            HumanMessage(content=f"Assistant message:\n{assistant_message}"),
        ])
        return result
    except Exception:
        return UIHints(suggestions=[], placeholder="ask me anything about your trip…")


# ---------------------------------------------------------------------------
# Authoritative UI block — parsed from assistant text (same model as the reply)
# ---------------------------------------------------------------------------

WAYFARER_UI_OPEN = "[WAYFARER_UI:"


def _find_json_object_end(s: str, start: int) -> int | None:
    """Return index of the closing `}` for the JSON object starting at start, or None."""
    depth = 0
    in_str = False
    esc = False
    i = start
    if i >= len(s) or s[i] != "{":
        return None
    while i < len(s):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def split_wayfarer_ui(raw: str) -> tuple[str, dict | None]:
    """Remove trailing [WAYFARER_UI:{...}] and return (visible_text, payload or None)."""
    i = raw.rfind(WAYFARER_UI_OPEN)
    if i < 0:
        return raw, None

    j = raw.find("{", i)
    if j < 0:
        return raw, None
    end = _find_json_object_end(raw, j)
    if end is None:
        return raw, None
    tail = raw[end + 1 :].lstrip()
    if not tail.startswith("]"):
        return raw, None

    blob = raw[j : end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return raw, None
    if not isinstance(data, dict):
        return raw, None

    return raw[:i].rstrip(), data


_ROUND_TRIP_OR_ONE_WAY = re.compile(
    r"(?is)(round[-\s]?trip|round trip).{0,80}(one[-\s]?way|one way)"
    r"|(one[-\s]?way|one way).{0,80}(round[-\s]?trip|round trip)"
)

_ISO_DATE_CHIP = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ordinal_suffix(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _date_to_natural(d: date) -> str:
    return f"{d.strftime('%B')} {d.day}{_ordinal_suffix(d.day)}"


def _iso_chip_to_natural(s: str) -> str:
    t = s.strip()
    if not _ISO_DATE_CHIP.match(t):
        return s
    try:
        return _date_to_natural(date.fromisoformat(t))
    except ValueError:
        return s


def _next_saturday(d: date) -> date:
    if d.weekday() == 5:
        return d
    if d.weekday() == 6:
        return d + timedelta(days=6)
    return d + timedelta(days=(5 - d.weekday()))


def _last_monday_of_may(year: int) -> date:
    dd = date(year, 5, 31)
    while dd.weekday() != 0:
        dd -= timedelta(days=1)
    return dd


def _first_monday_of_september(year: int) -> date:
    dd = date(year, 9, 1)
    while dd.weekday() != 0:
        dd += timedelta(days=1)
    return dd


def _smart_date_chip_candidates(today: date) -> list[str]:
    """Varied human-readable ideas (weekends + US long-weekend anchors)."""
    y = today.year
    candidates: list[str] = []

    sat = _next_saturday(today)
    candidates.append(f"{_date_to_natural(sat)} · weekend")

    md_mon = _last_monday_of_may(y)
    md_sat = md_mon - timedelta(days=2)
    if md_sat >= today:
        candidates.append(f"{_date_to_natural(md_sat)} · Memorial Day weekend")

    july4 = date(y, 7, 4)
    if july4 >= today:
        candidates.append(f"{_date_to_natural(july4)} · July 4th week")

    ld_mon = _first_monday_of_september(y)
    ld_sat = ld_mon - timedelta(days=2)
    if ld_sat >= today:
        candidates.append(f"{_date_to_natural(ld_sat)} · Labor Day weekend")

    hop = today + timedelta(weeks=6)
    if hop.day <= 3:
        hop += timedelta(days=7)
    candidates.append(f"{_date_to_natural(hop)} · flexible dates")

    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        key = c.split(" · ", 1)[0].strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
        if len(out) >= 3:
            break

    k = 0
    while len(out) < 3:
        hop2 = today + timedelta(days=21 + k * 14)
        label = _date_to_natural(hop2)
        if label.lower() not in seen:
            seen.add(label.lower())
            out.append(label)
        k += 1
        if k > 12:
            break
    return out[:3]


def _looks_like_lazy_first_of_month(opts: list[str]) -> bool:
    dates: list[date] = []
    for o in opts:
        t = o.strip()
        if not _ISO_DATE_CHIP.match(t):
            return False
        try:
            dates.append(date.fromisoformat(t))
        except ValueError:
            return False
    return len(dates) >= 2 and all(d.day == 1 for d in dates)


def repair_date_chip_quality(visible: str, hints: UIHints) -> UIHints:
    """
    Convert ISO date chips to spoken dates; replace lazy YYYY-MM-01 patterns
    with varied weekend / holiday-adjacent suggestions.
    """
    raw = hints.suggestions
    if not raw:
        return hints
    if _looks_like_lazy_first_of_month(raw):
        new_opts = _smart_date_chip_candidates(date.today())
    else:
        new_opts = [_iso_chip_to_natural(o) for o in raw]
    return UIHints(suggestions=new_opts[:6], placeholder=hints.placeholder)


def repair_yes_no_vs_or_choice(visible_text: str, hints: UIHints) -> UIHints:
    """
    If chips are Yes/No but the assistant asked an 'A or B' style question
    (e.g. round-trip vs one-way), replace with canonical alternatives.
    """
    opts = [x.strip() for x in hints.suggestions]
    if len(opts) != 2:
        return hints
    if {o.lower() for o in opts} != {"yes", "no"}:
        return hints
    tail = visible_text[-600:] if len(visible_text) > 600 else visible_text
    if _ROUND_TRIP_OR_ONE_WAY.search(tail):
        return UIHints(
            suggestions=["Round trip", "One way"],
            placeholder=hints.placeholder or "e.g. round-trip or one-way",
        )
    return hints


async def resolve_ui_hints(raw_assistant: str) -> tuple[str, UIHints]:
    """
    Prefer [WAYFARER_UI:{...}] from the assistant; otherwise call the extractor.
    Returns (visible_text_without_ui_block, hints).
    """
    visible, parsed = split_wayfarer_ui(raw_assistant)
    if parsed:
        options = parsed.get("options") or parsed.get("suggestions")
        ph_raw = parsed.get("placeholder")
        if isinstance(options, list) and options:
            opts = [str(x).strip() for x in options[:6] if str(x).strip()]
            if opts:
                pl = ""
                if isinstance(ph_raw, str) and ph_raw.strip():
                    pl = ph_raw.strip()[:120]
                if not pl:
                    pl = "ask me anything about your trip…"
                hints = UIHints(suggestions=opts, placeholder=pl)
                hints = repair_yes_no_vs_or_choice(visible, hints)
                return visible, repair_date_chip_quality(visible, hints)
    # Fallback extractor (sees only prose, no JSON block)
    fb = await extract_ui_hints(visible) if visible.strip() else UIHints(
        suggestions=[], placeholder="ask me anything about your trip…"
    )
    fb = repair_yes_no_vs_or_choice(visible, fb)
    return visible, repair_date_chip_quality(visible, fb)


# ---------------------------------------------------------------------------
# Chat-UI prompt overlay
# ---------------------------------------------------------------------------

CHAT_UI_ADDENDUM = """
## Chat UI Mode

You are talking to the user through a chat interface. Adjust your behaviour:

- Keep replies SHORT — 2-4 sentences. Only produce longer output when the \
  user explicitly requests it (e.g. "give me the full itinerary", \
  "write the trip report", "show me a budget breakdown").
- ONE QUESTION PER REPLY — this is a hard rule with no exceptions. Never \
  combine two questions using "and", commas, or semicolons. Ask the most \
  critical one and stop. Get the rest in subsequent turns. You may still wrap \
  that single question in friendly, human wording (a short encouraging line or \
  context) so tone stays warm — the rule is **one** interrogative, not **zero** \
  personality.
- Separate distinct thoughts with a blank line so the reply is easy to scan.
- Do not list your capabilities up front. Let the conversation unfold.
- Never echo back what the user just said.
- **Conversation continuity:** The full chat history for this session is in context.
  If you or the user already established a city, area, or dates (e.g. Tokyo, Shinjuku,
  May 6–7), you must **keep** that context on every turn. Never ask “what city”,
  “where should I look”, or list unrelated example cities unless the user is clearly
  starting a **new** trip or comparing destinations. A **short or one-word reply**
  (“Boutique”, “Yes”, “$150”, “Marriott”) is an answer to **your previous question**
  in the **same** trip — **not permission to reopen** the flight checklist (origin,
  RT vs OW, outbound/return) if Confirmed Trip Details already lists departure,
  trip type, and those dates. Treat “yes” after “save this as your preferred flight”
  as agreeing to THAT — thank them (and call `update_trip_profile` → `flights=...`),
  then offer the next step (e.g. hotels or itinerary), **without** re-asking LAX or
  roundtrip.
- If the main destination is known from the thread but missing from **Confirmed Trip
  Details**, call `update_trip_profile(destinations="...")` now. When the user
  refines hotels, update `hotels`, `travel_style`, `interests`, or `special_notes`
  as appropriate.
- If you asked for the user's **departure calendar day** and they answer with only a \
  date, parse it → `flight_outbound_ymd`, then continue the sequence.
- After they answered **when they RETURN** with only a date, parse it → \
  `flight_return_ymd`, then run **search_flights** matching those profile fields.
- When offering **Round trip** vs **One way** chips and the user picks **Round trip**, \
  FIRST call `update_trip_profile` with `flight_trip_type=round_trip` — then ask ONE \
  question for **when they depart (LEAVE)** and save `flight_outbound_ymd`. Only after \
  that, ask ONE question for **when they RETURN** and save `flight_return_ymd`. Do NOT \
  call **search_flights** until both YMD fields exist for round trips.
- Tool guard (**structural**, not prompting): **`update_trip_profile` rejects** saving \
  `flight_return_ymd` before `flight_outbound_ymd`. **search_flights** requires matching \
  `flight_trip_type`, mandatory profile YMD rows for round trips, sane **return_date**, \
  and rejects same-calendar-day outbound/return unless the rare explicit flag applies.
- If the user's **previous** message only answered **origin** (“New York”), this \
  turn must **not** be a flight search unless **flight_trip_type** plus real dates \
  are already confirmed in profile. Ask chips for **Round trip / One way** (and \
  save via `update_trip_profile`), then outbound/return dates as needed — do not \
  silently plug destination or calendar dates taken only from vague thread context.
- Before calling **search_flights**, every required fact must be known (from the \
  user or already in **Confirmed Trip Details**). **Do not re-ask** facts that are \
  already in profile (e.g. `flight_departure`, `flight_trip_type`, \
  `flight_outbound_ymd`, `flight_return_ymd`) just to "double-check" — only ask for \
  what is **missing** or **changed**. Never invent a departure city or use today's \
  date as outbound unless the user asked for today. If they only tapped "Flights", \
  your next reply is ONE question — usually where they are flying from — not a live \
  search; when they answer, save `flight_departure` immediately.
- Before calling search_hotels, gather: (1) neighbourhood/area preference and \
  (2) budget range or hotel style. If unknown, ask about one first. \
  If the user doesn't know the area, offer to plan the itinerary first.
- As soon as hotel inputs are complete (area + budget/style + dates from \
  user/profile), run `search_hotels` immediately in that same turn. Do NOT ask \
  an extra confirmation question ("Want me to search?") — the user's last detail \
  is already the green light to search.
- **Trip report / \"full report\":** If the user already said **yes** to adding \
  transportation, budget, packing, and entry/advisory together, your next completion \
  must **merge** those tool outputs into **one** Markdown document (via \
  `generate_trip_report` guidance and prior ToolMessages). Do **not** restart a \
  per-section carousel (\"Which section first?\", \"Add budget next?\") unless they \
  asked for **only one** slice.

## Quick-reply metadata (required every turn)

End your ENTIRE reply with a single machine-readable line AFTER your prose — \
no text after this line:

[WAYFARER_UI:{"options":["Chip 1","Chip 2"],"placeholder":"short hint"}]

Rules for `options` (2-4 strings, each under 8 words):
  • They MUST be direct answers to the **exact question you asked** in that reply.
  • Polar question ("Do you want…?", "Should I…?") with a yes/no answer \
    → exactly ["Yes","No"].
  • **Never** use Yes/No when you asked the user to choose between two \
    named alternatives (e.g. "round-trip or one-way", "economy or business"). \
    In those cases the chips MUST be those two choices, e.g. \
    ["Round trip","One way"] or ["Economy","Business class"].
  • Local-area / neighbourhood question → real place names plus \
    "Help me decide" as the last chip when appropriate.
  • Open-ended (dates, cities) → 3-4 concrete examples **only if** you genuinely
    need a city/date and none is fixed yet. If the trip city is **already** part of
    this conversation or the profile, chips must relate to **that** place (e.g.
    neighbourhoods, budget bands), never random cities like Paris or New York.
  • **Departure or return DATE chips:** use **spoken English only** — e.g. \
    "June 14th", "Memorial Day weekend", "July 4th week". **Never** put raw ISO \
    dates like 2026-08-01 in `options`. Do **not** use three different months \
    that are all the **1st** of the month. Vary the day; for U.S. trips, include \
    at least one **major-holiday-adjacent** weekend when it fits the calendar.
  • No meta-chips: never "Other", "Type here", "Custom", "Done".

The `placeholder` mirrors the same question (e.g. "e.g. June 12th–June 20th" \
or "e.g. round-trip or one-way").

The user will NOT see this line — it is stripped by the server. Do not mention \
WAYFARER_UI or JSON in your visible prose.
"""


def make_chat_prompt(state):
    """Wraps the CLI system prompt with chat-UI overlay + live trip profile."""
    today = date.today().strftime("%A, %B %d, %Y")
    fresh_prompt = re.sub(
        r"Today's date is .+?\.",
        f"Today's date is {today}.",
        SYSTEM_PROMPT,
    )
    profile = format_profile()
    base = f"{fresh_prompt}\n\n{CHAT_UI_ADDENDUM}"
    if profile:
        system_content = (
            f"{base}\n\n"
            "## Confirmed Trip Details (already established — do not ask again):\n"
            f"{profile}"
        )
    else:
        system_content = base

    return [SystemMessage(content=system_content)] + [
        m for m in state["messages"] if not isinstance(m, SystemMessage)
    ]


chat_agent = create_react_agent(
    model,
    tools=tools,
    checkpointer=checkpointer,
    prompt=make_chat_prompt,
)

# ---------------------------------------------------------------------------
# Cards extractor
# ---------------------------------------------------------------------------

CARDS_PATTERN = re.compile(r"__WAYFARER_CARDS__:(\{.+\})", re.DOTALL)

TOOL_LABELS: dict[str, str] = {
    "search_flights": "Searching for flights",
    "search_hotels": "Looking up hotels",
    "plan_itinerary": "Planning your itinerary",
    "estimate_budget": "Estimating budget",
    "suggest_packing_list": "Building packing list",
    "get_travel_advisory": "Checking travel advisories",
    "get_transportation_guide": "Looking up transportation options",
    "generate_trip_report": "Generating trip report",
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ResetRequest(BaseModel):
    session_id: str = "default"


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    set_session(request.session_id)
    config = {"configurable": {"thread_id": request.session_id}}

    async def generate():
        try:
            # tool call IDs already announced (avoids duplicate tool events for
            # multi-chunk tool-call streams where only the first chunk has the name)
            emitted_tool_ids: set[str] = set()

            async for chunk, metadata in chat_agent.astream(
                {"messages": [HumanMessage(content=request.message)]},
                config=config,
                stream_mode="messages",
            ):
                node = metadata.get("langgraph_node", "")

                if isinstance(chunk, AIMessageChunk) and node == "agent":
                    # ── Detect tool calls being initiated ───────────────────
                    for tc in (chunk.tool_call_chunks or []):
                        tc_id: str = tc.get("id") or ""
                        tc_name: str = tc.get("name") or ""
                        if tc_id and tc_name and tc_id not in emitted_tool_ids:
                            emitted_tool_ids.add(tc_id)
                            if tc_name != "update_trip_profile":
                                label = TOOL_LABELS.get(tc_name, tc_name.replace("_", " ").title())
                                yield sse({"type": "tool", "tool": tc_name, "label": label})

                    # We do NOT stream LLM tokens to the UI. Multiple `agent`
                    # invocations per turn concatenate their chunks; streaming
                    # would glue duplicate replies together. Canonical text comes
                    # from aget_state in the final `reply` payload below.

                elif isinstance(chunk, ToolMessage) and node == "tools":
                    content = chunk.content or ""
                    tool_name = getattr(chunk, "name", "")

                    # Surface profile updates so the user can see memory work.
                    if tool_name == "update_trip_profile":
                        match = re.search(r"\(([^)]+)\)", content)
                        if match:
                            fields = [f.strip() for f in match.group(1).split(",") if f.strip()]
                            if fields:
                                yield sse({"type": "memory", "fields": fields})
                                yield sse({"type": "profile", "profile": get_profile()})
                        continue

                    cards_match = CARDS_PATTERN.search(content)
                    if cards_match:
                        try:
                            card_payload = json.loads(cards_match.group(1))
                            yield sse({"type": "cards", **card_payload})
                        except json.JSONDecodeError:
                            pass

            # ── Get the definitive final message for UI hint extraction ──────
            # aget_state gives the canonical stored AIMessage, which is more
            # reliable than stitching streamed chunks together.
            state = await chat_agent.aget_state(config)
            final_content = ""
            for msg in reversed(state.values.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    final_content = msg.content
                    break

            if final_content:
                visible_reply, hints = await resolve_ui_hints(final_content)
            else:
                visible_reply = ""
                hints = UIHints(suggestions=[], placeholder="ask me anything about your trip…")
            yield sse({
                "type": "done",
                "reply": visible_reply,
                "suggestions": hints.suggestions,
                "placeholder": hints.placeholder,
            })

        except Exception as e:
            yield sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/reset")
async def reset_session(request: ResetRequest):
    reset_profile(request.session_id)
    return {"status": "ok", "session_id": request.session_id}


class SyncProfileRequest(BaseModel):
    session_id: str = "default"
    destinations: str | None = None
    travel_dates: str | None = None
    num_travelers: int | None = None
    travel_style: str | None = None
    flight_departure: str | None = None
    flight_outbound_ymd: str | None = None
    flight_return_ymd: str | None = None
    budget_estimate: str | None = None


@app.post("/api/sync-profile")
async def sync_profile_endpoint(request: SyncProfileRequest):
    """Directly persist snapshot fields entered in the UI without going through the agent."""
    from tools.profile import update_trip_profile
    set_session(request.session_id)
    result = update_trip_profile.func(
        destinations=request.destinations,
        travel_dates=request.travel_dates,
        num_travelers=request.num_travelers,
        travel_style=request.travel_style,
        flight_departure=request.flight_departure,
        flight_outbound_ymd=request.flight_outbound_ymd,
        flight_return_ymd=request.flight_return_ymd,
        budget_estimate=request.budget_estimate,
    )
    return {"status": "ok", "result": result, "profile": get_profile()}


@app.get("/health")
async def health():
    return {"status": "ok"}
