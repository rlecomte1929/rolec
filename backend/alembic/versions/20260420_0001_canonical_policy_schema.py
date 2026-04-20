"""create canonical policy schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260420_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_policy_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_policy_document_id", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False, server_default="local_file"),
        sa.Column("source_uri", sa.String(), nullable=True),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("policy_scope", sa.String(), nullable=True),
        sa.Column("document_type", sa.String(), nullable=True),
        sa.Column("version_label", sa.String(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("default_currency", sa.String(), nullable=True),
        sa.Column("assignment_types_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("ingestion_status", sa.String(), nullable=False, server_default="ingested"),
        sa.Column("extraction_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_policy_document_id"], ["policy_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_canonical_policy_documents_source_policy",
        "canonical_policy_documents",
        ["source_policy_document_id"],
    )
    op.create_index(
        "idx_canonical_policy_documents_status",
        "canonical_policy_documents",
        ["extraction_status"],
    )

    op.create_table(
        "canonical_policy_document_chunks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("canonical_policy_document_id", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_path", sa.String(), nullable=True),
        sa.Column("structure_type", sa.String(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["canonical_policy_document_id"],
            ["canonical_policy_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_canonical_policy_document_chunks_doc",
        "canonical_policy_document_chunks",
        ["canonical_policy_document_id"],
    )
    op.create_index(
        "idx_canonical_policy_document_chunks_doc_chunk",
        "canonical_policy_document_chunks",
        ["canonical_policy_document_id", "chunk_index"],
        unique=True,
    )

    op.create_table(
        "canonical_policy_facts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("canonical_policy_document_id", sa.String(), nullable=False),
        sa.Column("canonical_policy_document_chunk_id", sa.String(), nullable=False),
        sa.Column("source_policy_document_id", sa.String(), nullable=True),
        sa.Column("phase", sa.String(), nullable=True),
        sa.Column("benefit_category", sa.String(), nullable=True),
        sa.Column("value_type", sa.String(), nullable=False),
        sa.Column("frequency", sa.String(), nullable=True),
        sa.Column("provider_entity", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("eligibility_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("assignment_types_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("percentage", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("duration_value", sa.Integer(), nullable=True),
        sa.Column("duration_unit", sa.String(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("is_taxable", sa.Boolean(), nullable=True),
        sa.Column("reimbursement_required", sa.Boolean(), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["canonical_policy_document_id"],
            ["canonical_policy_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_policy_document_chunk_id"],
            ["canonical_policy_document_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["source_policy_document_id"], ["policy_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_canonical_policy_facts_doc", "canonical_policy_facts", ["canonical_policy_document_id"])
    op.create_index("idx_canonical_policy_facts_chunk", "canonical_policy_facts", ["canonical_policy_document_chunk_id"])
    op.create_index(
        "idx_canonical_policy_facts_category_phase",
        "canonical_policy_facts",
        ["benefit_category", "phase"],
    )

    op.create_table(
        "canonical_policy_fact_validation_errors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("canonical_policy_document_id", sa.String(), nullable=False),
        sa.Column("canonical_policy_document_chunk_id", sa.String(), nullable=False),
        sa.Column("raw_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("errors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["canonical_policy_document_id"],
            ["canonical_policy_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_policy_document_chunk_id"],
            ["canonical_policy_document_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_canonical_policy_fact_validation_errors_doc",
        "canonical_policy_fact_validation_errors",
        ["canonical_policy_document_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_canonical_policy_fact_validation_errors_doc", table_name="canonical_policy_fact_validation_errors")
    op.drop_table("canonical_policy_fact_validation_errors")
    op.drop_index("idx_canonical_policy_facts_category_phase", table_name="canonical_policy_facts")
    op.drop_index("idx_canonical_policy_facts_chunk", table_name="canonical_policy_facts")
    op.drop_index("idx_canonical_policy_facts_doc", table_name="canonical_policy_facts")
    op.drop_table("canonical_policy_facts")
    op.drop_index("idx_canonical_policy_document_chunks_doc_chunk", table_name="canonical_policy_document_chunks")
    op.drop_index("idx_canonical_policy_document_chunks_doc", table_name="canonical_policy_document_chunks")
    op.drop_table("canonical_policy_document_chunks")
    op.drop_index("idx_canonical_policy_documents_status", table_name="canonical_policy_documents")
    op.drop_index("idx_canonical_policy_documents_source_policy", table_name="canonical_policy_documents")
    op.drop_table("canonical_policy_documents")
