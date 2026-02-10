"""create presets table

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-02-10 14:00:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Seed data — mirrors DEFAULT_PRESETS from backend/app/models/presets.py
_SEED_PRESETS = [
    {
        "id": "prof_short_agree",
        "label": "Professional – Short Agreement",
        "tone": "professional",
        "length_bucket": "short",
        "intent": "agree",
        "description": "A brief, professional reply that agrees with the author's point and adds a supporting observation.",
        "guidance_bullets": json.dumps(["Acknowledge the author's point directly", "Add a brief supporting observation"]),
        "allow_hashtags": False,
        "is_default": True,
    },
    {
        "id": "casual_medium_add",
        "label": "Casual – Medium Add-On",
        "tone": "casual",
        "length_bucket": "medium",
        "intent": "add_perspective",
        "description": "A conversational, medium-length reply that adds a new angle or personal experience to the discussion.",
        "guidance_bullets": json.dumps(["Use a conversational, approachable voice", "Offer an additional angle or personal experience"]),
        "allow_hashtags": False,
        "is_default": False,
    },
    {
        "id": "supportive_short_encourage",
        "label": "Supportive – Short Encouragement",
        "tone": "supportive",
        "length_bucket": "short",
        "intent": "encourage",
        "description": "A short, warm reply that appreciates the post and encourages the author to keep sharing.",
        "guidance_bullets": json.dumps(["Express genuine appreciation for the post", "Encourage the author to keep sharing"]),
        "allow_hashtags": False,
        "is_default": False,
    },
    {
        "id": "contrarian_medium_challenge",
        "label": "Contrarian – Medium Challenge",
        "tone": "contrarian",
        "length_bucket": "medium",
        "intent": "challenge",
        "description": "A respectful, medium-length reply that presents an alternative viewpoint backed by reasoning.",
        "guidance_bullets": json.dumps(["Respectfully present an alternative viewpoint", "Back up the counterpoint with reasoning"]),
        "allow_hashtags": False,
        "is_default": False,
    },
    {
        "id": "prof_medium_insight",
        "label": "Professional – Medium Insight",
        "tone": "professional",
        "length_bucket": "medium",
        "intent": "share_insight",
        "description": "A professional, medium-length reply that shares a relevant insight or data point tied to the original post.",
        "guidance_bullets": json.dumps(["Share a relevant professional insight or data point", "Connect the insight back to the original post"]),
        "allow_hashtags": False,
        "is_default": False,
    },
    {
        "id": "casual_short_react",
        "label": "Casual – Short Reaction",
        "tone": "casual",
        "length_bucket": "short",
        "intent": "react",
        "description": "A quick, genuine reaction in a casual and conversational tone.",
        "guidance_bullets": json.dumps(["Express a genuine, brief reaction", "Keep it conversational and authentic"]),
        "allow_hashtags": False,
        "is_default": False,
    },
    {
        "id": "supportive_medium_story",
        "label": "Supportive – Medium Personal Story",
        "tone": "supportive",
        "length_bucket": "medium",
        "intent": "share_experience",
        "description": "A medium-length reply that relates a personal experience with empathy and connection to the author.",
        "guidance_bullets": json.dumps(["Relate a brief personal or professional experience", "Show empathy and connection to the author's situation"]),
        "allow_hashtags": False,
        "is_default": False,
    },
    {
        "id": "prof_long_analysis",
        "label": "Professional – Long Analysis",
        "tone": "professional",
        "length_bucket": "long",
        "intent": "analyze",
        "description": "A detailed, structured analysis that references the original post and offers a clear recommendation.",
        "guidance_bullets": json.dumps(["Provide a structured, thoughtful analysis", "Reference specific points from the original post", "Offer a clear takeaway or recommendation"]),
        "allow_hashtags": False,
        "is_default": False,
    },
]


def upgrade() -> None:
    op.create_table(
        "presets",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("tone", sa.String(50), nullable=False),
        sa.Column("length_bucket", sa.String(20), nullable=False),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("guidance_bullets", sa.Text(), nullable=True),
        sa.Column("allow_hashtags", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.bulk_insert(sa.table(
        "presets",
        sa.column("id", sa.String),
        sa.column("label", sa.String),
        sa.column("tone", sa.String),
        sa.column("length_bucket", sa.String),
        sa.column("intent", sa.String),
        sa.column("description", sa.Text),
        sa.column("guidance_bullets", sa.Text),
        sa.column("allow_hashtags", sa.Boolean),
        sa.column("is_default", sa.Boolean),
    ), _SEED_PRESETS)


def downgrade() -> None:
    op.drop_table("presets")
