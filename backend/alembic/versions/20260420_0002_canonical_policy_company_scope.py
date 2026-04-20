"""add canonical policy company scope and query audit log"""

from alembic import op
import sqlalchemy as sa


revision = "20260420_0002"
down_revision = "20260420_0001"
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set:
    return {c["name"] for c in insp.get_columns(table)}


def _has_index(insp, table: str, index_name: str) -> bool:
    return any(ix.get("name") == index_name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    cols_doc = _column_names(insp, "canonical_policy_documents")
    if "company_id" not in cols_doc:
        with op.batch_alter_table("canonical_policy_documents") as batch_op:
            batch_op.add_column(sa.Column("company_id", sa.String(), nullable=True))
    insp = sa.inspect(bind)
    if not _has_index(insp, "canonical_policy_documents", "idx_canonical_policy_documents_company"):
        op.create_index("idx_canonical_policy_documents_company", "canonical_policy_documents", ["company_id"])

    cols_chunk = _column_names(insp, "canonical_policy_document_chunks")
    if "company_id" not in cols_chunk:
        with op.batch_alter_table("canonical_policy_document_chunks") as batch_op:
            batch_op.add_column(sa.Column("company_id", sa.String(), nullable=True))
    insp = sa.inspect(bind)
    if not _has_index(insp, "canonical_policy_document_chunks", "idx_canonical_policy_document_chunks_company"):
        op.create_index(
            "idx_canonical_policy_document_chunks_company",
            "canonical_policy_document_chunks",
            ["company_id"],
        )

    cols_facts = _column_names(insp, "canonical_policy_facts")
    if "company_id" not in cols_facts:
        with op.batch_alter_table("canonical_policy_facts") as batch_op:
            batch_op.add_column(sa.Column("company_id", sa.String(), nullable=True))
    insp = sa.inspect(bind)
    if not _has_index(insp, "canonical_policy_facts", "idx_canonical_policy_facts_company"):
        op.create_index("idx_canonical_policy_facts_company", "canonical_policy_facts", ["company_id"])

    cols_err = _column_names(insp, "canonical_policy_fact_validation_errors")
    if "company_id" not in cols_err:
        with op.batch_alter_table("canonical_policy_fact_validation_errors") as batch_op:
            batch_op.add_column(sa.Column("company_id", sa.String(), nullable=True))
    insp = sa.inspect(bind)
    if not _has_index(insp, "canonical_policy_fact_validation_errors", "idx_canonical_policy_fact_validation_errors_company"):
        op.create_index(
            "idx_canonical_policy_fact_validation_errors_company",
            "canonical_policy_fact_validation_errors",
            ["company_id"],
        )

    # Backfill from legacy policy_documents only when that table exists (runtime DDL may create it after Alembic 0001 on SQLite).
    if insp.has_table("policy_documents"):
        op.execute(
            """
            UPDATE canonical_policy_documents
            SET company_id = (
                SELECT company_id FROM policy_documents p
                WHERE p.id = canonical_policy_documents.source_policy_document_id
            )
            WHERE company_id IS NULL
            """
        )
    op.execute(
        """
        UPDATE canonical_policy_document_chunks
        SET company_id = (
            SELECT company_id FROM canonical_policy_documents d
            WHERE d.id = canonical_policy_document_chunks.canonical_policy_document_id
        )
        WHERE company_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE canonical_policy_facts
        SET company_id = (
            SELECT company_id FROM canonical_policy_documents d
            WHERE d.id = canonical_policy_facts.canonical_policy_document_id
        )
        WHERE company_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE canonical_policy_fact_validation_errors
        SET company_id = (
            SELECT company_id FROM canonical_policy_documents d
            WHERE d.id = canonical_policy_fact_validation_errors.canonical_policy_document_id
        )
        WHERE company_id IS NULL
        """
    )

    insp = sa.inspect(bind)
    if not insp.has_table("canonical_policy_query_audit_logs"):
        op.create_table(
            "canonical_policy_query_audit_logs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("company_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("user_role", sa.String(), nullable=False),
            sa.Column("canonical_policy_document_id", sa.String(), nullable=False),
            sa.Column("query_text", sa.Text(), nullable=False),
            sa.Column("redacted_query_text", sa.Text(), nullable=False),
            sa.Column("retrieved_chunk_ids_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("answer_preview", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    insp = sa.inspect(bind)
    if not _has_index(insp, "canonical_policy_query_audit_logs", "idx_canonical_policy_query_audit_logs_company"):
        op.create_index(
            "idx_canonical_policy_query_audit_logs_company",
            "canonical_policy_query_audit_logs",
            ["company_id"],
        )


def downgrade() -> None:
    op.drop_index("idx_canonical_policy_query_audit_logs_company", table_name="canonical_policy_query_audit_logs")
    op.drop_table("canonical_policy_query_audit_logs")

    with op.batch_alter_table("canonical_policy_fact_validation_errors") as batch_op:
        batch_op.drop_index("idx_canonical_policy_fact_validation_errors_company")
        batch_op.drop_column("company_id")

    with op.batch_alter_table("canonical_policy_facts") as batch_op:
        batch_op.drop_index("idx_canonical_policy_facts_company")
        batch_op.drop_column("company_id")

    with op.batch_alter_table("canonical_policy_document_chunks") as batch_op:
        batch_op.drop_index("idx_canonical_policy_document_chunks_company")
        batch_op.drop_column("company_id")

    with op.batch_alter_table("canonical_policy_documents") as batch_op:
        batch_op.drop_index("idx_canonical_policy_documents_company")
        batch_op.drop_column("company_id")
