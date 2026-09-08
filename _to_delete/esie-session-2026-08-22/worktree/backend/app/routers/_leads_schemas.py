from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

VALID_STATUSES = {"new", "contacted", "qualified", "converted", "lost"}
VALID_SOURCES = {"marketing_site", "manual", "referral"}


class LeadCaptureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=200)
    last_name: Optional[str] = Field(None, max_length=200)
    company_domain: Optional[str] = Field(None, max_length=300)
    message: Optional[str] = Field(None, max_length=2000)
    source: str = Field("marketing_site", max_length=50)
    utm_source: Optional[str] = Field(None, max_length=200)
    utm_campaign: Optional[str] = Field(None, max_length=200)


class LeadPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Optional[str] = Field(None)
    tags: Optional[List[str]] = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    company_domain: Optional[str]
    source: str
    status: str
    tags: List[str]
    message: Optional[str]
    utm_source: Optional[str]
    utm_campaign: Optional[str]
    created_at: Any
    updated_at: Any
    matched_prospect: bool = False


class LeadStatsOut(BaseModel):
    total: int
    new_this_week: int
    by_status: dict
