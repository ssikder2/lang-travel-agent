import os
from serpapi import GoogleSearch
from langchain.tools import tool


def _fetch_news(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    """Fetch news headlines for a query, returning a clean list of title/source/date."""
    params = {
        "engine": "google_news",
        "q": query,
        "gl": "us",
        "hl": "en",
        "api_key": api_key,
    }
    try:
        results = GoogleSearch(params).get_dict()
    except Exception:
        return []

    headlines = []
    for item in results.get("news_results", [])[:max_results]:
        # Items can be a direct article or a grouped story with a highlight
        article = item.get("highlight") or item
        title = article.get("title", "").strip()
        source = article.get("source", {}).get("name", "")
        date = article.get("date", "")
        if title and not title.startswith("Top news") and not title.startswith("Latest"):
            headlines.append({"title": title, "source": source, "date": date})
    return headlines


@tool
def get_travel_advisory(
    destination: str,
    origin_country: str = "United States",
    travel_month: str = None,
) -> str:
    """Get comprehensive travel advisory information for a destination.

    ALWAYS call this tool — never answer from memory — when the user asks about:
    visa requirements, entry rules, passport validity, safety, cultural etiquette,
    currency and money, tax-free shopping (VAT refunds), or current news/events
    that could affect travel.

    Do NOT call this for transportation questions (use get_transportation_guide instead).

    Args:
        destination: The destination country or city (e.g. 'Belgium', 'Tokyo', 'Brazil').
        origin_country: The traveler's home country for visa purposes. Defaults to 'United States'.
        travel_month: Month of travel (e.g. 'July') for seasonal advisories. Optional.
    """
    api_key = os.getenv("SERPAPI_API_KEY")

    news_section = ""
    if api_key:
        headlines = _fetch_news(
            f"{destination} travel advisory safety tourists 2026", api_key
        )
        if headlines:
            formatted = "\n".join(
                f"- {h['title']} ({h['source']}, {h['date']})" for h in headlines
            )
            news_section = f"\nCurrent news headlines fetched (include only the ones that are actually relevant and significant for travelers, skip fluff):\n{formatted}\n"
        else:
            news_section = "\nNo live news was fetched — skip the news section or note there's nothing significant to flag.\n"
    else:
        news_section = "\nSERPAPI_API_KEY not set — skip the current news section.\n"

    month_line = f"Travel month: {travel_month}" if travel_month else "Travel month: not specified"

    return f"""\
TRAVEL ADVISORY REQUEST — please generate this now using your knowledge + the news below:

Destination: {destination}
Traveler origin: {origin_country}
{month_line}
{news_section}
Generate a comprehensive travel advisory using this format:

📋 Visa & Entry Requirements
[Visa requirements for {origin_country} citizens traveling to {destination}. Include:
- Whether a visa is required, and if so, how to get one
- Passport validity requirements
- ETIAS/ETA/eVisa if applicable
- Any entry restrictions to be aware of]

💳 Currency & Money
[Practical money info for {destination}:
- Local currency and approximate USD exchange rate
- Whether cards (credit/debit) are widely accepted or cash is preferred
- ATM availability and any fees/tips for withdrawing local currency
- Whether to get cash before arrival or on arrival
- Tipping norms — amounts and situations where it's expected]

💰 Tax-Free Shopping (VAT Refund)
[Explain the VAT/tax-free refund process in {destination} if applicable:
- Minimum spend thresholds
- How to claim at the airport or in-store
- Which stores/signs to look for]

🛡 Safety & Health
[Key safety tips specific to {destination}:
- General safety level and which areas/situations to be careful about
- Common scams targeting tourists
- Any vaccinations or health precautions recommended
- Emergency numbers]

🌍 Cultural Tips & Local Etiquette
[3-5 practical cultural norms travelers should know — things that could cause offense or surprise if ignored]

📰 Current News & Advisories
[Based on the headlines above, flag anything significant — protests, weather events, entry changes, safety incidents. If nothing significant, say "Nothing major to flag for travelers right now." Do NOT fabricate news items.]

💡 Quick Tips
[3-4 practical quick-wins specific to {destination} that most travel guides miss]

Rules:
- Be specific to {destination} — not generic worldwide advice.
- For visa info, be accurate but note that requirements can change and the user should verify with the official embassy or travel.state.gov.
- Keep each section concise and scannable.
"""
