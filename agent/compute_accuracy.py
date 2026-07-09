"""Compares the filled-in human sample against pass1-only and final (pass1+pass2
reconciled) claims. This produces the "accuracy moved from a lower first pass to
a higher one" number the assignment asks to see.
"""

import json

from . import config
from .human_sample import CHECK_FIELDS


def _matches(claim, verdict) -> bool | None:
    if verdict is None:
        return None  # not yet filled in by a human
    if isinstance(claim, list):
        return sorted(claim or []) == sorted(verdict or [])
    return claim == verdict


def score(sample: list[dict], claim_key: str) -> dict:
    per_field = {field: {"correct": 0, "total": 0} for field in CHECK_FIELDS}
    for entry in sample:
        claims = entry[claim_key]
        verdicts = entry["human_verdict"]
        for field in CHECK_FIELDS:
            match = _matches(claims.get(field), verdicts.get(field))
            if match is None:
                continue
            per_field[field]["total"] += 1
            if match:
                per_field[field]["correct"] += 1

    total_correct = sum(v["correct"] for v in per_field.values())
    total_checked = sum(v["total"] for v in per_field.values())
    overall = round(total_correct / total_checked, 3) if total_checked else None
    return {
        "overall_accuracy": overall,
        "checked": total_checked,
        "per_field": {
            field: {
                "accuracy": round(v["correct"] / v["total"], 3) if v["total"] else None,
                "correct": v["correct"],
                "total": v["total"],
            }
            for field, v in per_field.items()
        },
    }


def main():
    sample = json.loads(config.HUMAN_SAMPLE_PATH.read_text())

    unfilled = [e["name"] for e in sample if all(v is None for v in e["human_verdict"].values())]
    if unfilled:
        print(f"Warning: {len(unfilled)} apps still have no human_verdict filled in: {unfilled}")

    report = {
        "sample_size": len(sample),
        "pass1_only": score(sample, "pass1_claim"),
        "final_after_verification": score(sample, "final_claim"),
    }
    p1 = report["pass1_only"]["overall_accuracy"]
    pf = report["final_after_verification"]["overall_accuracy"]
    if p1 is not None and pf is not None:
        report["accuracy_delta"] = round(pf - p1, 3)

    config.VERIFICATION_DIR.mkdir(exist_ok=True)
    config.VERIFICATION_REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
