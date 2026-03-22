"""Pydantic request/response models for the dashboard API."""

from pydantic import BaseModel
from typing import Optional, List


# --- Auth ---

class LoginRequest(BaseModel):
    token: str


# --- Lists ---

class AddDomainRequest(BaseModel):
    domain: str
    reason: Optional[str] = None


class BulkImportRequest(BaseModel):
    domains: List[str]
    reason: Optional[str] = None


# --- Profiles ---

class CreateProfileRequest(BaseModel):
    name: str


class UpdateProfileRequest(BaseModel):
    name: str


class AddDeviceRequest(BaseModel):
    ip: str
    label: Optional[str] = None


# --- Focus ---

class CreateFocusRequest(BaseModel):
    profile_id: str
    note: str
    strictness: Optional[str] = "moderate"
    duration_minutes: int


class ExtendFocusRequest(BaseModel):
    extra_minutes: int


# --- Analysis ---

class CreateAnalysisRequest(BaseModel):
    domain: str
    profile_id: Optional[str] = None
    risk_level: Optional[str] = None
    category: Optional[str] = None
    reasoning: Optional[str] = None
    action_taken: Optional[str] = None
