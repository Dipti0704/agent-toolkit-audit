"""Pass 1: wide-net research across all 100 apps, run concurrently.

Failures are recorded, not swallowed -- an app that defeats the agent is itself
a finding (per the assignment: say so, don't hide it).

Writes to out_path incrementally (after every app, not just at the end) so a
stopped/crashed run doesn't lose already-completed work -- this bit us once
already when a rate-limit storm meant the run needed to be interrupted.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config
from .log_utils import get_logger
from .research_agent import research_app


def _research_one(app: dict, pass_number: int) -> dict:
    try:
        result = research_app(app, pass_number=pass_number)
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: one bad app must not kill the run
        return {
            "id": app["id"],
            "name": app["name"],
            "category": app["category"],
            "pass_number": pass_number,
            "error": f"{type(exc).__name__}: {exc}",
        }


def run(apps: list[dict], pass_number: int = 1, out_path=None, log_name: str = "pass1") -> list[dict]:
    out_path = out_path or config.PASS1_PATH
    logger = get_logger(log_name)
    results: dict[int, dict] = {}
    start = time.time()

    logger.info("Starting %s app(s), pass %d, concurrency %d", len(apps), pass_number, config.MAX_CONCURRENCY)

    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENCY) as pool:
        futures = {pool.submit(_research_one, app, pass_number): app for app in apps}
        done = 0
        for future in as_completed(futures):
            app = futures[future]
            record = future.result()
            results[app["id"]] = record
            done += 1
            if "error" in record:
                logger.warning("[%d/%d] %s: ERROR -- %s", done, len(apps), app["name"], record["error"])
            else:
                logger.info("[%d/%d] %s: ok", done, len(apps), app["name"])

            ordered = [results[a["id"]] for a in apps if a["id"] in results]
            out_path.write_text(json.dumps(ordered, indent=2))

    elapsed = time.time() - start
    errors = sum(1 for r in results.values() if "error" in r)
    logger.info("Done in %.0fs. %d/%d apps failed outright.", elapsed, errors, len(apps))
    return [results[a["id"]] for a in apps]


def main():
    apps = json.loads(config.APPS_SEED_PATH.read_text())
    run(apps, pass_number=1)


if __name__ == "__main__":
    main()
