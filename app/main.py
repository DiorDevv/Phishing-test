import os

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.orm import Session

from app.config import STATIC_DIR, TEMPLATES_DIR
from app.database import Base, engine, get_db
from app.mailer import notify_admin, send_html_email, smtp_ready
from app.models import CampaignEvent, EventType
from app.services import (
    client_context,
    create_simple_recipient,
    event_counts,
    get_recipient_by_id_or_404,
    get_recipient_or_404,
    list_events,
    list_recipients_status,
    recipient_status_payload,
    render_email_html,
    recipient_summary,
    log_event,
)

_TRANSPARENT_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00"
    b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Contact Sender", version="3.0.0")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

ADMIN_KEY = os.getenv("SIM_ADMIN_KEY", "change-me")


def supplied_admin_key(request: Request) -> str | None:
    return request.headers.get("x-admin-key") or request.query_params.get("admin_key")


def is_admin(request: Request) -> bool:
    return supplied_admin_key(request) == ADMIN_KEY


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Admin access denied")


def base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    if not is_admin(request):
        return templates.TemplateResponse(request, "login.html", {})
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "events": list_events(db),
            "counts": event_counts(db),
            "admin_key": ADMIN_KEY,
            "smtp_ready": smtp_ready(),
        },
    )


@app.get("/recipients/{recipient_id}", response_class=HTMLResponse)
def recipient_detail(recipient_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    summary = recipient_summary(db, get_recipient_by_id_or_404(db, recipient_id))
    return templates.TemplateResponse(
        request,
        "recipient_detail.html",
        {
            "summary": summary,
            "admin_key": ADMIN_KEY,
            "base_url": base_url(request),
        },
    )


@app.post("/api/send")
def send_single_email(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    message: str = Form(""),
    db: Session = Depends(get_db),
):
    require_admin(request)
    recipient = create_simple_recipient(db, email=email)
    origin = base_url(request)
    html_body = render_email_html(
        recipient=recipient,
        base_url=origin,
        intro_line="Quyidagi tugmani bosib ism va familiyangizni kiriting.",
        custom_message=message,
    )
    send_html_email(
        to_email=recipient.email,
        subject="Ma'lumotlaringizni kiriting",
        html_body=html_body,
    )
    db.commit()
    return recipient_status_payload(db, recipient, origin)


@app.get("/api/recipients")
def api_list_recipients(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    return list_recipients_status(db, base_url(request))


@app.get("/api/status/{recipient_id}")
def api_recipient_status(recipient_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    recipient = get_recipient_by_id_or_404(db, recipient_id)
    return recipient_status_payload(db, recipient, base_url(request))


@app.delete("/api/recipients/{recipient_id}")
def api_delete_recipient(recipient_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    recipient = get_recipient_by_id_or_404(db, recipient_id)
    db.execute(sql_delete(CampaignEvent).where(CampaignEvent.token == recipient.token))
    db.delete(recipient)
    db.commit()
    return {"deleted": recipient_id}


@app.get("/pixel/{token}")
def track_open(token: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    recipient = get_recipient_or_404(db, token)
    ip_address, user_agent = client_context(request)
    already_opened = db.scalar(
        select(CampaignEvent).where(
            CampaignEvent.token == token,
            CampaignEvent.event_type == EventType.OPENED,
        )
    )
    log_event(db, token, EventType.OPENED, ip_address=ip_address, user_agent=user_agent)
    db.commit()
    if not already_opened:
        background_tasks.add_task(
            notify_admin,
            event_type="opened",
            recipient_email=recipient.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    return Response(
        content=_TRANSPARENT_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/r/{token}")
def track_click(token: str, request: Request, db: Session = Depends(get_db)):
    get_recipient_or_404(db, token)
    ip_address, user_agent = client_context(request)
    log_event(db, token, EventType.CLICKED, ip_address=ip_address, user_agent=user_agent)
    db.commit()
    return RedirectResponse(url=f"/landing/{token}", status_code=307)


@app.get("/landing/{token}", response_class=HTMLResponse)
def landing_page(token: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    recipient = get_recipient_or_404(db, token)
    ip_address, user_agent = client_context(request)
    already_viewed = db.scalar(
        select(CampaignEvent).where(
            CampaignEvent.token == token,
            CampaignEvent.event_type == EventType.VIEWED,
        )
    )
    log_event(db, token, EventType.VIEWED, ip_address=ip_address, user_agent=user_agent)
    db.commit()
    if not already_viewed:
        background_tasks.add_task(
            notify_admin,
            event_type="viewed",
            recipient_email=recipient.email,
            ip_address=ip_address,
            user_agent=user_agent,
            extra={"📧 Hodim email": recipient.email},
        )
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"recipient": recipient, "submitted": False},
    )


@app.post("/landing/{token}", response_class=HTMLResponse)
def submit_landing(
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
    first_name: str = Form(...),
    last_name: str = Form(...),
    db: Session = Depends(get_db),
):
    recipient = get_recipient_or_404(db, token)
    ip_address, user_agent = client_context(request)
    log_event(
        db,
        token,
        EventType.SUBMITTED,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"first_name": first_name, "last_name": last_name},
    )
    db.commit()
    background_tasks.add_task(
        notify_admin,
        event_type="submitted",
        recipient_email=recipient.email,
        ip_address=ip_address,
        user_agent=user_agent,
        extra={
            "📧 Hodim email": recipient.email,
            "👤 Ism": first_name,
            "👤 Familiya": last_name,
            "✅ To'liq ism": f"{first_name} {last_name}",
        },
    )
    return templates.TemplateResponse(
        request,
        "landing.html",
        {"recipient": recipient, "submitted": True, "first_name": first_name, "last_name": last_name},
    )
