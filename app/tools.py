from __future__ import annotations

from typing import Any

import pandas as pd

from .ingest import load_hr_frame
from .vectorstore import VectorStore

_EMPLOYEES: VectorStore | None = None
_POLICIES: VectorStore | None = None
_HR: pd.DataFrame | None = None

PERF_MULT = {
    "Exceeds": 1.25,
    "Fully Meets": 1.00,
    "Needs Improvement": 0.50,
    "PIP": 0.00,
}

BONUS_TARGET = {
    "executive office": 0.25,
    "production manager": 0.10,
    "software engineer": 0.12,
    "sr. dba": 0.12,
    "enterprise architect": 0.12,
    "data analyst": 0.12,
    "database administrator": 0.12,
    "it support": 0.10,
    "sr. accountant": 0.10,
    "accountant": 0.10,
}


def get_stores() -> tuple[VectorStore, VectorStore]:
    global _EMPLOYEES, _POLICIES
    if _EMPLOYEES is None:
        _EMPLOYEES = VectorStore("employees").load()
    if _POLICIES is None:
        _POLICIES = VectorStore("policies").load()
    return _EMPLOYEES, _POLICIES


def get_hr() -> pd.DataFrame:
    global _HR
    if _HR is None:
        _HR = load_hr_frame()
    return _HR


def search_policies(query: str, k: int = 5) -> list[dict[str, Any]]:
    _, policies = get_stores()
    return policies.search(query, k=k)


def search_employees(query: str, k: int = 6) -> list[dict[str, Any]]:
    employees, _ = get_stores()
    return employees.search(query, k=k)


def find_employee(empid: int) -> dict[str, Any] | None:
    df = get_hr()
    match = df[df["EmpID"] == empid]
    if match.empty:
        return None
    row = match.iloc[0]
    return {k: _jsonable(row[k]) for k in df.columns}


def _jsonable(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def bonus_target_for_position(position: str, department: str) -> float:
    pos = (position or "").strip().lower()
    dept = (department or "").strip().lower()
    if dept == "executive office":
        return 0.25
    for key, pct in BONUS_TARGET.items():
        if key in pos:
            return pct
    if "technician" in pos:
        return 0.08
    if "manager" in pos:
        return 0.18
    return 0.10


def estimate_bonus(record: dict[str, Any]) -> dict[str, Any]:
    salary = float(record.get("Salary") or 0)
    perf = str(record.get("PerformanceScore") or "")
    absences = float(record.get("Absences") or 0)
    engagement = float(record.get("EngagementSurvey") or 0)
    projects = float(record.get("SpecialProjectsCount") or 0)
    target = bonus_target_for_position(str(record.get("Position")), str(record.get("Department")))
    mult = PERF_MULT.get(perf, 0.0)
    if absences > 18:
        mult *= 0.75
    elif absences > 12:
        mult *= 0.90
    if engagement >= 4.5 and projects >= 3:
        mult = min(mult + 0.05, 1.35)
    funding = 1.0
    amount = round(salary * target * funding * mult, 2)
    eligible = perf != "PIP" and str(record.get("EmploymentStatus")) == "Active"
    return {
        "eligible": eligible,
        "target_percent": target,
        "performance_multiplier": round(mult, 3),
        "assumed_company_funding": funding,
        "estimated_annual_bonus_usd": amount if eligible else 0,
        "notes": "Estimate uses policy formula with 100% company funding. Official letter is issued in February.",
    }


LEAVE_ENTITLEMENT = {"privilege": 21, "casual": 8, "sick": 12}


def leave_entitlement(record: dict[str, Any]) -> dict[str, Any]:
    absences = float(record.get("Absences") or 0)
    total = sum(LEAVE_ENTITLEMENT.values())
    return {
        "privilege_days": LEAVE_ENTITLEMENT["privilege"],
        "casual_days": LEAVE_ENTITLEMENT["casual"],
        "sick_days": LEAVE_ENTITLEMENT["sick"],
        "total_annual_days": total,
        "unplanned_absences_on_file": int(absences),
        "leave_year_start": "1 April",
    }


def filter_employees(
    department: str | None = None,
    performance: str | None = None,
    status: str | None = None,
    min_absences: int | None = None,
    max_absences: int | None = None,
    min_salary: float | None = None,
    max_salary: float | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    df = get_hr()
    view = df
    if department:
        view = view[view["Department"].str.lower() == department.strip().lower()]
    if performance:
        view = view[view["PerformanceScore"].str.lower() == performance.strip().lower()]
    if status:
        view = view[view["EmploymentStatus"].str.lower() == status.strip().lower()]
    if min_absences is not None:
        view = view[view["Absences"] >= min_absences]
    if max_absences is not None:
        view = view[view["Absences"] <= max_absences]
    if min_salary is not None:
        view = view[view["Salary"] >= min_salary]
    if max_salary is not None:
        view = view[view["Salary"] <= max_salary]
    cols = [
        "Employee_Name",
        "EmpID",
        "Department",
        "Position",
        "Salary",
        "EmploymentStatus",
        "PerformanceScore",
        "ManagerName",
        "Absences",
        "EngagementSurvey",
        "EmpSatisfaction",
        "SpecialProjectsCount",
        "DateofHire",
    ]
    records = view[cols].head(limit).to_dict(orient="records")
    return [{k: _jsonable(v) for k, v in rec.items()} for rec in records]


def workforce_stats() -> dict[str, Any]:
    df = get_hr()
    active = df[df["EmploymentStatus"] == "Active"]
    dept = (
        df.groupby("Department")
        .agg(
            headcount=("EmpID", "count"),
            active=("EmploymentStatus", lambda s: int((s == "Active").sum())),
            avg_salary=("Salary", "mean"),
            avg_absences=("Absences", "mean"),
            avg_engagement=("EngagementSurvey", "mean"),
        )
        .reset_index()
    )
    dept["avg_salary"] = dept["avg_salary"].round(0)
    dept["avg_absences"] = dept["avg_absences"].round(2)
    dept["avg_engagement"] = dept["avg_engagement"].round(2)
    perf = df["PerformanceScore"].value_counts().to_dict()
    return {
        "total_employees": int(len(df)),
        "active": int(len(active)),
        "terminated": int((df["Termd"] == 1).sum()),
        "avg_salary": round(float(df["Salary"].mean()), 0),
        "avg_salary_active": round(float(active["Salary"].mean()), 0) if len(active) else 0,
        "attrition_rate": round(float((df["Termd"] == 1).mean() * 100), 1),
        "departments": dept.to_dict(orient="records"),
        "performance_mix": {str(k): int(v) for k, v in perf.items()},
    }


def promotion_candidates(department: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
    df = get_hr()
    view = df[
        (df["EmploymentStatus"] == "Active")
        & (df["PerformanceScore"].isin(["Exceeds", "Fully Meets"]))
        & (df["EngagementSurvey"] >= 3.5)
        & (df["Absences"] <= 12)
    ].copy()
    if department:
        view = view[view["Department"].str.lower() == department.strip().lower()]
    view["score"] = (
        view["PerformanceScore"].map({"Exceeds": 2, "Fully Meets": 1}).fillna(0)
        + view["EngagementSurvey"]
        + view["EmpSatisfaction"]
        + view["SpecialProjectsCount"] * 0.3
        - view["Absences"] * 0.05
    )
    view = view.sort_values("score", ascending=False).head(limit)
    cols = [
        "Employee_Name",
        "EmpID",
        "Department",
        "Position",
        "Salary",
        "PerformanceScore",
        "EngagementSurvey",
        "EmpSatisfaction",
        "SpecialProjectsCount",
        "Absences",
        "ManagerName",
    ]
    out = view[cols].to_dict(orient="records")
    return [{k: _jsonable(v) for k, v in rec.items()} for rec in out]


def hr_directory(limit: int = 400) -> list[dict[str, Any]]:
    df = get_hr()
    cols = [
        "Employee_Name",
        "EmpID",
        "Department",
        "Position",
        "Salary",
        "EmploymentStatus",
        "PerformanceScore",
        "ManagerName",
        "Absences",
        "EngagementSurvey",
        "EmpSatisfaction",
        "SpecialProjectsCount",
        "DateofHire",
        "Sex",
        "State",
        "RecruitmentSource",
    ]
    records = df[cols].head(limit).to_dict(orient="records")
    return [{k: _jsonable(v) for k, v in rec.items()} for rec in records]