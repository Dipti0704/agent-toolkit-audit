# Composio App-Research Agent

A research agent that answers, for a list of 100 SaaS apps: what auth it uses, whether a developer
can self-serve credentials or needs to go through a paid/partner gate, how broad its API surface is,
whether an MCP server already exists, and whether it could be an agent toolkit today. Built for the
Composio AI Product Ops Intern take-home.

## Architecture

```
data/apps_seed.json         the 100 apps, seeded from the assignment brief
        |
        v
agent/pass1_research.py     pass 1: wide-net research, ~8x concurrent
        |  (per app: agent/research_agent.py)
        |    1. tool-use loop: OpenAI (gpt-5.4-nano) + Composio's no-auth
        |       COMPOSIO_SEARCH toolkit (web search + fetch-URL-content)
        |       actually reads each app's docs
        |    2. structured-extraction call: turns the research notes into a
        |       validated AppResearch record (OpenAI structured outputs)
        v
data/pass1.json
        |
        v
agent/verify_pass2.py        pass 2: independent, blind re-research of every app
        |                    (fresh session -- no exposure to pass 1's answers),
        |                    then a field-by-field diff against pass 1
        v
data/pass2.json, data/final.json, verification/pass1_vs_pass2_summary.json
        |
        v
agent/human_sample.py         draws a fixed 20-app random sample
agent/compute_accuracy.py     you hand-check the real docs for those 20 apps,
                               fill in human_verdict, then this scores pass1-only
                               accuracy vs. final (pass1+pass2-reconciled) accuracy
        |
        v
agent/synthesize_patterns.py  pure aggregation (auth distribution, self-serve %
                               by category, most common blocker, easy wins) --
                               no LLM call, this is just Counter() over structured data
        v
data/patterns.json  ->  docs/index.html (the case-study deliverable, served via GitHub Pages)
```

**Live page:** https://dipti0704.github.io/agent-toolkit-audit/

**Where a human was needed:** the LLM does the searching, fetching, and structured extraction; a
human is required for (a) the final 20-app ground-truth check against real docs -- LLM-vs-LLM
agreement is not proof of correctness, both passes can be wrong the same way -- and (b) judgment
calls on ambiguous gating language that neither pass could resolve confidently.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in COMPOSIO_API_KEY (app.composio.dev -> Settings -> API Keys)
# and OPENAI_API_KEY (platform.openai.com -> API Keys)
```

No Composio *connected account* is required for the search tools themselves -- `COMPOSIO_SEARCH` is
a Composio-hosted toolkit that needs no OAuth on our side, which is what makes a from-scratch research
agent workable without asking every one of the 100 apps for credentials just to go read its own docs.

## Running it

```bash
python -m agent.cli pass1       # wide-net research across all 100 apps
python -m agent.cli verify      # independent pass 2 + reconciliation -> data/final.json
python -m agent.cli patterns    # cluster stats -> data/patterns.json
python -m agent.cli sample      # draw the 20-app human spot-check sample -> verification/human_sample.json
#   ... hand-fill human_verdict fields in verification/human_sample.json against real docs ...
python -m agent.cli accuracy    # -> verification/accuracy_report.json (pass1-only vs. final accuracy)

# or, everything except the human step in one go:
python -m agent.cli all
```

Cost: roughly 100 apps x 2 passes x ~4 tool round-trips each on `gpt-5.4-nano` (OpenAI's cheapest
tool-calling-capable model, $0.20/$1.25 per million input/output tokens) -- well under a dollar for
the whole run. `RESEARCH_MODEL` in `.env` can be bumped to `gpt-5.4-mini` if nano's extractions look
shaky on trickier apps -- still cheap, noticeably sharper.

## What's honest about this

- If an app defeats the agent outright (docs unreachable, site blocks scraping, genuinely ambiguous),
  that shows up as an `error` entry in `data/pass1.json` / `data/pass2.json` and in the `failed_apps`
  list in `data/patterns.json` -- it is not silently dropped from the dataset.
- Where a paid plan / partnership gate is the correct finding (not a research failure), that's exactly
  what `self_serve` records, with the evidence URL that says so.
- `verification/accuracy_report.json` reports the real, human-checked accuracy on a 20-app sample, split
  by pass1-only vs. pass1+pass2-reconciled, so the improvement from the verification loop is a number,
  not a claim.
