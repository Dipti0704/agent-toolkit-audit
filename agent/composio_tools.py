"""Wires Composio's no-auth-required search toolkit into the OpenAI tool-use loop.

COMPOSIO_SEARCH is a Composio-hosted toolkit (web search, URL fetch, news, scholar, etc.)
that requires no connected account / OAuth on our side -- Composio proxies it. That's what
makes it usable for a from-scratch research agent without asking every app for credentials
just to go search its own docs.

Verified against the actually-installed composio==1.0.0rc10 package (not just its docs
site, which described a session API -- composio.create(user_id) -- that this rc doesn't
have). The real surface is composio.tools.get(user_id, toolkits=[...]), and the OpenAI
provider ships bundled in the base package as the default -- no composio-openai add-on
needed for this SDK generation.
"""

from composio import Composio

from . import config

SEARCH_TOOLKIT = "COMPOSIO_SEARCH"


def get_composio_client() -> Composio:
    return Composio(api_key=config.COMPOSIO_API_KEY)


def get_search_tools(composio: Composio, user_id: str):
    return composio.tools.get(user_id=user_id, toolkits=[SEARCH_TOOLKIT])
