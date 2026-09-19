from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .vectorstore import VectorStore

ROOT = Path(__file__).resolve().parent.parent
HR_CSV = ROOT / "data" / "hr" / "HRDataset_v14.csv"
POLICY_DIR = ROOT / "data" / "policies"


def _chunk_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def chunk_markdown(text: str, source: str, title: str) -> list[dict[str, Any]]:
    parts = re.split(r"\n(?=## )", text.strip())
    chunks: list[dict[str, Any]] = []
    for part in parts:
        part = part.strip()
        if len(part) < 40:
            continue
        heading = part.splitlines()[0].lstrip("# ").strip()
        # Keep retrieval units focused.
        if len(part) > 1400:
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", part) if p.strip()]
            buf = heading + "\n"
            for para in paragraphs:
                if para == heading:
                    continue
                if len(buf) + len(para) > 1100 and len(buf) > 80:
                    chunks.append(_policy_chunk(buf, source, title, heading))
                    buf = heading + "\n" + para + "\n"
                else:
                    buf += para + "\n\n"
            if len(buf) > 80:
                chunks.append(_policy_chunk(buf, source, title, heading))
        else:
            chunks.append(_policy_chunk(part, source, title, heading))
    return chunks


def _policy_chunk(text: str, source: str, title: str, heading: str) -> dict[str, Any]:
    body = f"AIONOS company policy document: {title}. Section: {heading}.\n\n{text.strip()}"
    return {
        "id": _chunk_id("policy", body),
        "text": body,
        "metadata": {
            "collection": "policies",
            "source": source,
            "title": title,
            "heading": heading,
            "audience": "all",
        },
    }


def employee_to_document(row: pd.Series) -> str:
    dept = str(row.get("Department", "")).strip()
    name = str(row.get("Employee_Name", "")).strip()
    status = str(row.get("EmploymentStatus", "")).strip()
    term = row.get("DateofTermination")
    term_txt = "still employed" if pd.isna(term) or str(term).strip() == "" else f"terminated on {term}"
    return (
        f"AIONOS employee HR record.\n"
        f"Name: {name}. Employee ID: {row.get('EmpID')}.\n"
        f"Position: {row.get('Position')} (Position ID {row.get('PositionID')}).\n"
        f"Department: {dept}. Department ID: {row.get('DeptID')}.\n"
        f"Manager: {row.get('ManagerName')} (Manager ID {row.get('ManagerID')}).\n"
        f"Employment status: {status}. Terminated flag: {row.get('Termd')}. Reason: {row.get('TermReason')}. {term_txt}.\n"
        f"Date of hire: {row.get('DateofHire')}. State: {row.get('State')}. Zip: {row.get('Zip')}.\n"
        f"Salary: {row.get('Salary')} USD annual base.\n"
        f"Performance score: {row.get('PerformanceScore')} (PerfScoreID {row.get('PerfScoreID')}).\n"
        f"Last performance review: {row.get('LastPerformanceReview_Date')}.\n"
        f"Engagement survey: {row.get('EngagementSurvey')}. Employee satisfaction: {row.get('EmpSatisfaction')}.\n"
        f"Special projects count: {row.get('SpecialProjectsCount')}.\n"
        f"Absences: {row.get('Absences')}. Days late last 30: {row.get('DaysLateLast30')}.\n"
        f"Recruitment source: {row.get('RecruitmentSource')}. Diversity job fair hire: {row.get('FromDiversityJobFairID')}.\n"
        f"Demographics on file: sex {str(row.get('Sex')).strip()}, marital {row.get('MaritalDesc')}, "
        f"citizenship {row.get('CitizenDesc')}, race {row.get('RaceDesc')}, Hispanic/Latino {row.get('HispanicLatino')}, DOB {row.get('DOB')}.\n"
        f"This record is confidential HR data and must only be shown to HR users."
    )


def load_hr_frame() -> pd.DataFrame:
    df = pd.read_csv(HR_CSV)
    df["Department"] = df["Department"].astype(str).str.strip()
    df["Employee_Name"] = df["Employee_Name"].astype(str).str.strip()
    df["Position"] = df["Position"].astype(str).str.strip()
    df["EmploymentStatus"] = df["EmploymentStatus"].astype(str).str.strip()
    df["PerformanceScore"] = df["PerformanceScore"].astype(str).str.strip()
    df["ManagerName"] = df["ManagerName"].astype(str).str.strip()
    df["EmpID"] = pd.to_numeric(df["EmpID"], errors="coerce").astype("Int64")
    return df


def ingest() -> dict[str, int]:
    df = load_hr_frame()
    emp_chunks: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        text = employee_to_document(row)
        emp_chunks.append(
            {
                "id": f"emp-{row['EmpID']}",
                "text": text,
                "metadata": {
                    "collection": "employees",
                    "empid": str(int(row["EmpID"])),
                    "name": row["Employee_Name"],
                    "department": row["Department"],
                    "position": row["Position"],
                    "status": row["EmploymentStatus"],
                    "performance": row["PerformanceScore"],
                    "audience": "hr",
                },
            }
        )

    policy_chunks: list[dict[str, Any]] = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title = raw.splitlines()[0].lstrip("# ").strip()
        policy_chunks.extend(chunk_markdown(raw, path.name, title))

    VectorStore("employees").build(emp_chunks)
    VectorStore("policies").build(policy_chunks)
    return {"employees": len(emp_chunks), "policies": len(policy_chunks)}
