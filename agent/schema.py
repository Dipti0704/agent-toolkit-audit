"""Shared data model for one researched app. Every pipeline stage reads/writes this shape.

Split into two classes on purpose: ExtractedFields is the ONLY thing shown to the
model as a structured-output target. AppResearch adds fields the pipeline computes
itself (id/name/category are copied from the seed data; pass_number and
disagreements are set by pass1/verify_pass2). Earlier this was one flat model and
the cheap extraction model would occasionally hallucinate content into
`disagreements` because it was a field in its own output schema -- it should never
have been something the model could write to in the first place.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AuthMethod(str, Enum):
    OAUTH2 = "OAuth2"
    API_KEY = "API Key"
    BASIC_AUTH = "Basic Auth"
    TOKEN = "Token/Bearer"
    JWT = "JWT"
    NONE = "None / Public"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class SelfServe(str, Enum):
    FREE_SELF_SERVE = "free_self_serve"
    TRIAL_SELF_SERVE = "trial_self_serve"
    PAID_GATED = "paid_plan_gated"
    ADMIN_APPROVAL_GATED = "admin_approval_gated"
    PARTNER_CONTACT_SALES = "partner_contact_sales"
    UNKNOWN = "unknown"


class Buildability(str, Enum):
    BUILDABLE_TODAY = "buildable_today"
    BUILDABLE_WITH_CAVEATS = "buildable_with_caveats"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ApiSurface(BaseModel):
    type: str = Field(description="e.g. 'REST', 'GraphQL', 'REST+GraphQL', 'SDK-only', 'CLI-only', 'None'")
    breadth: str = Field(description="short qualitative note, e.g. 'broad (100+ endpoints)' or 'narrow (single webhook)'")
    mcp_exists: bool = Field(
        description=(
            "STRICT: true only if the app itself (or a major, established platform like Composio/"
            "Zapier that clearly documents it as a stable, current offering) publishes a real, working "
            "MCP server for this app. False for: unofficial community wrapper repos, unverified "
            "third-party directory listings, 'coming soon' / preview announcements, or a competitor's "
            "similarly-named product. When in doubt, false -- put the nuance in mcp_notes instead."
        )
    )
    mcp_notes: Optional[str] = None


class Evidence(BaseModel):
    url: str
    note: Optional[str] = None


class ExtractedFields(BaseModel):
    """Everything the extraction call is allowed to produce. Nothing pipeline-managed lives here."""

    one_liner: str = Field(description="what the app does, in one line")

    auth_methods: list[AuthMethod] = Field(default_factory=list)
    self_serve: SelfServe = SelfServe.UNKNOWN
    self_serve_notes: Optional[str] = None

    api_surface: ApiSurface

    buildability_verdict: Buildability = Buildability.UNKNOWN
    blocker: Optional[str] = Field(default=None, description="the main blocker if not buildable_today")

    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, description="0.0-1.0; how confident the extraction is in these fields")


class AppResearch(ExtractedFields):
    """ExtractedFields plus the fields the pipeline itself owns."""

    id: int
    name: str
    category: str
    researcher_notes: Optional[str] = None

    # set by pass1_research.py / verify_pass2.py -- never by the model
    pass_number: int = 1
    disagreements: Optional[list[str]] = Field(default=None, description="fields pass2 disagreed with pass1 on")
