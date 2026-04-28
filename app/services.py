import csv
import io
import json
import secrets
from collections import Counter, defaultdict
from typing import Any

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Campaign, CampaignEvent, CampaignRecipient, EventType


def issue_token() -> str:
    return secrets.token_urlsafe(24)


def client_context(request: Request) -> tuple[str, str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    elif request.client:
        ip_address = request.client.host
    else:
        ip_address = "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    return ip_address, user_agent


def create_campaign(
    db: Session,
    *,
    name: str,
    scenario_name: str,
    landing_title: str,
    landing_message: str,
) -> Campaign:
    campaign = Campaign(
        name=name,
        scenario_name=scenario_name,
        landing_title=landing_title,
        landing_message=landing_message,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def get_or_create_default_campaign(db: Session) -> Campaign:
    campaign = db.scalar(select(Campaign).where(Campaign.name == "Default Contact Form"))
    if campaign:
        return campaign
    campaign = Campaign(
        name="Default Contact Form",
        scenario_name="Contact Follow-up",
        landing_title="Contact Request",
        landing_message="Ism va familiyangizni kiriting. Ma'lumot faqat aloqa uchun ishlatiladi.",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def get_campaign_or_404(db: Session, campaign_id: int) -> Campaign:
    campaign = db.scalar(
        select(Campaign)
        .options(selectinload(Campaign.recipients))
        .where(Campaign.id == campaign_id)
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Unknown campaign")
    return campaign


def create_recipient(
    db: Session,
    *,
    campaign_id: int,
    email: str,
    full_name: str,
    employee_ref: str,
    department: str,
) -> CampaignRecipient:
    campaign = get_campaign_or_404(db, campaign_id)
    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        email=email,
        full_name=full_name,
        employee_ref=employee_ref,
        department=department,
        token=issue_token(),
    )
    db.add(recipient)
    db.flush()
    log_event(db, recipient.token, EventType.SENT, metadata={"email": email, "campaign_id": campaign_id})
    db.commit()
    db.refresh(recipient)
    return recipient


def create_simple_recipient(db: Session, *, email: str) -> CampaignRecipient:
    campaign = get_or_create_default_campaign(db)
    local_name = email.split("@", 1)[0]
    display_name = local_name.replace(".", " ").replace("_", " ").strip() or email
    return create_recipient(
        db,
        campaign_id=campaign.id,
        email=email,
        full_name=display_name.title(),
        employee_ref="N/A",
        department="Contact",
    )


def latest_recipient_for_email(db: Session, email: str) -> CampaignRecipient | None:
    return db.scalar(
        select(CampaignRecipient)
        .options(joinedload(CampaignRecipient.campaign))
        .where(CampaignRecipient.email == email)
        .order_by(desc(CampaignRecipient.created_at))
    )


def create_recipients_bulk(db: Session, *, campaign_id: int, recipients: list[dict[str, str]]) -> list[CampaignRecipient]:
    created: list[CampaignRecipient] = []
    get_campaign_or_404(db, campaign_id)
    for row in recipients:
        recipient = CampaignRecipient(
            campaign_id=campaign_id,
            email=row["email"],
            full_name=row["full_name"],
            employee_ref=row.get("employee_ref", "N/A"),
            department=row.get("department", "General"),
            token=issue_token(),
        )
        db.add(recipient)
        db.flush()
        log_event(db, recipient.token, EventType.SENT, metadata={"email": row["email"], "campaign_id": campaign_id})
        created.append(recipient)
    db.commit()
    for recipient in created:
        db.refresh(recipient)
    return created


async def parse_csv_upload(upload: UploadFile) -> list[dict[str, str]]:
    content = await upload.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"email", "full_name"}
    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty")
    if not required.issubset(rows[0].keys()):
        raise HTTPException(status_code=400, detail="CSV must include email and full_name columns")
    return rows


def get_recipient_or_404(db: Session, token: str) -> CampaignRecipient:
    recipient = db.scalar(
        select(CampaignRecipient)
        .options(joinedload(CampaignRecipient.campaign))
        .where(CampaignRecipient.token == token)
    )
    if not recipient:
        raise HTTPException(status_code=404, detail="Unknown campaign token")
    return recipient


def get_recipient_by_id_or_404(db: Session, recipient_id: int) -> CampaignRecipient:
    recipient = db.scalar(
        select(CampaignRecipient)
        .options(joinedload(CampaignRecipient.campaign))
        .where(CampaignRecipient.id == recipient_id)
    )
    if not recipient:
        raise HTTPException(status_code=404, detail="Unknown recipient")
    return recipient


def log_event(
    db: Session,
    token: str,
    event_type: EventType,
    *,
    ip_address: str = "unknown",
    user_agent: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> CampaignEvent:
    event = CampaignEvent(
        token=token,
        event_type=event_type,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=True),
    )
    db.add(event)
    db.flush()
    return event


def list_events(db: Session, limit: int = 200) -> list[CampaignEvent]:
    return list(db.scalars(select(CampaignEvent).order_by(desc(CampaignEvent.created_at)).limit(limit)))


def list_campaigns(db: Session) -> list[Campaign]:
    return list(db.scalars(select(Campaign).order_by(desc(Campaign.created_at))))


def list_recipients(db: Session, campaign_id: int | None = None) -> list[CampaignRecipient]:
    query = select(CampaignRecipient).options(joinedload(CampaignRecipient.campaign)).order_by(desc(CampaignRecipient.created_at))
    if campaign_id is not None:
        query = query.where(CampaignRecipient.campaign_id == campaign_id)
    return list(db.scalars(query))


def list_recipient_events(db: Session, token: str) -> list[CampaignEvent]:
    return list(
        db.scalars(
            select(CampaignEvent)
            .where(CampaignEvent.token == token)
            .order_by(desc(CampaignEvent.created_at))
        )
    )


def event_counts(db: Session) -> dict[str, int]:
    counts = Counter(event.event_type.value for event in list_events(db, limit=5000))
    return {event.value: counts.get(event.value, 0) for event in EventType}


def campaign_rollup(db: Session) -> list[dict[str, Any]]:
    campaigns = list_campaigns(db)
    event_map: dict[str, set[str]] = {event.value: set() for event in EventType}
    for event in list_events(db, limit=10000):
        event_map[event.event_type.value].add(event.token)

    rollup: list[dict[str, Any]] = []
    for campaign in campaigns:
        campaign_tokens = {recipient.token for recipient in campaign.recipients}
        rollup.append(
            {
                "campaign": campaign,
                "recipient_count": len(campaign.recipients),
                "clicked_count": len(campaign_tokens & event_map[EventType.CLICKED.value]),
                "viewed_count": len(campaign_tokens & event_map[EventType.VIEWED.value]),
                "submitted_count": len(campaign_tokens & event_map[EventType.SUBMITTED.value]),
            }
        )
    return rollup


def recipient_summary(db: Session, recipient: CampaignRecipient) -> dict[str, Any]:
    events = list_recipient_events(db, recipient.token)
    counts = Counter(event.event_type.value for event in events)
    return {
        "recipient": recipient,
        "events": events,
        "counts": {event.value: counts.get(event.value, 0) for event in EventType},
    }


def latest_event_time(events: list[CampaignEvent], event_type: EventType) -> str | None:
    for event in events:
        if event.event_type == event_type:
            return event.created_at.isoformat(sep=" ", timespec="seconds")
    return None


def recipient_status_payload(db: Session, recipient: CampaignRecipient, base_url: str) -> dict[str, Any]:
    summary = recipient_summary(db, recipient)
    events = summary["events"]
    return {
        "recipient_id": recipient.id,
        "email": recipient.email,
        "status": "sent",
        "link": f"{base_url}/r/{recipient.token}",
        "landing_url": f"{base_url}/landing/{recipient.token}",
        "sent_at": latest_event_time(events, EventType.SENT),
        "opened_at": latest_event_time(events, EventType.OPENED),
        "clicked_at": latest_event_time(events, EventType.CLICKED),
        "viewed_at": latest_event_time(events, EventType.VIEWED),
        "submitted_at": latest_event_time(events, EventType.SUBMITTED),
        "submitted_name": next(
            (
                f"{json.loads(event.metadata_json).get('first_name', '')} {json.loads(event.metadata_json).get('last_name', '')}".strip()
                for event in events
                if event.event_type == EventType.SUBMITTED
            ),
            None,
        ),
    }


def list_recipients_status(db: Session, base_url: str) -> list[dict[str, Any]]:
    recipients = list(db.scalars(
        select(CampaignRecipient)
        .options(joinedload(CampaignRecipient.campaign))
        .order_by(desc(CampaignRecipient.created_at))
    ))
    if not recipients:
        return []
    tokens = [r.token for r in recipients]
    events = list(db.scalars(
        select(CampaignEvent)
        .where(CampaignEvent.token.in_(tokens))
        .order_by(desc(CampaignEvent.created_at))
    ))
    ev_map: dict[str, list[CampaignEvent]] = defaultdict(list)
    for e in events:
        ev_map[e.token].append(e)

    result = []
    for r in recipients:
        evs = ev_map[r.token]
        submitted_name = next(
            (
                f"{json.loads(e.metadata_json).get('first_name','')} "
                f"{json.loads(e.metadata_json).get('last_name','')}".strip()
                for e in evs
                if e.event_type == EventType.SUBMITTED
            ),
            None,
        )
        result.append({
            "id": r.id,
            "email": r.email,
            "full_name": r.full_name,
            "status": "sent",
            "link": f"{base_url}/r/{r.token}",
            "landing_url": f"{base_url}/landing/{r.token}",
            "sent_at": latest_event_time(evs, EventType.SENT),
            "opened_at": latest_event_time(evs, EventType.OPENED),
            "clicked_at": latest_event_time(evs, EventType.CLICKED),
            "viewed_at": latest_event_time(evs, EventType.VIEWED),
            "submitted_at": latest_event_time(evs, EventType.SUBMITTED),
            "submitted_name": submitted_name,
        })
    return result


def render_email_html(*, recipient: CampaignRecipient, base_url: str, intro_line: str) -> str:
    link = f"{base_url}/r/{recipient.token}"
    pixel = f"{base_url}/pixel/{recipient.token}"
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="background:#f1f5f9;margin:0;padding:40px 16px;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:480px;margin:0 auto">

  <!-- Logo -->
  <div style="text-align:center;margin-bottom:28px">
    <div style="display:inline-block;width:48px;height:48px;border-radius:12px;
                background:linear-gradient(135deg,#6366f1,#8b5cf6);
                line-height:48px;text-align:center;font-size:22px">🏢</div>
  </div>

  <!-- Karta -->
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:20px;
              padding:36px 32px;box-shadow:0 4px 20px rgba(0,0,0,.06)">

    <h2 style="margin:0 0 10px;font-size:1.35rem;font-weight:700;color:#0f172a;
               letter-spacing:-.02em">Ma'lumotlaringizni kiriting</h2>

    <p style="margin:0 0 28px;color:#64748b;font-size:.94rem;line-height:1.6">
      {intro_line}
    </p>

    <!-- Tugma -->
    <a href="{link}"
       style="display:block;text-align:center;
              background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 100%);
              color:#ffffff;font-size:.95rem;font-weight:700;
              padding:14px 24px;border-radius:999px;text-decoration:none;
              box-shadow:0 6px 20px rgba(99,102,241,.38)">
      Formani to'ldirish &rarr;
    </a>

    <!-- Zaxira link -->
    <p style="margin:20px 0 0;text-align:center;color:#94a3b8;font-size:.78rem;line-height:1.6">
      Tugma ishlamasa, quyidagi linkni brauzerga nusxalang:<br>
      <a href="{link}" style="color:#6366f1;word-break:break-all">{link}</a>
    </p>

  </div>

  <p style="text-align:center;color:#cbd5e1;font-size:.74rem;margin-top:20px">
    Bu xabar avtomatik yuborildi &middot; Javob bermang
  </p>

</div>
<!-- tracking pixel -->
<img src="{pixel}" width="1" height="1" style="display:none;border:0" alt="">
</body></html>"""
