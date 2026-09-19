# AIONOS People OS — Agentic RAG Portal

Internal portal for **AIONOS**. HR and employees share one dashboard shell (AionOS product look) but retrieve **different knowledge**.

| Role | What the assistant can retrieve |
| --- | --- |
| HR | Full employee file (`HRDataset_v14.csv`), workforce analytics, promotion/attendance tools, plus company policies |
| Employee | Company policies (bonus, raise, leave, promotions, partners) and **their own** profile only |

## Run

```powershell
cd C:\Users\tyagi\Desktop\GATE
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

On first start the app **chunks**, **embeds** (TF-IDF vectors), and writes a persistent store under `vector_db/`.

## Demo logins

- HR: `hr` / `aionos2026`
- Employee: EmpID `10002` (Linda Anderson) / `aionos2026`  
  Any **active** EmpID from the CSV also works.

## What was indexed

- 311 employee records as confidential HR documents
- Generated AIONOS policies in `data/policies/`
