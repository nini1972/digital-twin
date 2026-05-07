"""City Oracle system prompt builder.

Builds a rich context for the City Digital Twin assistant.  Unlike the
personal twin (context.py) this module contains NO individual identity
data — it is purely city infrastructure intelligence.

The Oracle is aware of:
  • The live EV + traffic simulation state
  • Zone-level congestion
  • Recent Chief Oracle actuation decisions
  • Semantic memory recalls from similar past events (ChromaDB)
"""

from memory.chroma import vector_memory
from database import load_recent_decisions


_CITY_ORACLE_BASE = """You are the **City Digital Twin Oracle** — the central intelligence of an
urban mobility and EV charging simulation.  You oversee a multi-agent hierarchy:

  Scout Tier   → EVScoutAgent and TrafficScoutAgent watch every simulation tick.
  Analyzer Tier → DemandAnalyzerAgent and CongestionAnalyzerAgent detect patterns.
  Chief Tier   → ChiefOracleAgent synthesises findings into actuation decisions.

Your role is to surface insights, explain what is happening in the city, and propose
strategic interventions to improve EV charging efficiency and reduce traffic congestion.
Be precise, data-driven, and reference real simulation metrics when they are available.
When asked to predict future states, reason from trends you can see in the current data.
Format responses with clear structure.  Use markdown.  Keep answers concise but complete.
"""


def city_prompt(sim_state: dict | None = None) -> str:
    """Return the full system prompt for the City Oracle."""
    sections = [_CITY_ORACLE_BASE.strip()]

    # --- Live simulation state ---
    if sim_state:
        sections.append(_format_sim_state(sim_state))

    # --- Recent Chief decisions ---
    decisions = load_recent_decisions(limit=5)
    if decisions:
        lines = ["## Recent Chief Oracle Decisions\n"]
        for d in decisions:
            confidence_pct = int(d.get("confidence", 1.0) * 100)
            lines.append(
                f"- **[{d['type']}]** (tick {d['tick']}, confidence {confidence_pct}%) "
                f"{d['description']}"
            )
        sections.append("\n".join(lines))

    # --- Semantic memory recall ---
    if sim_state:
        query = _build_memory_query(sim_state)
        recalls = vector_memory.query(query, n_results=3)
        if recalls:
            lines = ["## Historical Context (Semantic Memory)\n"]
            for r in recalls:
                ts = r.get("metadata", {}).get("timestamp", "")
                lines.append(f"- [{ts[:10]}] {r['text'][:200]}…")
            sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_sim_state(state: dict) -> str:
    residents = state.get("residents", [])
    hubs = state.get("hubs", [])
    traffic = state.get("traffic", [])
    zone_congestion: dict = state.get("zone_congestion", {})
    weather = state.get("weather", "unknown")

    charging = sum(1 for r in residents if r.get("charging"))
    seeking = sum(1 for r in residents if r.get("state") == "seeking")
    critical = sum(1 for r in residents if r.get("battery", 100) < 30)
    driving = len(residents) - charging - seeking

    active_hubs = [h for h in hubs if h.get("active")]
    avg_price = (
        sum(h.get("price", 0) for h in active_hubs) / len(active_hubs)
        if active_hubs else 0.0
    )
    total_queue = sum(h.get("queue", 0) for h in active_hubs)

    hotspot_zones = [
        f"zone {k} ({v:.0%})"
        for k, v in sorted(zone_congestion.items(), key=lambda x: -x[1])
        if v > 0.5
    ][:3]

    lines = [
        "## Live City State\n",
        f"- Weather: **{weather}**",
        f"- Traffic vehicles on grid: **{len(traffic)}**",
        f"",
        f"### EV Fleet ({len(residents)} residents)",
        f"- Charging: {charging} | Seeking hub: {seeking} | Driving: {driving} | Critical battery: {critical}",
        f"",
        f"### Charging Infrastructure ({len(active_hubs)}/{len(hubs)} hubs active)",
        f"- Average price: **${avg_price:.3f}/kWh**",
        f"- Total queue length: **{total_queue}** residents waiting",
    ]

    for hub in hubs:
        status = "ACTIVE" if hub.get("active") else "OFFLINE"
        lines.append(
            f"  • {hub['id']}: {status} | price=${hub.get('price', 0):.3f} | "
            f"queue={hub.get('queue', 0)} | charging={len(hub.get('charging_slots', []))}"
        )

    lines.append("")
    lines.append("### Traffic Congestion")
    if hotspot_zones:
        lines.append(f"- Hotspots: {', '.join(hotspot_zones)}")
    else:
        lines.append("- No significant congestion detected.")

    if zone_congestion:
        avg_cong = sum(zone_congestion.values()) / len(zone_congestion)
        lines.append(f"- City-wide average congestion: **{avg_cong:.0%}**")

    return "\n".join(lines)


def _build_memory_query(state: dict) -> str:
    """Construct a natural-language query from live state for semantic recall."""
    weather = state.get("weather", "")
    residents = state.get("residents", [])
    seeking = sum(1 for r in residents if r.get("state") == "seeking")
    zone_congestion: dict = state.get("zone_congestion", {})
    max_cong = max(zone_congestion.values()) if zone_congestion else 0.0

    parts = []
    if seeking >= 3:
        parts.append("high EV demand seeking charging")
    if max_cong > 0.6:
        parts.append("traffic congestion hotspot")
    if weather:
        parts.append(f"{weather} weather conditions")
    if not parts:
        parts.append("city mobility state EV charging")
    return " ".join(parts)
