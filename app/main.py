from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import tools
from .agent import EMP_PASSWORD, HR_PASSWORD, answer
from .ingest import ingest
from .vectorstore import VectorStore

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

app = FastAPI(title="AIONOS People OS", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, dict[str, Any]] = {}


class LoginBody(BaseModel):
    username: str
    password: str
    role: str = Field(pattern="^(hr|employee)$")


class ChatBody(BaseModel):
    message: str


def current_user(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in required")
    token = authorization.split(" ", 1)[1].strip()
    user = SESSIONS.get(token)
    if not user:
        raise HTTPException(401, "Session expired. Please sign in again.")
    return user


@app.on_event("startup")
def startup() -> None:
    emp = VectorStore("employees")
    pol = VectorStore("policies")
    if not emp.exists() or not pol.exists():
        ingest()
    else:
        emp.load()
        pol.load()


@app.post("/api/login")
def login(body: LoginBody) -> dict[str, Any]:
    role = body.role
    username = body.username.strip()
    if role == "hr":
        if username.lower() not in {"hr", "hr.admin", "people"} or body.password != HR_PASSWORD:
            raise HTTPException(401, "HR credentials were not recognised. Use hr / aionos2026")
        profile = {
            "role": "hr",
            "username": "hr.admin",
            "name": "Priya Menon",
            "title": "Head of People",
            "department": "Admin Offices",
            "empid": None,
        }
    else:
        if body.password != EMP_PASSWORD:
            raise HTTPException(401, "Employee password is aionos2026")
        record = None
        if username.isdigit():
            record = tools.find_employee(int(username))
        if record is None:
            df = tools.get_hr()
            key = "".join(ch for ch in username.lower() if ch.isalnum())
            matches = []
            for _, row in df.iterrows():
                compact = "".join(ch for ch in str(row["Employee_Name"]).lower() if ch.isalnum())
                last = str(row["Employee_Name"]).split(",")[0].lower().strip()
                if key and (key in compact or key == last.replace(" ", "")):
                    matches.append(row)
            if matches:
                matches.sort(key=lambda r: 0 if str(r["EmploymentStatus"]) == "Active" else 1)
                record = tools.find_employee(int(matches[0]["EmpID"]))
        if record is None:
            raise HTTPException(
                401,
                "Use an EmpID from the HR file (try 10002) or a last name such as Anderson, password aionos2026",
            )
        if str(record.get("EmploymentStatus")) != "Active":
            raise HTTPException(403, "Only active employees can open the employee portal in this demo.")
        profile = {
            "role": "employee",
            "username": str(int(record["EmpID"])),
            "name": record["Employee_Name"],
            "title": record["Position"],
            "department": record["Department"],
            "empid": int(record["EmpID"]),
        }
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = profile
    return {"token": token, "user": profile}


@app.get("/api/me")
def get_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return {"user": current_user(authorization)}


@app.get("/api/hr/overview")
def hr_overview(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = current_user(authorization)
    if user["role"] != "hr":
        raise HTTPException(403, "HR only")
    stats = tools.workforce_stats()
    stats["candidates"] = tools.promotion_candidates(limit=8)
    stats["pip"] = tools.filter_employees(performance="PIP", status="Active")
    stats["high_absence"] = tools.filter_employees(min_absences=15, status="Active", limit=8)
    return stats


@app.get("/api/hr/employees")
def hr_employees(
    authorization: str | None = Header(default=None), department: str | None = None
) -> dict[str, Any]:
    user = current_user(authorization)
    if user["role"] != "hr":
        raise HTTPException(403, "HR only")
    rows = tools.filter_employees(department=department, limit=400) if department else tools.hr_directory()
    return {"employees": rows}


@app.get("/api/employee/home")
def employee_home(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = current_user(authorization)
    if user["role"] != "employee":
        raise HTTPException(403, "Employee only")
    record = tools.find_employee(int(user["empid"]))
    if not record:
        raise HTTPException(404, "Profile missing")
    leave_used = int(record.get("Absences") or 0)
    return {
        "profile": {
            "name": record["Employee_Name"],
            "empid": int(record["EmpID"]),
            "position": record["Position"],
            "department": record["Department"],
            "manager": record["ManagerName"],
            "salary": record["Salary"],
            "performance": record["PerformanceScore"],
            "engagement": record["EngagementSurvey"],
            "satisfaction": record["EmpSatisfaction"],
            "projects": record["SpecialProjectsCount"],
            "absences": record["Absences"],
            "hire_date": record["DateofHire"],
            "status": record["EmploymentStatus"],
        },
        "bonus": tools.estimate_bonus(record),
        "leave": {
            "privilege_accrual": 21,
            "casual": 8,
            "sick": 12,
            "unplanned_absences_on_file": leave_used,
            "attendance_note": (
                "Unplanned absences above 12 reduce bonus multiplier by 10%; above 18 reduce it by 25%."
                if leave_used > 12
                else "Your unplanned absence count is within the bonus-safe range (12 or fewer)."
            ),
        },
        "policies": [
            {"id": "leave", "title": "Leave", "blurb": "21 PL, 8 casual, 12 sick. Leave year starts 1 April."},
            {"id": "bonus", "title": "Bonus", "blurb": "Annual payout 15 March. PIP is ineligible."},
            {"id": "raise", "title": "Raises", "blurb": "Merit cycle effective 1 April. Exceeds: 8–12%."},
            {"id": "promotion", "title": "Promotions", "blurb": "Windows in March–April and September."},
            {"id": "partners", "title": "Partners", "blurb": "Helix Health, Northstar Life, LearnGrid, PayOrbit."},
        ],
    }


@app.post("/api/chat")
def chat(body: ChatBody, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = current_user(authorization)
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(400, "Message required")
    return answer(message, user)


@app.post("/api/ingest")
def run_ingest(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = current_user(authorization)
    if user["role"] != "hr":
        raise HTTPException(403, "HR only")
    counts = ingest()
    return {"ok": True, "indexed": counts}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
