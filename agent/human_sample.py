"""Draws a fixed-seed random sample of apps and writes a fill-in-by-hand template.

A human (you) then opens each app's real docs, fills in `human_verdict`, and
re-runs compute_accuracy.py. This is the ground-truth check the assignment asks
for -- pass1-vs-pass2 agreement is not enough on its own, because both passes
can be confidently wrong the same way.
"""

import json
import random

from . import config

SAMPLE_SIZE = 20
SEED = 42
CHECK_FIELDS = ["auth_methods", "self_serve", "buildability_verdict", "mcp_exists"]


def _claim(record: dict) -> dict:
    return {
        "auth_methods": record.get("auth_methods"),
        "self_serve": record.get("self_serve"),
        "buildability_verdict": record.get("buildability_verdict"),
        "mcp_exists": (record.get("api_surface") or {}).get("mcp_exists"),
    }


def build_sample(apps: list[dict], pass1: list[dict], final: list[dict], sample_size: int = SAMPLE_SIZE) -> list[dict]:
    pass1_by_id = {r["id"]: r for r in pass1}
    final_by_id = {r["id"]: r for r in final}

    rng = random.Random(SEED)
    sampled_apps = rng.sample(apps, k=min(sample_size, len(apps)))

    sample = []
    for app in sorted(sampled_apps, key=lambda a: a["id"]):
        r1 = pass1_by_id.get(app["id"], {})
        rf = final_by_id.get(app["id"], {})
        entry = {
            "id": app["id"],
            "name": app["name"],
            "hint": app["hint"],
            "category": app["category"],
            "pass1_claim": _claim(r1),
            "final_claim": _claim(rf),
            "evidence_urls": [e.get("url") for e in (rf.get("evidence") or [])],
            "human_verdict": {field: None for field in CHECK_FIELDS},
            "human_notes": "",
        }
        sample.append(entry)
    return sample


def main():
    apps = json.loads(config.APPS_SEED_PATH.read_text())
    pass1 = json.loads(config.PASS1_PATH.read_text()) if config.PASS1_PATH.exists() else []
    final = json.loads(config.FINAL_PATH.read_text()) if config.FINAL_PATH.exists() else []

    sample = build_sample(apps, pass1, final)
    config.VERIFICATION_DIR.mkdir(exist_ok=True)
    config.HUMAN_SAMPLE_PATH.write_text(json.dumps(sample, indent=2))
    print(f"Wrote {len(sample)}-app sample to {config.HUMAN_SAMPLE_PATH}")
    print("Fill in human_verdict for each field by hand-checking the real docs, then run:")
    print("  python -m agent.compute_accuracy")


if __name__ == "__main__":
    main()
