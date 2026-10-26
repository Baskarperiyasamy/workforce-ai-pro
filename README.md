# WorkForce AI Pro

HR attrition prediction and workforce intelligence platform.
FastAPI + SQLAlchemy + MySQL + JWT on the backend, React (Vite) + Tailwind + Recharts on the frontend, scikit-learn for the prediction engine.

## Run it (VS Code, two terminals)

### 1. MySQL
```sql
CREATE DATABASE workforce_ai;
```
(or run `docs/schema.sql`; the app also creates the tables itself on first start)

### 2. Backend (terminal 1)
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env
```
Edit `.env` and put your MySQL password in `DATABASE_URL`, then set it in the terminal:
```bash
set DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/workforce_ai     # Mac/Linux: export ...
uvicorn app.main:app --reload --port 8000
```
First start creates tables, loads demo data (6 departments, 110 employees, attendance, payroll, leave) and trains the model.
Swagger docs: http://localhost:8000/docs

No MySQL handy? Use SQLite for a quick run: `set DATABASE_URL=sqlite:///./workforce.db`

### 3. Frontend (terminal 2)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

### Demo logins
| Role | Email | Password |
|---|---|---|
| Admin | admin@workforce.ai | Admin@123 |
| HR | hr@workforce.ai | Hr@12345 |
| Manager | manager@workforce.ai | Manager@123 |
| Employee | employee@workforce.ai | Employee@123 |

### Tests
```bash
cd backend
pytest tests -v
```

## Demo the full flow (employee activity to dashboard refresh)
1. Login as employee, Attendance, Check in, enter 14 in "simulate hours", Check out.
2. Overtime is added, the model re-scores the employee, risk change is logged.
3. If risk crosses 70%, HR gets an alert toast (WebSocket), an intervention is opened, the Risk Monitor and dashboard update.

## Module coverage
| Modules | Where |
|---|---|
| 1 Auth (register, login, forgot/reset, session, expiry) | `routes_auth.py`, `core.py`, `Auth` in App.jsx |
| 2, 3 Employees, departments, role assignment, stats | `routes_hr.py` |
| 4 Attendance and overtime | `routes_hr.py` |
| 5 Leave workflow, balances, report | `routes_hr.py` |
| 6 Payroll, tax slabs, bonus, payslip PDF | `routes_hr.py` |
| 7, 8 Notifications, toasts, one-to-one chat, read receipts, WebSocket | `routes_hr.py`, `main.py` |
| 9 Documents | `routes_hr.py` |
| 10 Dashboard | `routes_hr.py`, Dashboard page |
| 11 Dataset upload, versions, duplicate and failed-row report | `routes_ai.py` |
| 12 Prediction engine (risk %, confidence, history) | `ml.py`, `services.py`, `routes_ai.py` |
| 13 Risk monitoring and logs | `services.py`, Risk Monitor page |
| 14, 27 Forecast and stability scoring | `/api/ai/forecast`, Analytics page |
| 15 Attrition analytics | `/api/ai/analytics` |
| 16 Interventions and recommendations | `routes_ai.py`, `services.recommend` |
| 17 Alert priority engine | `services.raise_alert` (HIGH / CRITICAL) |
| 18 Live feed | `/api/ai/feed`, `/ws` |
| 19 Excel and PDF exports | `/api/reports/{kind}` |
| 20 Audit logs | `/api/audit` |
| 24 Multi-filter search | `/api/employees` |
| 25 UI/UX | `App.jsx`, `App.css` |
| 26 RBAC | `core.require`, role-filtered sidebar |
| 28 Optimisation | indexes on all lookup columns, denormalised `employees.risk`, pagination |
| 29 Testing | `backend/tests`, `docs/test-results.txt` |
| 30 Integration | Axios client, context state, toasts, WebSocket refresh |

Not built (listed in Phase 3 of the brief): Module 21 task management, Module 22 performance reviews, Module 23 as a separate engine (employee-level recommendations are covered by Module 16).

## Docs
- `docs/schema.sql` MySQL schema (15 tables)
- `docs/openapi.json` API specification, live version at `/docs`
- `docs/test-results.txt` test run output
