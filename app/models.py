from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EventType(str, Enum):
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    VIEWED = "viewed"
    SUBMITTED = "submitted"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    landing_title: Mapped[str] = mapped_column(String(255), nullable=False, default="Security Awareness Drill")
    landing_message: Mapped[str] = mapped_column(Text, nullable=False, default="This is a safe internal simulation.")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    employee_ref: Mapped[str] = mapped_column(String(64), nullable=False, default="N/A")
    department: Mapped[str] = mapped_column(String(128), nullable=False, default="General")
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    campaign: Mapped[Campaign] = relationship(back_populates="recipients")


class CampaignEvent(Base):
    __tablename__ = "campaign_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(SqlEnum(EventType), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="unknown", nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
