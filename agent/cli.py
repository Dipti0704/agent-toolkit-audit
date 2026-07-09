"""Single entry point for the research pipeline.

Usage:
    python -m agent.cli pass1              # wide-net research across all 100 apps
    python -m agent.cli verify             # pass 2 + reconcile -> data/final.json
    python -m agent.cli sample             # draw the 20-app human spot-check sample
    python -m agent.cli accuracy           # score the filled-in human sample
    python -m agent.cli patterns           # compute cluster stats -> data/patterns.json
    python -m agent.cli all                # run pass1 -> verify -> patterns end to end
"""

import argparse
import json

from . import compute_accuracy, human_sample, pass1_research, synthesize_patterns, verify_pass2
from . import config


def cmd_pass1(args):
    apps = json.loads(config.APPS_SEED_PATH.read_text())
    if args.limit:
        apps = apps[: args.limit]
    pass1_research.run(apps, pass_number=1)


def cmd_verify(args):
    verify_pass2.main(limit=args.limit)


def cmd_sample(_args):
    human_sample.main()


def cmd_accuracy(_args):
    compute_accuracy.main()


def cmd_patterns(_args):
    synthesize_patterns.main()


def cmd_all(args):
    cmd_pass1(args)
    cmd_verify(args)
    cmd_patterns(args)
    print("Pipeline complete. Run `python -m agent.cli sample` next, fill in human_verdict by hand, "
          "then `python -m agent.cli accuracy`.")


def main():
    parser = argparse.ArgumentParser(description="Composio app-research pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [
        ("pass1", cmd_pass1),
        ("verify", cmd_verify),
        ("sample", cmd_sample),
        ("accuracy", cmd_accuracy),
        ("patterns", cmd_patterns),
        ("all", cmd_all),
    ]:
        p = sub.add_parser(name)
        p.add_argument("--limit", type=int, default=None, help="only process the first N apps (for smoke-testing)")
        p.set_defaults(func=fn)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
