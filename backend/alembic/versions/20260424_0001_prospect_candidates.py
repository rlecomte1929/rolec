"""create prospect_candidates table for HR prospect pipeline

First routine in the agent-routines workstream: a staging table for HR
manager / mobility-lead prospects enriched by
`services.prospect_enrichment_service`. Rows start `pending_enrichment`
and are transitioned to `enriched` by the background enrichment task,
then to `approved` / `maybe` / `rejected` by a human reviewer in the
admin UI.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0001"
down_revision = "20260420_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prospect_candidates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("company_domain", sa.String(), nullable=True),
        sa.Column("company_linkedin_url", sa.String(), nullable=True),
        sa.Column("raw_input_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("enriched_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("icp_score", sa.Integer(), nullable=True),
        sa.Column("qualification_band", sa.String(), nullable=True),
        sa.Column("suggested_contact_title", sa.String(), nullable=True),
        sa.Column("suggested_hook", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending_enrichment"),
        sa.Column("enrichment_error", sa.Text(), nullable=True),
        sa.Column("web_search_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("batch_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("enriched_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_prospect_candidates_status",
        "prospect_candidates",
        ["status"],
    )
    op.create_index(
        "idx_prospect_candidates_batch",
        "prospect_candidates",
        ["batch_id"],
    )
    op.create_index(
        "idx_prospect_candidates_score",
        "prospect_candidates",
        ["icp_score"],
    )
    op.create_index(
        "idx_prospect_candidates_domain",
        "prospect_candidates",
        ["company_domain"],
    )


def downgrade() -> None:
    op.drop_index("idx_prospect_candidates_domain", table_name="prospect_candidates")
    op.drop_index("idx_prospect_candidates_score", table_name="prospect_candidates")
    op.drop_index("idx_prospect_candidates_batch", table_name="prospect_candidates")
    op.drop_index("idx_prospect_candidates_status", table_name="prospect_candidates")
    op.drop_table("prospect_candidates")
