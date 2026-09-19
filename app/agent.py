from __future__ import annotations

import re
from typing import Any

from . import tools

HR_PASSWORD = "aionos2026"
EMP_PASSWORD = "aionos2026"

DEPTS = {
    "production": "Production",
    "it/is": "IT/IS",
    "sales": "Sales",
    "software engineering": "Software Engineering",
    "admin offices": "Admin Offices",
    "executive office": "Executive Office",
}

PERF_LABELS = ["exceeds", "fully meets", "needs improvement", "pip"]


def _contains(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


POLICY_INTENTS = {
    "leave": [
        "leave", "absence", "casual", "sick", "privilege", "pl", "cl", "holiday", "parental",
        "bereavement", "remaining", "days left", "days off", "work days", "workdays", "time off",
        "pto", "vacation", "leave balance",
    ],
    "bonus": ["bonus", "payout", "variable pay", "spot bonus", "referral"],
    "raise": ["raise", "merit", "salary review", "compensation cycle", "pay increase"],
    "promotion": ["promotion", "promote", "career ladder", "eligibility checklist"],
    "partner": ["partner", "vendor", "insurance", "helix", "learngrid", "payroll", "benefits"],
}

LEAVE_BALANCE_HINTS = [
    "remaining", "days left", "how many days", "days do i have", "days off", "work days",
    "workdays", "time off", "pto", "vacation", "leave balance", "how much leave",
]


def _policy_queries(query: str) -> list[str]:
    q = query.lower()
    matched = [name for name, keys in POLICY_INTENTS.items() if any(k in q for k in keys)]
    if not matched:
        return [query]
    expanded = {
        "leave": "AIONOS casual leave sick leave privilege leave days notice",
        "bonus": "AIONOS annual bonus payout date 15 March eligibility PIP",
        "raise": "AIONOS merit increase April compensation review bands",
        "promotion": "AIONOS promotion eligibility windows March September",
        "partner": "AIONOS benefits partners Helix Northstar LearnGrid PayOrbit",
    }
    return [expanded[name] + " " + query for name in matched]


def plan(query: str, role: str) -> list[dict[str, Any]]:
    q = query.lower().strip()
    steps: list[dict[str, Any]] = []

    dept = next((name for key, name in DEPTS.items() if key in q), None)
    perf = next((p for p in PERF_LABELS if p in q), None)

    empid_match = re.search(r"\b(100\d{2}|101\d{2}|102\d{2})\b", q)
    if not empid_match:
        empid_match = re.search(r"\bempid\s*[:=]?\s*(\d{4,6})\b", q)
    empid = int(empid_match.group(1)) if empid_match else None

    if role == "hr":
        if _contains(q, "headcount", "attrition", "average salary", "avg salary", "workforce", "dashboard", "department summary", "how many employee"):
            steps.append({"tool": "workforce_stats", "args": {}})
        if _contains(q, "promotion", "high potential", "ready to promote", "promotion candidate"):
            steps.append({"tool": "promotion_candidates", "args": {"department": dept}})
        if empid:
            steps.append({"tool": "get_employee", "args": {"empid": empid}})
        if _contains(q, "absence", "absences", "late", "attendance"):
            min_abs = 12
            m = re.search(r"(?:more than|over|above|>)\s*(\d+)", q)
            if m:
                min_abs = int(m.group(1))
            steps.append(
                {
                    "tool": "filter_employees",
                    "args": {
                        "department": dept,
                        "performance": perf.title() if perf and perf != "pip" else ("PIP" if perf == "pip" else None),
                        "min_absences": min_abs,
                        "status": "Active" if "active" in q else None,
                    },
                }
            )
        if _contains(q, "pip", "needs improvement", "exceeds", "salary between", "who in", "list employee", "find employee", "show me"):
            if not any(s["tool"] == "filter_employees" for s in steps):
                args: dict[str, Any] = {
                    "department": dept,
                    "performance": "PIP" if perf == "pip" else (perf.title() if perf else None),
                    "status": "Active" if "active" in q or "terminated" not in q else None,
                }
                if "terminated" in q:
                    args["status"] = None
                steps.append({"tool": "filter_employees", "args": args})
        if _contains(q, "bonus", "raise", "leave", "promotion policy", "partner", "policy"):
            for pq in _policy_queries(query):
                steps.append({"tool": "search_policies", "args": {"query": pq}})
        if not steps:
            steps.append({"tool": "search_employees", "args": {"query": query}})
            steps.append({"tool": "search_policies", "args": {"query": query}})
        return steps

    # employee
    if _contains(q, "my bonus", "bonus estimate", "how much bonus", "my raise", "my salary", "my performance", "my absence", "my profile", "am i eligible"):
        steps.append({"tool": "my_profile", "args": {}})
    wants_leave_balance = _contains(q, *LEAVE_BALANCE_HINTS)
    if wants_leave_balance:
        # Numeric balance question ("remaining days", "how much leave do I have") - answer with
        # the exact entitlement numbers instead of a raw policy-document dump.
        steps.append({"tool": "leave_status", "args": {}})
    else:
        for pq in _policy_queries(query):
            steps.append({"tool": "search_policies", "args": {"query": pq}})
    return steps


def run_tool(name: str, args: dict[str, Any], user: dict[str, Any]) -> Any:
    if name == "workforce_stats":
        return tools.workforce_stats()
    if name == "promotion_candidates":
        return tools.promotion_candidates(department=args.get("department"))
    if name == "filter_employees":
        return tools.filter_employees(
            department=args.get("department"),
            performance=args.get("performance"),
            status=args.get("status"),
            min_absences=args.get("min_absences"),
            max_absences=args.get("max_absences"),
            min_salary=args.get("min_salary"),
            max_salary=args.get("max_salary"),
        )
    if name == "get_employee":
        return tools.find_employee(int(args["empid"]))
    if name == "search_employees":
        return tools.search_employees(args.get("query", ""), k=6)
    if name == "search_policies":
        return tools.search_policies(args.get("query", ""), k=5)
    if name == "my_profile":
        record = tools.find_employee(int(user["empid"]))
        if not record:
            return None
        return {"profile": record, "bonus_estimate": tools.estimate_bonus(record)}
    if name == "leave_status":
        record = tools.find_employee(int(user["empid"]))
        if not record:
            return None
        return tools.leave_entitlement(record)
    raise ValueError(name)


def _format_hits(hits: list[dict[str, Any]]) -> str:
    blocks = []
    for h in hits:
        meta = h.get("metadata") or {}
        label = meta.get("title") or meta.get("name") or meta.get("source") or "source"
        blocks.append(f"[{label} | {meta.get('heading', meta.get('department', ''))}]\n{h.get('text', '')[:900]}")
    return "\n\n".join(blocks)


def synthesize(query: str, role: str, observations: list[dict[str, Any]], user: dict[str, Any]) -> str:
    q = query.lower()
    parts: list[str] = []

    for obs in observations:
        tool = obs["tool"]
        data = obs["result"]
        if tool == "workforce_stats" and isinstance(data, dict):
            parts.append(
                f"AIONOS workforce snapshot: {data['total_employees']} people on file, "
                f"{data['active']} active, attrition {data['attrition_rate']}%. "
                f"Average salary across the file is ${data['avg_salary']:,.0f} "
                f"(${data['avg_salary_active']:,.0f} for active staff)."
            )
            lines = []
            for row in data.get("departments", []):
                lines.append(
                    f"- {row['Department']}: {row['headcount']} total / {row['active']} active, "
                    f"avg salary ${row['avg_salary']:,.0f}, absences {row['avg_absences']}, engagement {row['avg_engagement']}"
                )
            parts.append("Department breakdown:\n" + "\n".join(lines))
            mix = ", ".join(f"{k}: {v}" for k, v in data.get("performance_mix", {}).items())
            parts.append("Performance mix: " + mix)

        elif tool in {"filter_employees", "promotion_candidates"} and isinstance(data, list):
            if not data:
                parts.append("No employees matched those filters in the HR file.")
            else:
                shown = data[:6]
                header = (
                    f"Top {len(shown)} promotion-ready employees, out of {len(data)} that meet the checklist "
                    "(Active, Fully Meets/Exceeds, engagement ≥ 3.5, absences ≤ 12), ranked by overall fit:"
                    if tool == "promotion_candidates"
                    else f"{len(data)} employee{'s' if len(data) != 1 else ''} matched — showing the top {len(shown)}:"
                )
                rows = []
                for rec in shown:
                    rows.append(
                        f"• {rec['Employee_Name']} — {rec['Position']}, {rec['Department']} (EmpID {rec['EmpID']})\n"
                        f"   ${rec['Salary']:,} · {rec['PerformanceScore']} · {rec['Absences']} absences · manager {rec['ManagerName']}"
                    )
                tail = f"\n…and {len(data) - len(shown)} more matching the same criteria." if len(data) > len(shown) else ""
                parts.append(header + "\n" + "\n".join(rows) + tail)

        elif tool == "get_employee" and isinstance(data, dict):
            parts.append(
                f"{data['Employee_Name']} (EmpID {data['EmpID']}) is a {data['Position']} in {data['Department']} "
                f"reporting to {data['ManagerName']}. Status: {data['EmploymentStatus']}. "
                f"Salary ${data['Salary']:,}. Performance: {data['PerformanceScore']}. "
                f"Engagement {data['EngagementSurvey']}, satisfaction {data['EmpSatisfaction']}, "
                f"special projects {data['SpecialProjectsCount']}, absences {data['Absences']}."
            )
            if _contains(q, "bonus"):
                est = tools.estimate_bonus(data)
                parts.append(
                    f"Policy-based bonus estimate at 100% funding: ${est['estimated_annual_bonus_usd']:,.0f} "
                    f"(target {est['target_percent']*100:.0f}%, multiplier {est['performance_multiplier']}). "
                    f"{est['notes']}"
                )

        elif tool == "my_profile" and isinstance(data, dict):
            rec = data["profile"]
            est = data["bonus_estimate"]
            parts.append(
                f"Your AIONOS profile: {rec['Employee_Name']} (EmpID {rec['EmpID']}), {rec['Position']} "
                f"in {rec['Department']}, manager {rec['ManagerName']}. "
                f"Performance {rec['PerformanceScore']}, engagement {rec['EngagementSurvey']}, "
                f"absences {rec['Absences']}, salary ${rec['Salary']:,}."
            )
            if est["eligible"]:
                parts.append(
                    f"Under the bonus policy (assuming 100% company funding) your estimated annual bonus is "
                    f"${est['estimated_annual_bonus_usd']:,.0f}. Official letters go out the last week of February and pay on 15 March."
                )
            else:
                parts.append("You are not eligible for the annual bonus under current status or PIP rules. Spot bonuses may still apply after a PIP is closed.")

        elif tool == "leave_status" and isinstance(data, dict):
            parts.append(
                f"Your annual leave entitlement: {data['privilege_days']} privilege leave days, "
                f"{data['casual_days']} casual leave days, and {data['sick_days']} sick leave days "
                f"({data['total_annual_days']} days total), on a leave year that starts "
                f"{data['leave_year_start']}. "
                + (
                    f"You currently have {data['unplanned_absences_on_file']} unplanned absences on file this cycle. "
                    "The HR system tracks that as one combined absence count rather than a running balance per leave "
                    "type, so for your exact days remaining, check with your manager or HR."
                    if data["unplanned_absences_on_file"]
                    else "You have no unplanned absences on file this cycle."
                )
            )

        elif tool == "search_policies" and isinstance(data, list):
            if data:
                snippet = _clean_policy_answer(query, data)
                if snippet and snippet not in parts:
                    parts.append(snippet)

        elif tool == "search_employees" and isinstance(data, list) and data:
            if len(data) == 1:
                meta = data[0].get("metadata") or {}
                parts.append(
                    f"{meta.get('name')} (EmpID {meta.get('empid')}) — {meta.get('position')}, "
                    f"{meta.get('department')}, performance {meta.get('performance')}."
                )
            else:
                rows = []
                for h in data[:5]:
                    meta = h.get("metadata") or {}
                    rows.append(f"• {meta.get('name')} (EmpID {meta.get('empid')}) — {meta.get('position')}, {meta.get('department')}, {meta.get('performance')}")
                parts.append("Closest-matching HR records:\n" + "\n".join(rows))

    if not parts:
        if role == "employee":
            return (
                "I can help with AIONOS leave, bonus, raise, promotion, and partner policies, "
                "plus your own profile. Try asking: “How many casual leave days do I get?” or “When is bonus paid?”"
            )
        return "I could not find matching HR records or policy text. Try a department name, EmpID, or a policy topic."

    preface = (
        "HR view. Confidential employee data is included where relevant."
        if role == "hr"
        else f"Employee view for {user.get('name')}. Other employees' records are hidden."
    )
    return preface + "\n\n" + "\n\n".join(parts)


def _clean_policy_text(body: str) -> str:
    # Drop the synthetic ingest preamble.
    body = re.sub(r"^AIONOS company policy document:.*?\n+", "", body, flags=re.S)
    # Drop markdown heading markers ("## Heading" -> "Heading") - the heading is already
    # shown separately, and raw "#" characters read as clutter in a chat bubble.
    body = re.sub(r"(?m)^#{1,6}\s*", "", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def _sentence_trim(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # Prefer to end on a full sentence rather than mid-word/mid-clause.
    end = max(cut.rfind(". "), cut.rfind(".\n"))
    if end > max_chars * 0.4:
        return cut[: end + 1]
    return cut.rstrip() + "…"


def _clean_policy_answer(query: str, hits: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    seen = set()
    ranked = sorted(hits, key=lambda h: -float(h.get("score") or 0))
    # Two focused, well-scored snippets read better than four loosely related ones.
    for hit in ranked[:2]:
        meta = hit.get("metadata") or {}
        key = (meta.get("source"), meta.get("heading"))
        if key in seen:
            continue
        seen.add(key)
        body = _clean_policy_text(hit.get("text", ""))
        heading = meta.get("heading") or meta.get("title") or "Policy"
        title = meta.get("title") or "AIONOS policy"
        # The cleaned body's first line is usually the heading again (from the markdown source) -
        # drop it since it's already shown in the "From ... - heading:" line below.
        first_line, _, rest = body.partition("\n")
        if first_line.strip().lower() == str(heading).strip().lower() and rest.strip():
            body = rest
        blocks.append(f"From {title} - {heading}:\n{_sentence_trim(body, 500)}")
    return "\n\n".join(blocks)


def _trim(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def answer(query: str, user: dict[str, Any]) -> dict[str, Any]:
    role = user["role"]
    steps = plan(query, role)
    observations = []
    traces = []
    for step in steps:
        if role != "hr" and step["tool"] in {
            "workforce_stats",
            "promotion_candidates",
            "filter_employees",
            "search_employees",
            "get_employee",
        }:
            traces.append({"tool": step["tool"], "status": "blocked", "reason": "Employee role cannot access other employees’ data"})
            continue
        result = run_tool(step["tool"], step.get("args") or {}, user)
        observations.append({"tool": step["tool"], "result": result})
        preview = result
        if isinstance(result, list):
            preview = f"{len(result)} rows"
        elif isinstance(result, dict):
            preview = ", ".join(list(result.keys())[:8])
        traces.append({"tool": step["tool"], "status": "ok", "preview": preview, "args": step.get("args")})
    text = synthesize(query, role, observations, user)
    citations = []
    for obs in observations:
        if obs["tool"] in {"search_policies", "search_employees"} and isinstance(obs["result"], list):
            for hit in obs["result"][:4]:
                meta = hit.get("metadata") or {}
                citations.append(
                    {
                        "title": meta.get("title") or meta.get("name"),
                        "heading": meta.get("heading") or meta.get("department"),
                        "score": round(float(hit.get("score") or 0), 3),
                        "audience": meta.get("audience"),
                    }
                )
    return {"answer": text, "trace": traces, "citations": citations, "role": role}