"""
Substrait Simple CRM App — a single backend serving both the web UI and REST API.

Substrait contract requirements:
  1. Port 8000 (handled via cicd/Dockerfile.backend)
  2. GET /health returns 200 (readiness check)
  3. JSON API under /api
"""

from datetime import datetime, timezone
import json
import os
import threading
from typing import Any, List, Optional
import urllib.error
import urllib.request
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

APP_NAME = "NinjaCRM"

app = FastAPI(title=APP_NAME, description="Simple CRM for Leads and Sales Pipelines", docs_url="/api/docs")

# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

STAGES = ["lead", "contacted", "qualified", "proposal", "won", "lost"]
STAGE_LABELS = {
    "lead": "New Lead",
    "contacted": "Contacted",
    "qualified": "Qualified",
    "proposal": "Proposal Sent",
    "won": "Closed Won",
    "lost": "Closed Lost",
}


class Note(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str
    author: str = "Sales Rep"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )


class Lead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    company: str
    email: str
    phone: str = ""
    value: float = 0.0
    stage: str = "lead"
    notes: List[Note] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )


class LeadCreate(BaseModel):
    name: str
    company: str
    email: str
    phone: Optional[str] = ""
    value: Optional[float] = 0.0
    stage: Optional[str] = "lead"
    initial_note: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    value: Optional[float] = None
    stage: Optional[str] = None


class NoteCreate(BaseModel):
    content: str
    author: Optional[str] = None


class BridgePush(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])


class GatewayAsk(BaseModel):
    prompt: str
    token: str = ""


class GatewayTokenConfig(BaseModel):
    token: str
    daily_cap: int = 20


class GatewayRelay(BaseModel):
    prompt: str = "Reply with exactly SESSION4_CROSS_APP_OK"
    token: str = "session4-cross-app-smoke"


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Thread-Safe Data Store
# ─────────────────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_leads: dict[str, Lead] = {}
_bridge_rows: list[dict[str, Any]] = []
_bridge_pending: list[dict[str, Any]] = []
_gateway_log: list[dict[str, Any]] = []
_gateway_counts: dict[str, dict[str, int | str]] = {}


def _seed_demo_data():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    demo_items = [
        Lead(
            id="lead-1",
            name="Sarah Chen",
            company="Starlight Fashion Asia",
            email="sarah.chen@starlightfashion.sg",
            phone="+65 9123 4567",
            value=24500.0,
            stage="proposal",
            created_at=now_str,
            updated_at=now_str,
            notes=[
                Note(
                    content="Sent tailored Q4 cross-border shipping proposal. Sarah requested a SLA guarantee on next-day deliveries.",
                    author="Sean Goh",
                    created_at=now_str,
                )
            ],
        ),
        Lead(
            id="lead-2",
            name="Marcus Tan",
            company="Apex Electronics Hub",
            email="marcus.t@apexelectronics.com",
            phone="+65 8234 5678",
            value=58000.0,
            stage="qualified",
            created_at=now_str,
            updated_at=now_str,
            notes=[
                Note(
                    content="Technical discovery call completed. High interest in API integration for automated parcel tracking.",
                    author="Sean Goh",
                    created_at=now_str,
                )
            ],
        ),
        Lead(
            id="lead-3",
            name="Priya Sharma",
            company="Organic Bites Marketplace",
            email="priya@organicbites.co",
            phone="+65 9876 5432",
            value=12500.0,
            stage="contacted",
            created_at=now_str,
            updated_at=now_str,
            notes=[
                Note(
                    content="Reached out via LinkedIn. Scheduled introductory demo for next Tuesday.",
                    author="Sean Goh",
                    created_at=now_str,
                )
            ],
        ),
        Lead(
            id="lead-4",
            name="Kenji Watanabe",
            company="Zenith Home Goods",
            email="kenji@zenithgoods.jp",
            phone="+65 9345 6789",
            value=95000.0,
            stage="won",
            created_at=now_str,
            updated_at=now_str,
            notes=[
                Note(
                    content="Annual master logistics contract signed! Onboarding kickoff meeting set for next month.",
                    author="Sean Goh",
                    created_at=now_str,
                )
            ],
        ),
        Lead(
            id="lead-5",
            name="Amanda Lim",
            company="Glow Cosmetics SG",
            email="amanda@glowcosmetics.com.sg",
            phone="+65 8123 9876",
            value=18000.0,
            stage="lead",
            created_at=now_str,
            updated_at=now_str,
            notes=[
                Note(
                    content="Inbound inquiry from website form requesting temperature-controlled fulfillment options.",
                    author="System",
                    created_at=now_str,
                )
            ],
        ),
        Lead(
            id="lead-6",
            name="Daniel O'Connor",
            company="Global Freight Connect",
            email="daniel@globalfreight.net",
            phone="+65 9567 1234",
            value=34000.0,
            stage="lost",
            created_at=now_str,
            updated_at=now_str,
            notes=[
                Note(
                    content="Decided to postpone regional expansion to next fiscal year. Keep warm for Q2 follow-up.",
                    author="Sean Goh",
                    created_at=now_str,
                )
            ],
        ),
    ]
    with _lock:
        _leads.clear()
        for item in demo_items:
            _leads[item.id] = item


_seed_demo_data()


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _require_secret(request: Request, env_name: str):
    expected = os.getenv(env_name, "")
    token = _bearer_token(request)
    if not expected:
        raise HTTPException(status_code=503, detail=f"{env_name} is not configured")
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def _today_sg() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/api/info", tags=["system"])
def info(request: Request):
    user_email = request.headers.get("X-Forwarded-Email", "user@ninjavan.co")
    user_name = request.headers.get("X-Forwarded-User", user_email.split("@")[0])
    return {
        "app": APP_NAME,
        "version": "1.0.0",
        "server_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "user": {"email": user_email, "name": user_name},
    }


@app.post("/api/bridge/push-rows", tags=["session4"])
def bridge_push_rows(payload: BridgePush, request: Request):
    _require_secret(request, "SESSION4_SHARED_SECRET")
    received_at = datetime.now(timezone.utc).isoformat()
    accepted = []
    with _lock:
        for row in payload.rows[:50]:
            item = {
                "id": str(uuid.uuid4())[:8],
                "request_id": payload.request_id,
                "received_at": received_at,
                "row": row,
            }
            _bridge_rows.append(item)
            accepted.append(item)
            if row.get("email_to") or row.get("write_back"):
                _bridge_pending.append(
                    {
                        "id": item["id"],
                        "type": "email" if row.get("email_to") else "write_back",
                        "row": row,
                        "created_at": received_at,
                    }
                )
    return {"ok": True, "accepted": len(accepted), "request_id": payload.request_id}


@app.get("/api/bridge/pending", tags=["session4"])
def bridge_pending(request: Request):
    _require_secret(request, "SESSION4_SHARED_SECRET")
    with _lock:
        pending = list(_bridge_pending)
        _bridge_pending.clear()
    return {"ok": True, "items": pending}


@app.post("/api/gateway/configure-token", tags=["session4"])
def gateway_configure_token(payload: GatewayTokenConfig, request: Request):
    _require_secret(request, "SESSION4_ADMIN_TOKEN")
    with _lock:
        _gateway_counts[payload.token] = {"date": _today_sg(), "count": 0, "cap": payload.daily_cap}
    return {"ok": True, "token_suffix": payload.token[-4:], "daily_cap": payload.daily_cap}


@app.post("/api/gateway/ask", tags=["session4"])
def gateway_ask(payload: GatewayAsk, request: Request):
    api_key = os.getenv("GEMINI_API_KEY", "")
    caller_key = _bearer_token(request)
    expected_caller_key = os.getenv("SESSION4_GATEWAY_API_KEY", "")
    if not expected_caller_key:
        raise HTTPException(status_code=503, detail="SESSION4_GATEWAY_API_KEY is not configured")
    if caller_key != expected_caller_key:
        raise HTTPException(status_code=401, detail="Invalid gateway API key")
    caller_id = request.headers.get("X-Caller-App", "unknown-caller")[:80]
    caller_token = payload.token or caller_key
    key_configured = bool(api_key)
    today = _today_sg()
    with _lock:
        entry = _gateway_counts.setdefault(caller_token, {"date": today, "count": 0, "cap": 20})
        if entry["date"] != today:
            entry["date"] = today
            entry["count"] = 0
        if int(entry["count"]) >= int(entry["cap"]):
            raise HTTPException(status_code=429, detail="Daily cap exceeded for token")
        entry["count"] = int(entry["count"]) + 1
        log_item = {
            "caller": caller_id,
            "token_suffix": caller_token[-4:],
            "prompt_chars": len(payload.prompt),
            "key_configured": key_configured,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _gateway_log.append(log_item)
    if not key_configured:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured")
    body = json.dumps(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": payload.prompt[:4000]}],
                }
            ]
        }
    ).encode("utf-8")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent?key="
        + api_key
    )
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            gemini_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:1000]
        raise HTTPException(
            status_code=502,
            detail={"gemini_status": exc.code, "gemini_error": error_body},
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}") from exc
    answer = (
        gemini_payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    return {
        "ok": True,
        "answer": answer,
        "usage": {"today": entry["count"], "daily_cap": entry["cap"]},
    }


@app.get("/api/gateway/log", tags=["session4"])
def gateway_log(request: Request):
    _require_secret(request, "SESSION4_ADMIN_TOKEN")
    with _lock:
        return {"ok": True, "items": list(_gateway_log[-50:])}


@app.post("/api/caller/gateway-smoke", tags=["session4"])
def caller_gateway_smoke(payload: GatewayRelay):
    target_url = os.getenv(
        "SESSION4_GATEWAY_URL",
        "https://substrait-starter--dev.ninjavan.apps.substrait.build/api/gateway/ask",
    )
    gateway_api_key = os.getenv("SESSION4_GATEWAY_API_KEY", "")
    if not gateway_api_key:
        raise HTTPException(status_code=503, detail="SESSION4_GATEWAY_API_KEY is not configured")
    body = json.dumps({"prompt": payload.prompt, "token": payload.token}).encode("utf-8")
    req = urllib.request.Request(
        target_url,
        data=body,
        headers={
            "Authorization": f"Bearer {gateway_api_key}",
            "Content-Type": "application/json",
            "X-Caller-App": os.getenv("SUBSTRAIT_APP_SLUG", "starter-260914-v2"),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return {
                "ok": True,
                "target_status": response.status,
                "target_body": json.loads(response_body),
            }
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:1000]
        return {
            "ok": False,
            "target_status": exc.code,
            "target_body": error_body,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gateway relay failed: {exc}") from exc


@app.get("/api/leads", response_model=List[Lead], tags=["leads"])
def list_leads(search: Optional[str] = Query(None), stage: Optional[str] = Query(None)):
    with _lock:
        items = list(_leads.values())

    if stage and stage in STAGES:
        items = [i for i in items if i.stage == stage]

    if search:
        s = search.lower().strip()
        items = [
            i
            for i in items
            if s in i.name.lower() or s in i.company.lower() or s in i.email.lower()
        ]

    # Return newest updated first
    return sorted(items, key=lambda x: x.updated_at, reverse=True)


@app.post("/api/leads", response_model=Lead, status_code=201, tags=["leads"])
def create_lead(payload: LeadCreate, request: Request):
    author = request.headers.get("X-Forwarded-User", "Sales Rep")
    stage = payload.stage if payload.stage in STAGES else "lead"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lead = Lead(
        name=payload.name.strip(),
        company=payload.company.strip(),
        email=payload.email.strip(),
        phone=payload.phone.strip() if payload.phone else "",
        value=max(0.0, float(payload.value or 0.0)),
        stage=stage,
        created_at=now_str,
        updated_at=now_str,
    )

    if payload.initial_note and payload.initial_note.strip():
        lead.notes.append(
            Note(content=payload.initial_note.strip(), author=author, created_at=now_str)
        )

    with _lock:
        _leads[lead.id] = lead

    return lead


@app.get("/api/leads/{lead_id}", response_model=Lead, tags=["leads"])
def get_lead(lead_id: str):
    with _lock:
        lead = _leads.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@app.put("/api/leads/{lead_id}", response_model=Lead, tags=["leads"])
def update_lead(lead_id: str, payload: LeadUpdate):
    with _lock:
        lead = _leads.get(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        if payload.name is not None:
            lead.name = payload.name.strip()
        if payload.company is not None:
            lead.company = payload.company.strip()
        if payload.email is not None:
            lead.email = payload.email.strip()
        if payload.phone is not None:
            lead.phone = payload.phone.strip()
        if payload.value is not None:
            lead.value = max(0.0, float(payload.value))
        if payload.stage is not None and payload.stage in STAGES:
            lead.stage = payload.stage

        lead.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _leads[lead_id] = lead
        return lead


@app.delete("/api/leads/{lead_id}", tags=["leads"])
def delete_lead(lead_id: str):
    with _lock:
        if lead_id not in _leads:
            raise HTTPException(status_code=404, detail="Lead not found")
        del _leads[lead_id]
    return {"success": True, "id": lead_id}


@app.post("/api/leads/{lead_id}/notes", response_model=Note, status_code=201, tags=["leads"])
def add_note(lead_id: str, payload: NoteCreate, request: Request):
    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=400, detail="Note content cannot be empty")

    author = payload.author or request.headers.get("X-Forwarded-User", "Sales Rep")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    note = Note(content=payload.content.strip(), author=author, created_at=now_str)

    with _lock:
        lead = _leads.get(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        lead.notes.insert(0, note)
        lead.updated_at = now_str

    return note


@app.get("/api/stats", tags=["stats"])
def get_stats():
    with _lock:
        leads = list(_leads.values())

    total = len(leads)
    stage_counts = {s: 0 for s in STAGES}
    stage_values = {s: 0.0 for s in STAGES}

    for l in leads:
        st = l.stage if l.stage in stage_counts else "lead"
        stage_counts[st] += 1
        stage_values[st] += l.value

    active_stages = ["lead", "contacted", "qualified", "proposal"]
    pipeline_val = sum(stage_values[s] for s in active_stages)
    won_val = stage_values["won"]
    closed_total = stage_counts["won"] + stage_counts["lost"]
    win_rate = round((stage_counts["won"] / closed_total * 100), 1) if closed_total > 0 else 0.0

    return {
        "total_leads": total,
        "active_leads": sum(stage_counts[s] for s in active_stages),
        "pipeline_value": round(pipeline_val, 2),
        "won_value": round(won_val, 2),
        "win_rate": win_rate,
        "stage_counts": stage_counts,
        "stage_values": {s: round(v, 2) for s, v in stage_values.items()},
    }


@app.post("/api/reset", tags=["system"])
def reset_data():
    _seed_demo_data()
    return {"message": "Demo data reset successfully"}


# ─────────────────────────────────────────────────────────────────────────────
# Embedded Web UI
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NinjaCRM &bull; Pipeline &amp; Lead Management</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-canvas: #f8fafc;
      --bg-surface: #ffffff;
      --bg-subtle: #f1f5f9;
      --border-main: #e2e8f0;
      --border-focus: #94a3b8;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --text-soft: #94a3b8;
      --brand: #e11d48;
      --brand-hover: #be123c;
      --brand-light: #fff1f2;
      --emerald: #059669;
      --emerald-light: #ecfdf5;
      --blue: #2563eb;
      --blue-light: #eff6ff;
      --amber: #d97706;
      --amber-light: #fffbeb;
      --purple: #7c3aed;
      --purple-light: #f5f3ff;
      --radius: 10px;
      --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
      --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05);
      --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.05);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      background-color: var(--bg-canvas);
      color: var(--text-main);
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Navbar */
    header {
      background: #0f172a;
      color: #f8fafc;
      padding: 0.85rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #1e293b;
      position: sticky;
      top: 0;
      z-index: 40;
    }
    .brand-wrap {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand-logo {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background: linear-gradient(135deg, #e11d48, #f43f5e);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1.1rem;
      color: white;
      box-shadow: 0 2px 6px rgba(225, 29, 72, 0.4);
    }
    .brand-title {
      font-weight: 700;
      font-size: 1.15rem;
      letter-spacing: -0.02em;
    }
    .brand-badge {
      font-size: 0.7rem;
      font-weight: 600;
      background: #1e293b;
      color: #94a3b8;
      padding: 0.15rem 0.5rem;
      border-radius: 9999px;
      margin-left: 0.5rem;
      border: 1px solid #334155;
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .user-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      background: #1e293b;
      padding: 0.35rem 0.85rem;
      border-radius: 9999px;
      font-size: 0.8rem;
      color: #cbd5e1;
      border: 1px solid #334155;
    }
    .user-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10b981;
    }

    /* Main Container */
    main {
      flex: 1;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
      padding: 1.75rem 1.5rem 3rem;
    }

    /* KPI Cards */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin-bottom: 1.75rem;
    }
    .kpi-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: var(--radius);
      padding: 1.2rem 1.25rem;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
    }
    .kpi-label {
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
    }
    .kpi-value {
      font-size: 1.8rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text-main);
    }
    .kpi-sub {
      font-size: 0.78rem;
      color: var(--text-soft);
      margin-top: 0.4rem;
    }

    /* Controls Bar */
    .controls-bar {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: var(--radius);
      padding: 0.85rem 1.2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.5rem;
      box-shadow: var(--shadow-sm);
      flex-wrap: wrap;
    }
    .search-input-wrap {
      display: flex;
      align-items: center;
      position: relative;
      flex: 1;
      min-width: 240px;
      max-width: 400px;
    }
    .search-input-wrap svg {
      position: absolute;
      left: 0.8rem;
      width: 16px;
      height: 16px;
      fill: none;
      stroke: var(--text-muted);
      stroke-width: 2;
    }
    .search-input {
      width: 100%;
      padding: 0.5rem 0.8rem 0.5rem 2.3rem;
      font-size: 0.875rem;
      font-family: inherit;
      border: 1px solid var(--border-main);
      border-radius: 8px;
      background: var(--bg-subtle);
      color: var(--text-main);
      outline: none;
      transition: all 0.15s;
    }
    .search-input:focus {
      background: #fff;
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px rgba(15, 23, 42, 0.06);
    }

    .btn-group {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .btn {
      font-family: inherit;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      padding: 0.5rem 0.95rem;
      font-size: 0.85rem;
      font-weight: 600;
      border-radius: 8px;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.15s ease;
    }
    .btn-primary {
      background: var(--brand);
      color: white;
    }
    .btn-primary:hover {
      background: var(--brand-hover);
    }
    .btn-secondary {
      background: var(--bg-surface);
      color: var(--text-main);
      border-color: var(--border-main);
    }
    .btn-secondary:hover {
      background: var(--bg-subtle);
      border-color: var(--border-focus);
    }
    .view-toggle {
      display: inline-flex;
      background: var(--bg-subtle);
      padding: 3px;
      border-radius: 8px;
      border: 1px solid var(--border-main);
    }
    .view-btn {
      border: none;
      background: transparent;
      padding: 0.35rem 0.75rem;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      color: var(--text-muted);
      transition: all 0.15s;
    }
    .view-btn.active {
      background: white;
      color: var(--text-main);
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* Pipeline Board */
    .pipeline-board {
      display: grid;
      grid-template-columns: repeat(6, minmax(240px, 1fr));
      gap: 1rem;
      overflow-x: auto;
      padding-bottom: 1rem;
      align-items: start;
    }
    .pipeline-col {
      background: var(--bg-subtle);
      border-radius: var(--radius);
      border: 1px solid var(--border-main);
      display: flex;
      flex-direction: column;
      max-height: calc(100vh - 300px);
    }
    .col-header {
      padding: 0.85rem 0.95rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--border-main);
      background: rgba(255, 255, 255, 0.6);
      border-top-left-radius: var(--radius);
      border-top-right-radius: var(--radius);
    }
    .col-title-wrap {
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }
    .col-title {
      font-size: 0.825rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .col-count {
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.1rem 0.45rem;
      border-radius: 9999px;
      background: white;
      border: 1px solid var(--border-main);
      color: var(--text-muted);
    }
    .col-total {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    .col-cards {
      padding: 0.75rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      overflow-y: auto;
      min-height: 120px;
    }

    /* Lead Card */
    .lead-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: 8px;
      padding: 0.85rem;
      box-shadow: var(--shadow-sm);
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .lead-card:hover {
      border-color: var(--brand);
      box-shadow: var(--shadow-md);
      transform: translateY(-1px);
    }
    .lead-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 0.5rem;
    }
    .lead-name {
      font-weight: 700;
      font-size: 0.9rem;
      color: var(--text-main);
    }
    .lead-company {
      font-size: 0.78rem;
      color: var(--text-muted);
    }
    .lead-value {
      font-weight: 700;
      font-size: 0.85rem;
      color: var(--emerald);
      background: var(--emerald-light);
      padding: 0.15rem 0.45rem;
      border-radius: 6px;
      white-space: nowrap;
    }
    .lead-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-top: 1px solid var(--border-main);
      padding-top: 0.5rem;
      margin-top: 0.25rem;
      font-size: 0.75rem;
      color: var(--text-soft);
    }
    .lead-move-btns {
      display: flex;
      gap: 0.25rem;
    }
    .move-btn {
      background: var(--bg-subtle);
      border: 1px solid var(--border-main);
      border-radius: 4px;
      width: 22px;
      height: 22px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 0.75rem;
      cursor: pointer;
      color: var(--text-muted);
      transition: all 0.1s;
    }
    .move-btn:hover {
      background: white;
      border-color: var(--brand);
      color: var(--brand);
    }

    /* Badges */
    .badge {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
      text-transform: capitalize;
    }
    .badge-lead { background: #f1f5f9; color: #475569; }
    .badge-contacted { background: var(--blue-light); color: var(--blue); }
    .badge-qualified { background: var(--amber-light); color: var(--amber); }
    .badge-proposal { background: var(--purple-light); color: var(--purple); }
    .badge-won { background: var(--emerald-light); color: var(--emerald); }
    .badge-lost { background: #fef2f2; color: #dc2626; }

    /* Contacts Table View */
    .table-view-wrap {
      background: var(--bg-surface);
      border: 1px solid var(--border-main);
      border-radius: var(--radius);
      box-shadow: var(--shadow-sm);
      overflow-x: auto;
      display: none;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.85rem;
    }
    th {
      background: var(--bg-subtle);
      padding: 0.75rem 1rem;
      font-weight: 700;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-main);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    td {
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--border-main);
      color: var(--text-main);
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #f8fafc; }

    /* Modal / Drawer */
    .modal-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(2px);
      z-index: 50;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }
    .modal-card {
      background: white;
      border-radius: 12px;
      max-width: 520px;
      width: 100%;
      box-shadow: var(--shadow-lg);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      max-height: 90vh;
      animation: modalPop 0.15s ease-out;
    }
    @keyframes modalPop {
      from { transform: scale(0.96); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
    .modal-header {
      padding: 1.1rem 1.4rem;
      border-bottom: 1px solid var(--border-main);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .modal-title {
      font-size: 1.05rem;
      font-weight: 700;
    }
    .modal-close {
      border: none;
      background: transparent;
      font-size: 1.25rem;
      cursor: pointer;
      color: var(--text-muted);
    }
    .modal-body {
      padding: 1.4rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
    }
    .form-label {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    .form-control {
      font-family: inherit;
      font-size: 0.875rem;
      padding: 0.55rem 0.75rem;
      border: 1px solid var(--border-main);
      border-radius: 6px;
      background: #fff;
      color: var(--text-main);
      outline: none;
    }
    .form-control:focus {
      border-color: var(--brand);
      box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.1);
    }
    .form-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }
    .modal-footer {
      padding: 1rem 1.4rem;
      border-top: 1px solid var(--border-main);
      background: var(--bg-subtle);
      display: flex;
      justify-content: flex-end;
      gap: 0.5rem;
    }

    /* Detail Drawer / Modal for Notes */
    .timeline {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin-top: 0.5rem;
    }
    .timeline-item {
      background: var(--bg-subtle);
      border-radius: 8px;
      padding: 0.75rem;
      font-size: 0.825rem;
      border-left: 3px solid var(--brand);
    }
    .timeline-meta {
      display: flex;
      justify-content: space-between;
      color: var(--text-muted);
      font-size: 0.725rem;
      margin-bottom: 0.25rem;
    }

    /* Toast Notification */
    .toast-container {
      position: fixed;
      bottom: 1.5rem;
      right: 1.5rem;
      z-index: 100;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .toast {
      background: #0f172a;
      color: white;
      padding: 0.75rem 1.1rem;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 500;
      box-shadow: var(--shadow-lg);
      display: flex;
      align-items: center;
      gap: 0.6rem;
      animation: slideIn 0.2s ease-out;
    }
    @keyframes slideIn {
      from { transform: translateY(10px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  </style>
</head>
<body>

<header>
  <div class="brand-wrap">
    <div class="brand-logo">N</div>
    <div>
      <span class="brand-title">NinjaCRM</span>
      <span class="brand-badge">Pipeline Manager</span>
    </div>
  </div>
  <div class="nav-actions">
    <div class="user-pill" id="userPill">
      <div class="user-dot"></div>
      <span id="userName">Connecting...</span>
    </div>
    <button class="btn btn-secondary" onclick="resetDemoData()" title="Reset to demo dataset">Reset Data</button>
    <button class="btn btn-primary" onclick="openCreateModal()">+ Add Lead</button>
  </div>
</header>

<main>
  <!-- KPI Summary -->
  <section class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Active Pipeline</div>
      <div class="kpi-value" id="kpiPipeline">$0</div>
      <div class="kpi-sub">Across open stages</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Won Deals</div>
      <div class="kpi-value" id="kpiWon" style="color: var(--emerald);">$0</div>
      <div class="kpi-sub">Successfully closed</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Active Leads</div>
      <div class="kpi-value" id="kpiActive">0</div>
      <div class="kpi-sub" id="kpiTotalSub">0 total tracked</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Win Rate</div>
      <div class="kpi-value" id="kpiWinRate">0%</div>
      <div class="kpi-sub">Won vs closed lost</div>
    </div>
  </section>

  <!-- Filter & Controls -->
  <section class="controls-bar">
    <div class="search-input-wrap">
      <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
      <input type="text" id="searchInput" class="search-input" placeholder="Search by name, company, or email..." oninput="handleSearch()">
    </div>
    <div class="btn-group">
      <div class="view-toggle">
        <button class="view-btn active" id="btnViewBoard" onclick="switchView('board')">Pipeline Board</button>
        <button class="view-btn" id="btnViewTable" onclick="switchView('table')">Contacts Table</button>
      </div>
    </div>
  </section>

  <!-- Pipeline Kanban Board -->
  <section class="pipeline-board" id="boardView">
    <!-- Lead Column -->
    <div class="pipeline-col" data-stage="lead">
      <div class="col-header">
        <div class="col-title-wrap">
          <span class="col-title">New Leads</span>
          <span class="col-count" id="count-lead">0</span>
        </div>
        <span class="col-total" id="val-lead">$0</span>
      </div>
      <div class="col-cards" id="cards-lead"></div>
    </div>

    <!-- Contacted Column -->
    <div class="pipeline-col" data-stage="contacted">
      <div class="col-header">
        <div class="col-title-wrap">
          <span class="col-title">Contacted</span>
          <span class="col-count" id="count-contacted">0</span>
        </div>
        <span class="col-total" id="val-contacted">$0</span>
      </div>
      <div class="col-cards" id="cards-contacted"></div>
    </div>

    <!-- Qualified Column -->
    <div class="pipeline-col" data-stage="qualified">
      <div class="col-header">
        <div class="col-title-wrap">
          <span class="col-title">Qualified</span>
          <span class="col-count" id="count-qualified">0</span>
        </div>
        <span class="col-total" id="val-qualified">$0</span>
      </div>
      <div class="col-cards" id="cards-qualified"></div>
    </div>

    <!-- Proposal Column -->
    <div class="pipeline-col" data-stage="proposal">
      <div class="col-header">
        <div class="col-title-wrap">
          <span class="col-title">Proposal Sent</span>
          <span class="col-count" id="count-proposal">0</span>
        </div>
        <span class="col-total" id="val-proposal">$0</span>
      </div>
      <div class="col-cards" id="cards-proposal"></div>
    </div>

    <!-- Won Column -->
    <div class="pipeline-col" data-stage="won">
      <div class="col-header">
        <div class="col-title-wrap">
          <span class="col-title">Closed Won</span>
          <span class="col-count" id="count-won">0</span>
        </div>
        <span class="col-total" id="val-won">$0</span>
      </div>
      <div class="col-cards" id="cards-won"></div>
    </div>

    <!-- Lost Column -->
    <div class="pipeline-col" data-stage="lost">
      <div class="col-header">
        <div class="col-title-wrap">
          <span class="col-title">Closed Lost</span>
          <span class="col-count" id="count-lost">0</span>
        </div>
        <span class="col-total" id="val-lost">$0</span>
      </div>
      <div class="col-cards" id="cards-lost"></div>
    </div>
  </section>

  <!-- Table View -->
  <section class="table-view-wrap" id="tableView">
    <table>
      <thead>
        <tr>
          <th>Lead / Contact</th>
          <th>Company</th>
          <th>Stage</th>
          <th>Deal Value</th>
          <th>Contact Info</th>
          <th>Last Update</th>
          <th style="text-align: right;">Actions</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </section>
</main>

<!-- Create Lead Modal -->
<div class="modal-backdrop" id="createModal">
  <div class="modal-card">
    <div class="modal-header">
      <h3 class="modal-title">Create New Lead</h3>
      <button class="modal-close" onclick="closeModal('createModal')">&times;</button>
    </div>
    <form id="createLeadForm" onsubmit="handleCreateLead(event)">
      <div class="modal-body">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Contact Name *</label>
            <input type="text" id="newLeadName" class="form-control" required placeholder="e.g. Rachel Koh">
          </div>
          <div class="form-group">
            <label class="form-label">Company Name *</label>
            <input type="text" id="newLeadCompany" class="form-control" required placeholder="e.g. Apex Logistics">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Email Address *</label>
            <input type="email" id="newLeadEmail" class="form-control" required placeholder="rachel@apex.com">
          </div>
          <div class="form-group">
            <label class="form-label">Phone Number</label>
            <input type="text" id="newLeadPhone" class="form-control" placeholder="+65 9123 4567">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Deal Value ($ SGD)</label>
            <input type="number" step="100" min="0" id="newLeadValue" class="form-control" placeholder="15000">
          </div>
          <div class="form-group">
            <label class="form-label">Pipeline Stage</label>
            <select id="newLeadStage" class="form-control">
              <option value="lead">New Lead</option>
              <option value="contacted">Contacted</option>
              <option value="qualified">Qualified</option>
              <option value="proposal">Proposal Sent</option>
              <option value="won">Closed Won</option>
              <option value="lost">Closed Lost</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Initial Note or Context</label>
          <textarea id="newLeadNote" class="form-control" rows="3" placeholder="Key prospect requirements or source of inquiry..."></textarea>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" onclick="closeModal('createModal')">Cancel</button>
        <button type="submit" class="btn btn-primary">Create Lead</button>
      </div>
    </form>
  </div>
</div>

<!-- Lead Detail & Notes Modal -->
<div class="modal-backdrop" id="detailModal">
  <div class="modal-card">
    <div class="modal-header">
      <div>
        <h3 class="modal-title" id="detailName">Lead Details</h3>
        <p style="font-size: 0.8rem; color: var(--text-muted);" id="detailCompany"></p>
      </div>
      <button class="modal-close" onclick="closeModal('detailModal')">&times;</button>
    </div>
    <div class="modal-body">
      <!-- Quick Stage Switcher -->
      <div class="form-row" style="background: var(--bg-subtle); padding: 0.75rem; border-radius: 8px;">
        <div class="form-group">
          <label class="form-label">Update Stage</label>
          <select id="detailStageSelect" class="form-control" onchange="updateLeadStageFromDetail(this.value)">
            <option value="lead">New Lead</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="proposal">Proposal Sent</option>
            <option value="won">Closed Won</option>
            <option value="lost">Closed Lost</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Deal Value ($ SGD)</label>
          <input type="number" id="detailValueInput" class="form-control" onchange="updateLeadValueFromDetail(this.value)">
        </div>
      </div>

      <div style="font-size: 0.85rem; color: var(--text-muted); display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
        <div><strong>Email:</strong> <span id="detailEmail"></span></div>
        <div><strong>Phone:</strong> <span id="detailPhone"></span></div>
      </div>

      <hr style="border: 0; border-top: 1px solid var(--border-main);">

      <!-- Add Note -->
      <div class="form-group">
        <label class="form-label">Add Note / Interaction Log</label>
        <div style="display: flex; gap: 0.5rem;">
          <input type="text" id="newNoteInput" class="form-control" placeholder="Log call notes, email updates, or next steps..." onkeydown="if(event.key==='Enter'){event.preventDefault();submitNewNote();}">
          <button class="btn btn-primary" onclick="submitNewNote()">Add</button>
        </div>
      </div>

      <!-- Notes History -->
      <div>
        <div class="form-label">Activity &amp; Notes History</div>
        <div class="timeline" id="detailNotesList"></div>
      </div>
    </div>
    <div class="modal-footer" style="justify-content: space-between;">
      <button type="button" class="btn btn-secondary" style="color: #dc2626; border-color: #fecaca;" onclick="handleDeleteCurrentLead()">Delete Lead</button>
      <button type="button" class="btn btn-secondary" onclick="closeModal('detailModal')">Close</button>
    </div>
  </div>
</div>

<div class="toast-container" id="toastContainer"></div>

<script>
  let allLeads = [];
  let currentActiveLeadId = null;
  const STAGES = ["lead", "contacted", "qualified", "proposal", "won", "lost"];
  const STAGE_LABELS = {
    lead: "New Lead",
    contacted: "Contacted",
    qualified: "Qualified",
    proposal: "Proposal Sent",
    won: "Closed Won",
    lost: "Closed Lost"
  };

  function showToast(msg) {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 200);
    }, 2500);
  }

  function formatCurrency(val) {
    return new Intl.NumberFormat('en-SG', { style: 'currency', currency: 'SGD', maximumFractionDigits: 0 }).format(val || 0);
  }

  async function loadUserInfo() {
    try {
      const res = await fetch("/api/info");
      if (res.ok) {
        const data = await res.json();
        document.getElementById("userName").textContent = data.user ? data.user.name : "Sales Rep";
      }
    } catch (e) {
      document.getElementById("userName").textContent = "Local Session";
    }
  }

  async function refreshData() {
    try {
      const [leadsRes, statsRes] = await Promise.all([
        fetch("/api/leads"),
        fetch("/api/stats")
      ]);
      if (leadsRes.ok) {
        allLeads = await leadsRes.json();
        renderLeads();
      }
      if (statsRes.ok) {
        const stats = await statsRes.json();
        renderStats(stats);
      }
    } catch (err) {
      console.error("Failed to load data:", err);
    }
  }

  function renderStats(stats) {
    document.getElementById("kpiPipeline").textContent = formatCurrency(stats.pipeline_value);
    document.getElementById("kpiWon").textContent = formatCurrency(stats.won_value);
    document.getElementById("kpiActive").textContent = stats.active_leads;
    document.getElementById("kpiTotalSub").textContent = `${stats.total_leads} total tracked`;
    document.getElementById("kpiWinRate").textContent = `${stats.win_rate}%`;

    STAGES.forEach(st => {
      const countEl = document.getElementById(`count-${st}`);
      const valEl = document.getElementById(`val-${st}`);
      if (countEl) countEl.textContent = stats.stage_counts[st] || 0;
      if (valEl) valEl.textContent = formatCurrency(stats.stage_values[st] || 0);
    });
  }

  function renderLeads() {
    const query = (document.getElementById("searchInput").value || "").toLowerCase().trim();
    const filtered = allLeads.filter(l => {
      if (!query) return true;
      return l.name.toLowerCase().includes(query) ||
             l.company.toLowerCase().includes(query) ||
             l.email.toLowerCase().includes(query);
    });

    // Clear board columns
    STAGES.forEach(st => {
      const container = document.getElementById(`cards-${st}`);
      if (container) container.innerHTML = "";
    });

    // Render cards on board
    filtered.forEach(lead => {
      const col = document.getElementById(`cards-${lead.stage}`);
      if (col) {
        col.appendChild(createLeadCard(lead));
      }
    });

    // Render table rows
    const tbody = document.getElementById("tableBody");
    tbody.innerHTML = "";
    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No leads match your search criteria.</td></tr>`;
    } else {
      filtered.forEach(lead => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>
            <strong>${escapeHtml(lead.name)}</strong>
          </td>
          <td>${escapeHtml(lead.company)}</td>
          <td><span class="badge badge-${lead.stage}">${STAGE_LABELS[lead.stage] || lead.stage}</span></td>
          <td><strong style="color: var(--emerald);">${formatCurrency(lead.value)}</strong></td>
          <td style="font-size: 0.8rem; color: var(--text-muted);">
            ${escapeHtml(lead.email)}${lead.phone ? ` &bull; ${escapeHtml(lead.phone)}` : ""}
          </td>
          <td style="font-size: 0.75rem; color: var(--text-soft);">${escapeHtml(lead.updated_at)}</td>
          <td style="text-align: right;">
            <button class="btn btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" onclick="openDetailModal('${lead.id}')">View / Notes</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  }

  function createLeadCard(lead) {
    const card = document.createElement("div");
    card.className = "lead-card";
    card.onclick = (e) => {
      if (e.target.closest('.move-btn')) return;
      openDetailModal(lead.id);
    };

    const currentIdx = STAGES.indexOf(lead.stage);
    const prevStage = currentIdx > 0 ? STAGES[currentIdx - 1] : null;
    const nextStage = currentIdx < STAGES.length - 1 ? STAGES[currentIdx + 1] : null;

    card.innerHTML = `
      <div class="lead-header">
        <div>
          <div class="lead-name">${escapeHtml(lead.name)}</div>
          <div class="lead-company">${escapeHtml(lead.company)}</div>
        </div>
        <div class="lead-value">${formatCurrency(lead.value)}</div>
      </div>
      <div class="lead-footer">
        <span>${lead.notes.length} note${lead.notes.length === 1 ? '' : 's'}</span>
        <div class="lead-move-btns">
          ${prevStage ? `<button class="move-btn" title="Move to ${STAGE_LABELS[prevStage]}" onclick="moveLeadStage('${lead.id}', '${prevStage}')">&larr;</button>` : ''}
          ${nextStage ? `<button class="move-btn" title="Move to ${STAGE_LABELS[nextStage]}" onclick="moveLeadStage('${lead.id}', '${nextStage}')">&rarr;</button>` : ''}
        </div>
      </div>
    `;
    return card;
  }

  async function moveLeadStage(id, newStage) {
    try {
      const res = await fetch(`/api/leads/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: newStage })
      });
      if (res.ok) {
        showToast(`Moved to ${STAGE_LABELS[newStage]}`);
        refreshData();
      }
    } catch (e) {
      showToast("Error moving lead stage");
    }
  }

  function handleSearch() {
    renderLeads();
  }

  function switchView(view) {
    const board = document.getElementById("boardView");
    const table = document.getElementById("tableView");
    const btnB = document.getElementById("btnViewBoard");
    const btnT = document.getElementById("btnViewTable");

    if (view === "board") {
      board.style.display = "grid";
      table.style.display = "none";
      btnB.classList.add("active");
      btnT.classList.remove("active");
    } else {
      board.style.display = "none";
      table.style.display = "block";
      btnB.classList.remove("active");
      btnT.classList.add("active");
    }
  }

  function openCreateModal() {
    document.getElementById("createLeadForm").reset();
    document.getElementById("createModal").style.display = "flex";
  }

  function closeModal(id) {
    document.getElementById(id).style.display = "none";
  }

  async function handleCreateLead(e) {
    e.preventDefault();
    const payload = {
      name: document.getElementById("newLeadName").value.trim(),
      company: document.getElementById("newLeadCompany").value.trim(),
      email: document.getElementById("newLeadEmail").value.trim(),
      phone: document.getElementById("newLeadPhone").value.trim(),
      value: parseFloat(document.getElementById("newLeadValue").value) || 0.0,
      stage: document.getElementById("newLeadStage").value,
      initial_note: document.getElementById("newLeadNote").value.trim() || null
    };

    try {
      const res = await fetch("/api/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        closeModal("createModal");
        showToast("Lead added successfully!");
        refreshData();
      } else {
        const err = await res.json();
        alert(err.detail || "Error creating lead");
      }
    } catch (err) {
      alert("Network error creating lead");
    }
  }

  function openDetailModal(id) {
    const lead = allLeads.find(l => l.id === id);
    if (!lead) return;

    currentActiveLeadId = id;
    document.getElementById("detailName").textContent = lead.name;
    document.getElementById("detailCompany").textContent = lead.company;
    document.getElementById("detailEmail").textContent = lead.email || "-";
    document.getElementById("detailPhone").textContent = lead.phone || "-";
    document.getElementById("detailStageSelect").value = lead.stage;
    document.getElementById("detailValueInput").value = lead.value;

    renderNotes(lead.notes);
    document.getElementById("detailModal").style.display = "flex";
  }

  function renderNotes(notes) {
    const container = document.getElementById("detailNotesList");
    container.innerHTML = "";
    if (!notes || notes.length === 0) {
      container.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-soft); font-style: italic;">No notes recorded yet.</p>`;
      return;
    }
    notes.forEach(n => {
      const item = document.createElement("div");
      item.className = "timeline-item";
      item.innerHTML = `
        <div class="timeline-meta">
          <span><strong>${escapeHtml(n.author || "Sales Rep")}</strong></span>
          <span>${escapeHtml(n.created_at)}</span>
        </div>
        <div>${escapeHtml(n.content)}</div>
      `;
      container.appendChild(item);
    });
  }

  async function updateLeadStageFromDetail(newStage) {
    if (!currentActiveLeadId) return;
    try {
      const res = await fetch(`/api/leads/${currentActiveLeadId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: newStage })
      });
      if (res.ok) {
        showToast(`Stage updated to ${STAGE_LABELS[newStage]}`);
        refreshData();
      }
    } catch (e) {
      showToast("Error updating stage");
    }
  }

  async function updateLeadValueFromDetail(val) {
    if (!currentActiveLeadId) return;
    try {
      const res = await fetch(`/api/leads/${currentActiveLeadId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: parseFloat(val) || 0.0 })
      });
      if (res.ok) {
        showToast("Deal value updated");
        refreshData();
      }
    } catch (e) {
      showToast("Error updating deal value");
    }
  }

  async function submitNewNote() {
    const input = document.getElementById("newNoteInput");
    const content = input.value.trim();
    if (!content || !currentActiveLeadId) return;

    try {
      const res = await fetch(`/api/leads/${currentActiveLeadId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content })
      });
      if (res.ok) {
        input.value = "";
        showToast("Note added");
        // Reload lead and update notes
        const leadRes = await fetch(`/api/leads/${currentActiveLeadId}`);
        if (leadRes.ok) {
          const updatedLead = await leadRes.json();
          renderNotes(updatedLead.notes);
          refreshData();
        }
      }
    } catch (e) {
      showToast("Error adding note");
    }
  }

  async function handleDeleteCurrentLead() {
    if (!currentActiveLeadId) return;
    if (!confirm("Are you sure you want to delete this lead?")) return;

    try {
      const res = await fetch(`/api/leads/${currentActiveLeadId}`, { method: "DELETE" });
      if (res.ok) {
        closeModal("detailModal");
        showToast("Lead deleted");
        refreshData();
      }
    } catch (e) {
      showToast("Error deleting lead");
    }
  }

  async function resetDemoData() {
    if (!confirm("Reset all leads back to demo data?")) return;
    try {
      const res = await fetch("/api/reset", { method: "POST" });
      if (res.ok) {
        showToast("Demo data restored");
        refreshData();
      }
    } catch (e) {
      showToast("Error resetting data");
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/[&<>"']/g, function(m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  // Initial load
  loadUserInfo();
  refreshData();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def homepage():
    return HTML_TEMPLATE
