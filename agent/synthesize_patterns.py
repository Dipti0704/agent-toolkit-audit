"""Pure aggregation over the final dataset -- no LLM call needed here, this is
exactly the kind of thing a script should do directly rather than asking an agent.
Produces the headline numbers the case-study page leads with.
"""

import json
from collections import Counter, defaultdict

from . import config

# `blocker` is free text -- exact-string counting over it is useless (every
# blocker is phrased slightly differently, so "most common" always shows count=1).
# Bucket by keyword into a small, fixed taxonomy instead. Deliberately still not
# an LLM call: this is a deterministic, auditable heuristic over ~100 short
# strings, matched in priority order (first match wins), falling back to "Other".
BLOCKER_TAXONOMY = [
    ("Admin approval required", ("admin approval", "admin-only", "admin user", "restricted to admin", "org admin")),
    ("Contact sales / partnership required", ("contact sales", "partnership", "partner program", "sales team", "csm")),
    ("Paid plan required for API access", ("paid plan", "upgrade required", "subscription required", "paid tier")),
    ("No public / documented API", ("no public api", "not publicly documented", "undocumented", "no api")),
    ("OAuth consent & credential lifecycle", ("oauth", "connected app", "consent", "token lifecycle", "external client app")),
    ("Agent safety / permissioning for destructive actions", ("destructive", "safety", "permissioning", "irreversible")),
    ("Rate limits / usage quotas", ("rate limit", "quota", "throttl")),
]


def bucket_blocker(text: str) -> str:
    lowered = text.lower()
    for label, keywords in BLOCKER_TAXONOMY:
        if any(kw in lowered for kw in keywords):
            return label
    return "Other"


def load_final() -> list[dict]:
    return json.loads(config.FINAL_PATH.read_text())


def build_patterns(records: list[dict]) -> dict:
    valid = [r for r in records if "error" not in r]
    failed = [r for r in records if "error" in r]

    auth_counter = Counter()
    for r in valid:
        for method in r.get("auth_methods") or ["Unknown"]:
            auth_counter[method] += 1

    self_serve_counter = Counter(r.get("self_serve", "unknown") for r in valid)
    buildability_counter = Counter(r.get("buildability_verdict", "unknown") for r in valid)
    blocker_counter = Counter(bucket_blocker(r["blocker"]) for r in valid if r.get("blocker"))
    mcp_exists_count = sum(1 for r in valid if (r.get("api_surface") or {}).get("mcp_exists"))

    by_category: dict[str, dict] = defaultdict(lambda: {"total": 0, "self_serve": Counter(), "buildability": Counter()})
    for r in valid:
        cat = r.get("category", "Unknown")
        by_category[cat]["total"] += 1
        by_category[cat]["self_serve"][r.get("self_serve", "unknown")] += 1
        by_category[cat]["buildability"][r.get("buildability_verdict", "unknown")] += 1

    category_summary = {}
    for cat, stats in by_category.items():
        total = stats["total"]
        self_serve_count = stats["self_serve"].get("free_self_serve", 0) + stats["self_serve"].get("trial_self_serve", 0)
        unknown_count = stats["self_serve"].get("unknown", 0)
        gated_count = total - self_serve_count - unknown_count
        category_summary[cat] = {
            "total": total,
            "self_serve_pct": round(self_serve_count / total, 2) if total else 0,
            "gated_pct": round(gated_count / total, 2) if total else 0,
            "unknown_pct": round(unknown_count / total, 2) if total else 0,
            "buildable_today_count": stats["buildability"].get("buildable_today", 0),
        }

    easy_wins = [
        r["name"]
        for r in valid
        if r.get("self_serve") == "free_self_serve" and r.get("buildability_verdict") == "buildable_today"
    ]

    # The mirror image of easy wins: gated on credentials, but not otherwise blocked --
    # these are worth a partnership/outreach conversation rather than a dead end.
    GATED_STATES = {"paid_plan_gated", "admin_approval_gated", "partner_contact_sales"}
    needs_outreach = [
        r["name"]
        for r in valid
        if r.get("self_serve") in GATED_STATES and r.get("buildability_verdict") != "blocked"
    ]

    total_valid = len(valid) or 1
    top_auth_name, top_auth_count = auth_counter.most_common(1)[0] if auth_counter else ("Unknown", 0)
    most_gated_category = max(category_summary.items(), key=lambda kv: kv[1]["gated_pct"], default=(None, None))
    top_blocker_name, top_blocker_count = blocker_counter.most_common(1)[0] if blocker_counter else ("Unknown", 0)

    headline_insights = [
        f"{top_auth_name} dominates auth -- {top_auth_count} of {len(valid)} apps support it, "
        "often alongside a second method.",
        f"{len(easy_wins)} apps are free self-serve AND buildable today -- start there, no outreach needed.",
        f"{len(needs_outreach)} more are gated but not blocked -- worth a partnership conversation, not a dead end.",
        f"{mcp_exists_count} of {len(valid)} apps already have a real MCP server -- the rest are the actual opportunity.",
    ]
    if most_gated_category[0]:
        headline_insights.insert(
            2,
            f"{most_gated_category[0]} is the most gated category "
            f"({round(most_gated_category[1]['gated_pct'] * 100)}% of its apps).",
        )

    return {
        "total_apps": len(records),
        "researched_ok": len(valid),
        "failed_outright": len(failed),
        "failed_apps": [r["name"] for r in failed],
        "auth_method_distribution": dict(auth_counter.most_common()),
        "self_serve_distribution": dict(self_serve_counter.most_common()),
        "buildability_distribution": dict(buildability_counter.most_common()),
        "most_common_blockers": blocker_counter.most_common(10),
        "mcp_already_exists_count": mcp_exists_count,
        "category_summary": category_summary,
        "easy_wins": easy_wins,
        "easy_win_count": len(easy_wins),
        "needs_outreach": needs_outreach,
        "needs_outreach_count": len(needs_outreach),
        "headline_insights": headline_insights,
    }


def main():
    records = load_final()
    patterns = build_patterns(records)
    config.PATTERNS_PATH.write_text(json.dumps(patterns, indent=2))
    print(json.dumps(patterns, indent=2))


if __name__ == "__main__":
    main()
