from sqlalchemy import Column, String, DateTime, Text, Float, Date
from sqlalchemy.sql import func

from .db import Base


class Case(Base):
    __tablename__ = "wizard_cases"

    id = Column(String, primary_key=True, index=True)
    draft_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    origin_country = Column(String, nullable=True)
    origin_city = Column(String, nullable=True)
    dest_country = Column(String, nullable=True)
    dest_city = Column(String, nullable=True)
    purpose = Column(String, nullable=True)
    target_move_date = Column(Date, nullable=True)
    flags_json = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="DRAFT")
    requirements_snapshot_id = Column(String, nullable=True)


class CountryProfile(Base):
    __tablename__ = "country_profiles"

    id = Column(String, primary_key=True, index=True)
    country_code = Column(String, index=True)
    last_updated_at = Column(DateTime, nullable=True)
    confidence_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)


class SourceRecord(Base):
    __tablename__ = "source_records"

    id = Column(String, primary_key=True, index=True)
    country_code = Column(String, index=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    publisher_domain = Column(String, nullable=False)
    retrieved_at = Column(DateTime, nullable=False)
    snippet = Column(Text, nullable=True)
    content_hash = Column(String, nullable=False, unique=True)


class RequirementItem(Base):
    __tablename__ = "requirement_items"

    id = Column(String, primary_key=True, index=True)
    country_code = Column(String, index=True)
    purpose = Column(String, nullable=False)
    pillar = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    required_fields_json = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=False)
    last_verified_at = Column(DateTime, nullable=False)


class CaseRequirementsSnapshot(Base):
    __tablename__ = "case_requirements_snapshots"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, index=True)
    dest_country = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    snapshot_json = Column(Text, nullable=False)
    sources_json = Column(Text, nullable=False)
