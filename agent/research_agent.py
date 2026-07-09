"""Two-phase per-app research: (1) a free-running tool-use loop that actually
searches/fetches docs, (2) a structured-extraction call that turns the research
notes into a validated AppResearch record.

Splitting these two phases (rather than forcing structured output while tools are
still in play) keeps the tool loop simple and makes the extraction step reusable
for the pass-2 verifier, which re-derives the same fields from an independently
gathered set of research notes.
"""

import json

from openai import OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from . import config
from .composio_tools import get_composio_client, get_search_tools
from .schema import AppResearch, ExtractedFields

# The research loop makes several OpenAI calls per app; under concurrency they can
# collectively exceed the account's tokens-per-minute limit even though each
# individual call is well-formed. Retry with backoff rather than failing the app
# outright -- a transient 429 is not evidence the app defeated the agent.
_retry_on_rate_limit = retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_random_exponential(min=2, max=90),
    stop=stop_after_attempt(10),
    reraise=True,
)

RESEARCH_SYSTEM_PROMPT = """You are a product-ops research analyst investigating whether a SaaS app \
could become an AI-agent toolkit (an MCP server or a set of agent-callable actions).

For every claim you make, you must have visited the actual documentation page (or a page that \
clearly discusses it) with a tool call this turn -- do not rely on prior knowledge alone. Prefer \
the app's own developer docs / API reference over third-party summaries. When the docs are \
ambiguous or you cannot find something after a reasonable search, say so explicitly rather than \
guessing.

Investigate, in order:
1. What auth method(s) the API uses (OAuth2, API key, Basic auth, bearer token, JWT, or none).
2. Whether a developer can get credentials themselves for free or on a trial (self-serve), or \
   whether it requires a paid plan, admin approval, or a partnership / contact-sales conversation.
3. What the public API surface looks like: REST, GraphQL, SDK-only, CLI-only, or none; roughly how \
   broad it is; and whether an official or well-known third-party MCP server already exists for it.
4. Whether this could be built as an agent toolkit today, and if not, the single biggest blocker.

Cite the exact URL(s) you found each fact on. When you are done researching, write a concise plain-text \
summary covering all four points above with URLs inline -- this summary is the only thing the next \
step sees, so make it complete and evidence-backed rather than vague."""


def build_research_prompt(app: dict, pass_number: int = 1) -> str:
    base = (
        f"Research \"{app['name']}\" ({app['hint']}), a {app['category']} app, for agent-toolkit "
        "buildability. Use the search tool to find its developer docs / API reference page(s), then "
        "the fetch tool to read the relevant pages. Cover auth method, self-serve vs gated credential "
        "access, API surface breadth, existing MCP server (if any), and a buildability verdict with the "
        "main blocker if it's not buildable today."
    )
    if pass_number >= 2:
        base += (
            " This is an independent verification pass -- research from scratch as if for the first "
            "time. Pay particular attention to the self-serve-vs-gated question: actually try to find "
            "the signup / API key / pricing page and quote the specific phrase that tells you whether a "
            "developer can get credentials for free or on a trial, versus needing a paid plan, admin "
            "approval, or a contact-sales conversation."
        )
    return base


@_retry_on_rate_limit
def _create(client: OpenAI, **kwargs):
    return client.chat.completions.create(**kwargs)


@_retry_on_rate_limit
def _parse(client: OpenAI, **kwargs):
    return client.chat.completions.parse(**kwargs)


def run_research_loop(
    client: OpenAI, composio, tools, app: dict, model: str, user_id: str, pass_number: int = 1
) -> str:
    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": build_research_prompt(app, pass_number)},
    ]
    response = _create(client, model=model, messages=messages, tools=tools)

    max_turns = 8
    turns = 0
    while response.choices[0].message.tool_calls and turns < max_turns:
        turns += 1
        tool_calls = response.choices[0].message.tool_calls
        results = composio.provider.handle_tool_calls(response=response, user_id=user_id)

        messages.append(response.choices[0].message)
        for tool_call, result in zip(tool_calls, results):
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)}
            )

        response = _create(client, model=model, messages=messages, tools=tools)

    return response.choices[0].message.content or ""


EXTRACTION_PROMPT_TEMPLATE = """Below are research notes gathered about the app "{name}" ({category}). \
Extract a structured record from them. If the notes don't clearly support a field, use the most honest \
"unknown"-style value for that field and lower the confidence score accordingly -- do not invent evidence \
URLs that weren't in the notes.

Be strict about api_surface.mcp_exists specifically: set it true only if the notes describe a real, \
current, stable MCP server -- from the app itself, or clearly documented by a major platform (e.g. \
Composio, Zapier) as an actual working offering. If the notes only mention an unofficial community repo, \
an unverified directory listing, or a "coming soon" / preview announcement, set it false and put that \
nuance in mcp_notes instead of letting it inflate mcp_exists.

Research notes:
---
{notes}
---
"""


def extract_structured(client: OpenAI, app: dict, research_notes: str, model: str) -> AppResearch:
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(name=app["name"], category=app["category"], notes=research_notes)
    completion = _parse(
        client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=ExtractedFields,
    )
    extracted: ExtractedFields = completion.choices[0].message.parsed
    fields = extracted.model_dump()
    fields["confidence"] = max(0.0, min(1.0, fields["confidence"]))
    return AppResearch(**fields, id=app["id"], name=app["name"], category=app["category"])


def research_app(app: dict, pass_number: int = 1, model: str | None = None) -> AppResearch:
    model = model or config.RESEARCH_MODEL
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    user_id = f"app-research-{app['id']}-pass{pass_number}"
    composio = get_composio_client()
    tools = get_search_tools(composio, user_id)

    research_notes = run_research_loop(client, composio, tools, app, model, user_id, pass_number)
    result = extract_structured(client, app, research_notes, model)
    result.pass_number = pass_number
    result.researcher_notes = research_notes[:2000]
    return result
