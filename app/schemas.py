from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CampaignCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    scenario_name: str = Field(default="Contact Follow-up", min_length=3, max_length=255)
    landing_title: str = Field(default="Contact Request", min_length=3, max_length=255)
    landing_message: str = Field(
        default="Ism va familiyangizni qoldiring. Yuborilgan ma'lumot faqat aloqa uchun ishlatiladi.",
        min_length=12,
        max_length=1000,
    )


class RecipientCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    employee_ref: str = Field(default="N/A", min_length=1, max_length=64)
    department: str = Field(default="General", min_length=2, max_length=128)


class RecipientBatchCreate(BaseModel):
    campaign_id: int
    recipients: list[RecipientCreate] = Field(min_length=1, max_length=500)


class LandingForm(BaseModel):
    first_name: str = Field(min_length=2, max_length=64)
    last_name: str = Field(min_length=2, max_length=64)


class CampaignSummary(BaseModel):
    id: int
    name: str
    scenario_name: str
    recipient_count: int
    created_at: datetime


class CampaignSendRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    intro_line: str = Field(
        default="Quyidagi sahifada ism va familiyangizni qoldiring.",
        min_length=3,
        max_length=500,
    )
    recipient_ids: list[int] | None = None
