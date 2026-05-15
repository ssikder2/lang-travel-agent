// Accumulated trip details extracted from the conversation
export interface TripContext {
  destination?: string;
  dates?: string;
  duration?: string;
  travelers?: string;
  style?: string;
  budget?: string;
}

export interface ResolvedResponse {
  response: string;
  suggestions: string[];
  contextUpdate: Partial<TripContext>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function travelersLabel(ctx: TripContext): string {
  const t = ctx.travelers?.toLowerCase() ?? "";
  if (t === "solo") return "you";
  if (t === "couple") return "both of you";
  return "per person";
}

function destinationLabel(ctx: TripContext): string {
  return ctx.destination ?? "your destination";
}

// ---------------------------------------------------------------------------
// Intent matchers — order matters (more specific first)
// ---------------------------------------------------------------------------

interface Rule {
  test: (msg: string) => boolean;
  resolve: (msg: string, ctx: TripContext) => ResolvedResponse;
}

const rules: Rule[] = [
  // ── Destinations ──────────────────────────────────────────────────────────
  {
    test: (m) => /paris|france/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { destination: "Paris" },
      response: "Paris is a wonderful choice! When are you thinking of going?",
      suggestions: ["Next month", "In 2–3 months", "In 6 months", "Flexible on dates"],
    }),
  },
  {
    test: (m) => /tokyo|japan/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { destination: "Tokyo" },
      response:
        "Tokyo is an incredible destination — futuristic and deeply traditional at the same time.\n\nWhen are you thinking of going?",
      suggestions: ["Next month", "In 2–3 months", "Spring (cherry blossom)", "Flexible"],
    }),
  },
  {
    test: (m) => /bali|indonesia/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { destination: "Bali" },
      response:
        "Bali is a great pick — beaches, rice terraces, temples, and incredible food. When are you planning to travel?",
      suggestions: ["Next month", "In 2–3 months", "Dry season (Apr–Oct)", "Flexible"],
    }),
  },
  {
    test: (m) => /southeast asia|se asia/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { destination: "Southeast Asia" },
      response:
        "Southeast Asia is a fantastic choice. Any particular countries in mind, or are you open to a multi-country route?",
      suggestions: ["Thailand & Vietnam", "Indonesia & Malaysia", "Multi-country route", "Not sure yet"],
    }),
  },
  {
    test: (m) => /surprise/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { destination: "TBD" },
      response:
        "I love the spirit! How about this — tell me the kind of experience you're after and I'll suggest destinations that fit.",
      suggestions: ["Beach & relaxation", "Culture & history", "Adventure & outdoors", "Food-focused trip"],
    }),
  },

  // ── Dates ─────────────────────────────────────────────────────────────────
  {
    test: (m) =>
      /next month|2.3 months|3 months|6 months|spring|summer|fall|winter|flexible|cherry blossom|dry season/.test(m),
    resolve: (m, _ctx) => ({
      contextUpdate: { dates: m },
      response: "Got it! And how long are you thinking for the trip?",
      suggestions: ["3–4 days", "5–7 days", "1–2 weeks", "2+ weeks"],
    }),
  },

  // ── Duration ──────────────────────────────────────────────────────────────
  {
    test: (m) => /3.4 days|5.7 days|1.2 weeks|2\+ weeks|weekend|week|two weeks/.test(m),
    resolve: (m, _ctx) => ({
      contextUpdate: { duration: m },
      response: "Perfect. Are you traveling solo or with others?",
      suggestions: ["Solo", "Couple", "Family with kids", "Group of friends"],
    }),
  },

  // ── Travelers ─────────────────────────────────────────────────────────────
  {
    test: (m) => /^solo$|traveling solo|just me/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { travelers: "Solo" },
      response: "Got it — just you. What's your travel style?",
      suggestions: ["Relaxed & slow", "Balanced mix", "Pack as much in as possible", "Flexible"],
    }),
  },
  {
    test: (m) => /couple|partner|spouse|two of us/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { travelers: "Couple" },
      response: "Lovely! A trip for two. What's your travel style as a couple?",
      suggestions: ["Relaxed & romantic", "Balanced mix", "Pack as much in as possible", "Flexible"],
    }),
  },
  {
    test: (m) => /family|kids|children/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { travelers: "Family" },
      response: "Great — a family trip! What's your preferred pace?",
      suggestions: ["Relaxed & kid-friendly", "Balanced mix", "Busy but manageable", "Flexible"],
    }),
  },
  {
    test: (m) => /group|friends/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { travelers: "Group" },
      response: "A group trip — fun! What's the vibe you're going for?",
      suggestions: ["Relaxed & social", "Balanced mix", "Non-stop adventures", "Flexible"],
    }),
  },

  // ── Travel style ──────────────────────────────────────────────────────────
  {
    test: (m) => /relaxed|romantic|slow|balanced|mix|pack|busy|flexible/.test(m),
    resolve: (m, ctx) => ({
      contextUpdate: { style: m },
      response: `And what's your rough daily budget${ctx.travelers?.toLowerCase() === "solo" ? "" : " per person"}?`,
      suggestions: ["Budget (under $80/day)", "Mid-range ($80–200/day)", "Comfort ($200–400/day)", "Luxury ($400+/day)"],
    }),
  },

  // ── Budget ────────────────────────────────────────────────────────────────
  {
    test: (m) => /budget|mid-range|comfort|luxury|per day|\$/.test(m),
    resolve: (m, ctx) => ({
      contextUpdate: { budget: m },
      response: `Perfect — I have everything I need to start planning your trip to ${destinationLabel(ctx)}. What would you like me to work on first?`,
      suggestions: ["Search flights", "Find hotels", "Build a day-by-day itinerary", "Estimate full trip budget"],
    }),
  },

  // ── Flights ───────────────────────────────────────────────────────────────
  {
    test: (m) => /search flights|find flights|flights/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `What cabin class are you looking for${ctx.travelers?.toLowerCase() === "solo" ? "" : " for the group"}?`,
      suggestions: ["Economy", "Premium Economy", "Business", "No preference"],
    }),
  },
  {
    test: (m) => /economy|premium economy|business|no preference/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `On it. I'll pull together flight options from your origin to ${destinationLabel(ctx)}.\n\n*(Live flight search coming once the backend is connected.)*`,
      suggestions: ["Find hotels", "Build the itinerary", "Estimate the budget"],
    }),
  },

  // ── Hotels ────────────────────────────────────────────────────────────────
  {
    test: (m) => /find hotels|hotels|accommodation|hostel|stay/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `What kind of accommodation are you after in ${destinationLabel(ctx)}?`,
      suggestions: ["Budget hostel / guesthouse", "Mid-range hotel", "Boutique hotel", "Luxury resort"],
    }),
  },
  {
    test: (m) => /hostel|guesthouse|mid-range hotel|boutique|resort/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `Noted! I'll find the best ${destinationLabel(ctx)} accommodation options that match.\n\n*(Live hotel search coming once the backend is connected.)*`,
      suggestions: ["Build the itinerary", "Estimate the budget", "Packing list"],
    }),
  },

  // ── Itinerary ─────────────────────────────────────────────────────────────
  {
    test: (m) => /itinerary|day.by.day|schedule|plan/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `What are your main interests for ${destinationLabel(ctx)}?`,
      suggestions: ["Food & local cuisine", "History & culture", "Nature & outdoors", "Art, nightlife & shopping"],
    }),
  },
  {
    test: (m) => /food|history|culture|nature|art|nightlife|outdoors|temples|cuisine|shopping/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `Building your ${ctx.duration ? ctx.duration + " " : ""}itinerary for ${destinationLabel(ctx)} now.\n\n*(Full itinerary generation will be live once the backend is connected.)*`,
      suggestions: ["Estimate the budget", "Packing list", "Travel advisory"],
    }),
  },

  // ── Budget estimate ───────────────────────────────────────────────────────
  {
    test: (m) => /estimate.*budget|full.*budget|trip.*budget|how much/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `Calculating a full breakdown for ${ctx.travelers ? ctx.travelers.toLowerCase() + " traveling to " : ""}${destinationLabel(ctx)}.\n\n*(Real prices from flight and hotel searches will feed into this once the backend is live.)*`,
      suggestions: ["Packing list", "Travel advisory", "Generate full trip report"],
    }),
  },

  // ── Packing ───────────────────────────────────────────────────────────────
  {
    test: (m) => /packing|pack|luggage|bag|suitcase/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `What type of trip is this mainly for ${destinationLabel(ctx)}?`,
      suggestions: ["City break", "Beach holiday", "Hiking / outdoors", "Mix of everything"],
    }),
  },
  {
    test: (m) => /city break|beach|hiking|mix of/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `Your tailored packing list for ${destinationLabel(ctx)} is ready.\n\n*(Destination-specific tips will generate once the backend is connected.)*`,
      suggestions: ["Travel advisory", "Generate full trip report"],
    }),
  },

  // ── Advisory / visa ───────────────────────────────────────────────────────
  {
    test: (m) => /visa|passport|entry|advisory/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `What's your passport nationality? I'll check visa rules for ${destinationLabel(ctx)}.`,
      suggestions: ["US passport", "UK passport", "EU passport", "Other — I'll type it"],
    }),
  },
  {
    test: (m) => /us passport|uk passport|eu passport|other/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `Checking the latest entry and visa requirements for ${destinationLabel(ctx)}.\n\n*(Live advisory data coming once the backend is connected.)*`,
      suggestions: ["Generate full trip report", "Start over"],
    }),
  },

  // ── Report ────────────────────────────────────────────────────────────────
  {
    test: (m) => /report|full trip|summary/.test(m),
    resolve: (_m, ctx) => ({
      contextUpdate: {},
      response: `Generating your complete trip report for ${destinationLabel(ctx)}.\n\n*(The full Markdown report will be produced by the agent once the backend is wired up.)*`,
      suggestions: ["Plan another trip", "Ask something else"],
    }),
  },

  // ── Reset ─────────────────────────────────────────────────────────────────
  {
    test: (m) => /start over|new trip|plan another|another trip/.test(m),
    resolve: (_m, _ctx) => ({
      contextUpdate: { destination: undefined, dates: undefined, duration: undefined, travelers: undefined, style: undefined, budget: undefined },
      response: "Sure! Let's plan something new. Where are you thinking of going?",
      suggestions: ["Tokyo 🇯🇵", "Paris 🇫🇷", "Bali 🌴", "Southeast Asia trip", "Surprise me"],
    }),
  },
];

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

const fallback: ResolvedResponse = {
  response:
    "Happy to help! To point you in the right direction, which destination are you thinking about?",
  suggestions: ["Tokyo 🇯🇵", "Paris 🇫🇷", "Bali 🌴", "Southeast Asia trip", "I'm not sure yet"],
  contextUpdate: {},
};

export function getMockResponse(userMessage: string, ctx: TripContext): ResolvedResponse {
  const lower = userMessage.toLowerCase().trim();

  for (const rule of rules) {
    if (rule.test(lower)) {
      return rule.resolve(lower, ctx);
    }
  }

  return fallback;
}
