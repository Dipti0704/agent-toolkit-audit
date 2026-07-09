"""Pass 2: an independent, blind re-research of every app, then a field-by-field
diff against pass 1. Agreement between two independently-run research passes is
NOT proof of correctness (both can be wrong the same way) -- it's a cheap signal
that catches noisy/inconsistent fields. The real accuracy number comes from the
human spot-check in human_sample.py; this stage exists to (a) catch and correct
obvious pass-1 mistakes before a human ever looks at it, and (b) produce the
"where pass 1 and pass 2 disagreed" list that the case-study page shows honestly.
"""

import json

from . import config
from .log_utils import get_logger
from .pass1_research import run as run_pass

COMPARE_FIELDS = ["self_serve", "buildability_verdict"]
VALID_DISAGREEMENT_TAGS = {*COMPARE_FIELDS, "auth_methods", "api_surface.mcp_exists"}


def _auth_methods_agree(v1, v2) -> bool:
    """Treat overlapping (not necessarily identical) auth-method sets as agreement.

    Exact-set equality was too strict: one pass finding an extra, non-contradictory
    method (e.g. pass 1 says ["OAuth2"], pass 2 says ["OAuth2", "Other"]) inflated
    the disagreement count without reflecting an actual contradiction. Only flag it
    when the two sets share nothing in common -- a real signal that one pass is wrong.
    """
    s1, s2 = set(v1 or []), set(v2 or [])
    if not s1 and not s2:
        return True
    if not s1 or not s2:
        return False
    return bool(s1 & s2)


def diff_record(r1: dict, r2: dict) -> list[str]:
    disagreements = []
    if not _auth_methods_agree(r1.get("auth_methods"), r2.get("auth_methods")):
        disagreements.append("auth_methods")
    for field in COMPARE_FIELDS:
        if r1.get(field) != r2.get(field):
            disagreements.append(field)
    if bool((r1.get("api_surface") or {}).get("mcp_exists")) != bool((r2.get("api_surface") or {}).get("mcp_exists")):
        disagreements.append("api_surface.mcp_exists")
    return disagreements


def _sanitize_disagreements(record: dict, fallback: list[str] | None) -> dict:
    """Never trust a `disagreements` value already sitting on a raw pass record --
    older extractions could hallucinate arbitrary text into that field since it
    used to be part of the model-facing schema. Only our own known tags survive."""
    record = dict(record)
    existing = record.get("disagreements")
    if isinstance(existing, list) and all(tag in VALID_DISAGREEMENT_TAGS for tag in existing):
        record["disagreements"] = existing or fallback
    else:
        record["disagreements"] = fallback
    return record


def reconcile(r1: dict, r2: dict) -> dict:
    """Build the 'final' record: agreement keeps the value; disagreement prefers
    pass 2 (it ran the sharper, self-serve-focused prompt) but is flagged and
    demoted in confidence so it surfaces for human review."""
    if "error" in r1 and "error" in r2:
        return {**r1, "disagreements": ["both_passes_failed"]}
    if "error" in r1:
        return _sanitize_disagreements(r2, ["single_pass_only"])
    if "error" in r2:
        return _sanitize_disagreements(r1, ["single_pass_only"])

    disagreements = diff_record(r1, r2)
    final = dict(r2)
    final["disagreements"] = disagreements or None
    if disagreements:
        final["confidence"] = min(r1.get("confidence", 0.5), r2.get("confidence", 0.5), 0.4)
    else:
        final["confidence"] = max(r1.get("confidence", 0.5), r2.get("confidence", 0.5))
    return final


def reconcile_all(apps: list[dict], pass1: list[dict], pass2: list[dict], logger) -> list[dict]:
    pass1_by_id = {r["id"]: r for r in pass1}
    pass2_by_id = {r["id"]: r for r in pass2}

    final_records = []
    disagreement_count = 0
    field_disagreement_counts: dict[str, int] = {}
    for app in apps:
        r1 = pass1_by_id.get(app["id"], {"id": app["id"], "error": "missing_from_pass1"})
        r2 = pass2_by_id.get(app["id"], {"id": app["id"], "error": "missing_from_pass2"})
        final = reconcile(r1, r2)
        final_records.append(final)
        disagreements = [d for d in (final.get("disagreements") or []) if d in VALID_DISAGREEMENT_TAGS]
        if disagreements:
            disagreement_count += 1
            for field in disagreements:
                field_disagreement_counts[field] = field_disagreement_counts.get(field, 0) + 1

    config.FINAL_PATH.write_text(json.dumps(final_records, indent=2))

    summary = {
        "total_apps": len(apps),
        "apps_with_pass1_pass2_disagreement": disagreement_count,
        "agreement_rate": round(1 - disagreement_count / len(apps), 3),
        "field_disagreement_counts": field_disagreement_counts,
    }
    config.VERIFICATION_DIR.mkdir(exist_ok=True)
    (config.VERIFICATION_DIR / "pass1_vs_pass2_summary.json").write_text(json.dumps(summary, indent=2))
    logger.info("Reconciliation summary: %s", json.dumps(summary))
    return final_records


def main(limit: int | None = None):
    logger = get_logger("verify")
    apps = json.loads(config.APPS_SEED_PATH.read_text())
    if limit:
        apps = apps[:limit]

    if config.PASS1_PATH.exists():
        pass1 = json.loads(config.PASS1_PATH.read_text())
    else:
        logger.warning("pass1.json not found -- running pass 1 first.")
        pass1 = run_pass(apps, pass_number=1, log_name="pass1")

    pass2 = run_pass(apps, pass_number=2, out_path=config.PASS2_PATH, log_name="pass2")
    reconcile_all(apps, pass1, pass2, logger)


def reconcile_only():
    """Recompute data/final.json + the summary from existing pass1.json/pass2.json,
    without re-running any research. Use this after changing diff/reconcile logic."""
    logger = get_logger("reconcile")
    apps = json.loads(config.APPS_SEED_PATH.read_text())
    pass1 = json.loads(config.PASS1_PATH.read_text())
    pass2 = json.loads(config.PASS2_PATH.read_text())
    reconcile_all(apps, pass1, pass2, logger)


if __name__ == "__main__":
    main()
