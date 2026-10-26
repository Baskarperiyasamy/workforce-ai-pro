import datetime as dt
import io
import os
import uuid
from datetime import date
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from .core import current_user, get_db, now, require, row
from .models import (Attendance, Audit, Department, Document, Employee, Intervention, Leave, Message, MonitorLog,
                     Notification, Payroll, Prediction, User)
from .services import audit, notify, notify_hr, recompute, dept_name_map

router = APIRouter(prefix="/api", tags=["workforce"])
HR = ("ADMIN", "HR")
MGR = ("ADMIN", "HR", "MANAGER")
POLICY = {"ANNUAL": 22, "SICK": 10, "CASUAL": 7}
UPLOADS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}


class EmployeeIn(BaseModel):
    name: str = Field(min_length=2)
    email: EmailStr
    phone: str | None = None
    title: str = "Staff"
    department_id: int | None = None
    salary: float = Field(gt=0)
    hire_date: date | None = None
    status: str = "ACTIVE"
    shift: str = "Morning"
    age: int = Field(30, ge=18, le=70)
    tenure: float = Field(0, ge=0)
    satisfaction: int = Field(3, ge=1, le=4)
    overtime: float = Field(0, ge=0)
    performance: int = Field(3, ge=1, le=5)
    absences: int = Field(0, ge=0)
    promo_gap: float = Field(0, ge=0)


class DeptIn(BaseModel):
    name: str = Field(min_length=2)
    description: str | None = None


class RoleIn(BaseModel):
    role: str = Field(pattern="^(ADMIN|HR|MANAGER|EMPLOYEE)$")


class EmpRef(BaseModel):
    employee_id: int | None = None


class LeaveIn(BaseModel):
    employee_id: int | None = None
    kind: str = Field(pattern="^(ANNUAL|SICK|CASUAL)$")
    start: date
    end: date
    reason: str | None = None


class Decision(BaseModel):
    status: str = Field(pattern="^(APPROVED|REJECTED)$")


class PayrollIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    bonus_pct: float = Field(0, ge=0, le=100)


class MsgIn(BaseModel):
    to: int
    body: str = Field(min_length=1, max_length=2000)


def emp_of(user, explicit=None):
    eid = explicit if explicit and user.role in MGR else user.employee_id
    if not eid:
        raise HTTPException(400, "No employee profile linked to this account")
    return eid


@router.get("/employees")
def list_employees(q: str = "", department_id: int | None = None, status: str | None = None, risk: str | None = None,
                   min_salary: float | None = None, max_salary: float | None = None, page: int = 1, size: int = 50,
                   db=Depends(get_db), user=Depends(require(*MGR))):
    qs = db.query(Employee)
    if q:
        qs = qs.filter(Employee.name.like(f"%{q}%") | Employee.email.like(f"%{q}%") | Employee.title.like(f"%{q}%"))
    if department_id:
        qs = qs.filter(Employee.department_id == department_id)
    if status:
        qs = qs.filter(Employee.status == status)
    if min_salary is not None:
        qs = qs.filter(Employee.salary >= min_salary)
    if max_salary is not None:
        qs = qs.filter(Employee.salary <= max_salary)
    if risk == "HIGH":
        qs = qs.filter(Employee.risk >= 70)
    elif risk == "MEDIUM":
        qs = qs.filter(Employee.risk >= 40, Employee.risk < 70)
    elif risk == "LOW":
        qs = qs.filter(Employee.risk < 40)
    total = qs.count()
    names = dept_name_map(db)
    items = qs.order_by(Employee.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"total": total, "items": [row(e, department=names.get(e.department_id)) for e in items]}


@router.post("/employees", status_code=201)
def create_employee(body: EmployeeIn, db=Depends(get_db), user=Depends(require(*HR))):
    if db.query(Employee).filter(Employee.email == body.email.lower()).first():
        raise HTTPException(409, "Employee email already exists")
    e = Employee(**{**body.model_dump(), "email": body.email.lower()})
    db.add(e)
    db.flush()
    recompute(db, e)
    audit(db, user, "EMPLOYEE_CREATE", e.name)
    db.commit()
    return row(e)


@router.get("/employees/{eid}")
def get_employee(eid: int, db=Depends(get_db), user=Depends(current_user)):
    if user.role == "EMPLOYEE" and user.employee_id != eid:
        raise HTTPException(403, "You can only view your own profile")
    e = db.get(Employee, eid)
    if not e:
        raise HTTPException(404, "Employee not found")
    return row(e, department=dept_name_map(db).get(e.department_id))


@router.put("/employees/{eid}")
def update_employee(eid: int, body: EmployeeIn, db=Depends(get_db), user=Depends(require(*HR))):
    e = db.get(Employee, eid)
    if not e:
        raise HTTPException(404, "Employee not found")
    for k, v in body.model_dump().items():
        setattr(e, k, v.lower() if k == "email" else v)
    recompute(db, e)
    audit(db, user, "EMPLOYEE_UPDATE", e.name)
    db.commit()
    return row(e)


@router.delete("/employees/{eid}")
def delete_employee(eid: int, db=Depends(get_db), user=Depends(require(*HR))):
    e = db.get(Employee, eid)
    if not e:
        raise HTTPException(404, "Employee not found")
    db.query(User).filter(User.employee_id == eid).update({"employee_id": None})
    for m in (Attendance, Leave, Payroll, Prediction, MonitorLog, Intervention, Document):
        db.query(m).filter(m.employee_id == eid).delete()
    audit(db, user, "EMPLOYEE_DELETE", e.name)
    db.delete(e)
    db.commit()
    return {"deleted": eid}


@router.get("/departments")
def list_departments(db=Depends(get_db), user=Depends(current_user)):
    return [row(d) for d in db.query(Department).order_by(Department.name)]


@router.post("/departments", status_code=201)
def create_department(body: DeptIn, db=Depends(get_db), user=Depends(require(*HR))):
    if db.query(Department).filter(Department.name == body.name).first():
        raise HTTPException(409, "Department already exists")
    d = Department(**body.model_dump())
    db.add(d)
    audit(db, user, "DEPT_CREATE", body.name)
    db.commit()
    return row(d)


@router.put("/departments/{did}")
def update_department(did: int, body: DeptIn, db=Depends(get_db), user=Depends(require(*HR))):
    d = db.get(Department, did)
    if not d:
        raise HTTPException(404, "Department not found")
    d.name, d.description = body.name, body.description
    audit(db, user, "DEPT_UPDATE", body.name)
    db.commit()
    return row(d)


@router.delete("/departments/{did}")
def delete_department(did: int, db=Depends(get_db), user=Depends(require(*HR))):
    d = db.get(Department, did)
    if not d:
        raise HTTPException(404, "Department not found")
    if db.query(Employee).filter(Employee.department_id == did).count():
        raise HTTPException(400, "Move employees out of this department first")
    audit(db, user, "DEPT_DELETE", d.name)
    db.delete(d)
    db.commit()
    return {"deleted": did}


@router.get("/departments/stats")
def department_stats(db=Depends(get_db), user=Depends(require(*MGR))):
    rows = db.query(Department.id, Department.name, func.count(Employee.id), func.avg(Employee.salary), func.avg(Employee.risk),
                    func.avg(Employee.overtime)).outerjoin(Employee, (Employee.department_id == Department.id) & (Employee.status == "ACTIVE")).group_by(Department.id, Department.name).all()
    return [{"id": r[0], "name": r[1], "headcount": r[2], "avg_salary": round(r[3] or 0), "avg_risk": round(r[4] or 0, 1), "avg_overtime": round(r[5] or 0, 1)} for r in rows]


@router.get("/users")
def list_users(db=Depends(get_db), user=Depends(current_user)):
    return [row(u) for u in db.query(User).order_by(User.name)]


@router.put("/users/{uid}/role")
def assign_role(uid: int, body: RoleIn, db=Depends(get_db), user=Depends(require("ADMIN"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    u.role = body.role
    audit(db, user, "ROLE_ASSIGN", f"{u.email} -> {body.role}")
    db.commit()
    return row(u)


@router.post("/attendance/check-in", status_code=201)
def check_in(body: EmpRef, db=Depends(get_db), user=Depends(current_user)):
    eid = emp_of(user, body.employee_id)
    today = date.today()
    if db.query(Attendance).filter(Attendance.employee_id == eid, Attendance.day == today).first():
        raise HTTPException(400, "Already checked in today")
    a = Attendance(employee_id=eid, day=today, check_in=now())
    db.add(a)
    db.commit()
    return row(a)


@router.post("/attendance/check-out")
def check_out(body: EmpRef, simulate_hours: float | None = None, db=Depends(get_db), user=Depends(current_user)):
    eid = emp_of(user, body.employee_id)
    a = db.query(Attendance).filter(Attendance.employee_id == eid, Attendance.day == date.today(), Attendance.check_out.is_(None)).first()
    if not a:
        raise HTTPException(400, "No open check-in for today")
    a.check_out = now()
    a.hours = round(simulate_hours if simulate_hours is not None else (a.check_out - a.check_in).total_seconds() / 3600, 2)
    a.overtime = round(max(0, a.hours - 8), 2)
    e = db.get(Employee, eid)
    e.overtime = (e.overtime or 0) + a.overtime
    recompute(db, e)
    db.commit()
    return row(a, employee_risk=e.risk)


@router.get("/attendance")
def attendance_report(employee_id: int | None = None, start: date | None = None, end: date | None = None, limit: int = 200,
                      db=Depends(get_db), user=Depends(current_user)):
    qs = db.query(Attendance, Employee.name).join(Employee, Employee.id == Attendance.employee_id)
    if user.role == "EMPLOYEE":
        employee_id = user.employee_id
    if employee_id:
        qs = qs.filter(Attendance.employee_id == employee_id)
    if start:
        qs = qs.filter(Attendance.day >= start)
    if end:
        qs = qs.filter(Attendance.day <= end)
    return [row(a, employee=n) for a, n in qs.order_by(Attendance.day.desc(), Attendance.id.desc()).limit(limit)]


@router.post("/leaves", status_code=201)
def apply_leave(body: LeaveIn, db=Depends(get_db), user=Depends(current_user)):
    eid = emp_of(user, body.employee_id)
    if body.end < body.start:
        raise HTTPException(400, "End date is before start date")
    days = (body.end - body.start).days + 1
    if days > leave_balance(db, eid)[body.kind]["remaining"]:
        raise HTTPException(400, f"Not enough {body.kind.lower()} leave balance")
    lv = Leave(employee_id=eid, kind=body.kind, start=body.start, end=body.end, days=days, reason=body.reason)
    db.add(lv)
    e = db.get(Employee, eid)
    ids = [u.id for u in db.query(User).filter(User.role.in_(MGR))]
    notify(db, ids, f"{e.name} applied for {days} day(s) of {body.kind.lower()} leave", "LOW", "LEAVE")
    db.commit()
    return row(lv)


def leave_balance(db, eid):
    year = date.today().year
    out = {}
    for kind, total in POLICY.items():
        used = db.query(func.coalesce(func.sum(Leave.days), 0)).filter(Leave.employee_id == eid, Leave.kind == kind, Leave.status == "APPROVED", func.extract("year", Leave.start) == year).scalar()
        out[kind] = {"total": total, "used": int(used), "remaining": total - int(used)}
    return out


@router.get("/leaves")
def list_leaves(status: str | None = None, db=Depends(get_db), user=Depends(current_user)):
    qs = db.query(Leave, Employee.name).join(Employee, Employee.id == Leave.employee_id)
    if user.role == "EMPLOYEE":
        qs = qs.filter(Leave.employee_id == user.employee_id)
    if status:
        qs = qs.filter(Leave.status == status)
    return [row(l, employee=n) for l, n in qs.order_by(Leave.id.desc()).limit(200)]


@router.get("/leaves/balance")
def balance(employee_id: int | None = None, db=Depends(get_db), user=Depends(current_user)):
    return leave_balance(db, emp_of(user, employee_id))


@router.put("/leaves/{lid}/decision")
def decide(lid: int, body: Decision, db=Depends(get_db), user=Depends(require(*MGR))):
    lv = db.get(Leave, lid)
    if not lv or lv.status != "PENDING":
        raise HTTPException(400, "Leave request not found or already decided")
    lv.status, lv.decided_by = body.status, user.id
    target = db.query(User).filter(User.employee_id == lv.employee_id).first()
    if target:
        notify(db, [target.id], f"Your {lv.kind.lower()} leave was {body.status.lower()}", "LOW", "LEAVE")
    audit(db, user, "LEAVE_" + body.status, f"leave {lid}")
    db.commit()
    return row(lv)


@router.get("/leaves/report")
def leave_report(db=Depends(get_db), user=Depends(require(*MGR))):
    rows = db.query(Leave.kind, Leave.status, func.count(Leave.id), func.sum(Leave.days)).group_by(Leave.kind, Leave.status).all()
    return [{"kind": r[0], "status": r[1], "requests": r[2], "days": int(r[3] or 0)} for r in rows]


def tax_rate(gross):
    annual = gross * 12
    return 0 if annual <= 30000 else 0.10 if annual <= 60000 else 0.20 if annual <= 100000 else 0.30


@router.post("/payroll/generate")
def generate_payroll(body: PayrollIn, db=Depends(get_db), user=Depends(require(*HR))):
    done = {p.employee_id for p in db.query(Payroll.employee_id).filter(Payroll.month == body.month)}
    created = 0
    for e in db.query(Employee).filter(Employee.status == "ACTIVE"):
        if e.id in done:
            continue
        basic = round(e.salary / 12, 2)
        bonus = round(basic * body.bonus_pct / 100, 2)
        tax = round((basic + bonus) * tax_rate(basic + bonus), 2)
        db.add(Payroll(employee_id=e.id, month=body.month, basic=basic, bonus=bonus, tax=tax, net=round(basic + bonus - tax, 2)))
        created += 1
    audit(db, user, "PAYROLL_GENERATE", f"{body.month}: {created}")
    db.commit()
    return {"month": body.month, "created": created, "skipped": len(done)}


@router.get("/payroll")
def list_payroll(month: str | None = None, db=Depends(get_db), user=Depends(current_user)):
    qs = db.query(Payroll, Employee.name).join(Employee, Employee.id == Payroll.employee_id)
    if user.role == "EMPLOYEE":
        qs = qs.filter(Payroll.employee_id == user.employee_id)
    elif user.role == "MANAGER":
        raise HTTPException(403, "Payroll is restricted to HR and Admin")
    if month:
        qs = qs.filter(Payroll.month == month)
    return [row(p, employee=n) for p, n in qs.order_by(Payroll.month.desc(), Payroll.id.desc()).limit(300)]


@router.get("/payroll/{pid}/payslip")
def payslip(pid: int, db=Depends(get_db), user=Depends(current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    p = db.get(Payroll, pid)
    if not p or (user.role == "EMPLOYEE" and p.employee_id != user.employee_id) or user.role == "MANAGER":
        raise HTTPException(404, "Payslip not found")
    e = db.get(Employee, p.employee_id)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 780
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, y, f"Payslip - {p.month}")
    c.setFont("Helvetica", 12)
    for label, val in [("Employee", e.name), ("Title", e.title), ("Basic", p.basic), ("Bonus", p.bonus), ("Tax deducted", p.tax), ("Net pay", p.net)]:
        y -= 28
        c.drawString(60, y, f"{label}: {val}")
    c.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=payslip-{p.month}-{e.id}.pdf"})


@router.get("/notifications")
def notifications(db=Depends(get_db), user=Depends(current_user)):
    items = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(100).all()
    return {"unread": sum(1 for n in items if not n.read), "items": [row(n) for n in items]}


@router.put("/notifications/read-all")
def read_all(db=Depends(get_db), user=Depends(current_user)):
    db.query(Notification).filter(Notification.user_id == user.id).update({"read": True})
    db.commit()
    return {"ok": True}


@router.put("/notifications/{nid}/read")
def read_one(nid: int, db=Depends(get_db), user=Depends(current_user)):
    db.query(Notification).filter(Notification.id == nid, Notification.user_id == user.id).update({"read": True})
    db.commit()
    return {"ok": True}


@router.get("/chat/{other}")
def chat_history(other: int, db=Depends(get_db), user=Depends(current_user)):
    db.query(Message).filter(Message.sender_id == other, Message.receiver_id == user.id, Message.read.is_(False)).update({"read": True})
    db.commit()
    msgs = db.query(Message).filter(((Message.sender_id == user.id) & (Message.receiver_id == other)) | ((Message.sender_id == other) & (Message.receiver_id == user.id))).order_by(Message.id).limit(300)
    return [row(m) for m in msgs]


@router.post("/chat", status_code=201)
def send_message(body: MsgIn, db=Depends(get_db), user=Depends(current_user)):
    if not db.get(User, body.to):
        raise HTTPException(404, "Recipient not found")
    m = Message(sender_id=user.id, receiver_id=body.to, body=body.body)
    db.add(m)
    notify(db, [body.to], f"New message from {user.name}", "LOW", "CHAT")
    db.commit()
    return row(m)


@router.post("/documents", status_code=201)
async def upload_document(employee_id: int = Form(...), file: UploadFile = File(...), db=Depends(get_db), user=Depends(current_user)):
    if user.role == "EMPLOYEE" and user.employee_id != employee_id:
        raise HTTPException(403, "You can only upload to your own profile")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"File type not allowed. Use: {', '.join(sorted(ALLOWED))}")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "File is larger than 5 MB")
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    os.makedirs(UPLOADS, exist_ok=True)
    stored = uuid.uuid4().hex + ext
    with open(os.path.join(UPLOADS, stored), "wb") as f:
        f.write(data)
    d = Document(employee_id=employee_id, filename=os.path.basename(file.filename), stored=stored, size=len(data), uploaded_by=user.id)
    db.add(d)
    audit(db, user, "DOCUMENT_UPLOAD", file.filename)
    db.commit()
    return row(d)


@router.get("/documents")
def list_documents(employee_id: int | None = None, db=Depends(get_db), user=Depends(current_user)):
    qs = db.query(Document, Employee.name).join(Employee, Employee.id == Document.employee_id)
    if user.role == "EMPLOYEE":
        employee_id = user.employee_id
    if employee_id:
        qs = qs.filter(Document.employee_id == employee_id)
    return [row(d, employee=n) for d, n in qs.order_by(Document.id.desc()).limit(200)]


def own_doc(db, did, user):
    d = db.get(Document, did)
    if not d or (user.role == "EMPLOYEE" and d.employee_id != user.employee_id):
        raise HTTPException(404, "Document not found")
    return d


@router.get("/documents/{did}/download")
def download_document(did: int, db=Depends(get_db), user=Depends(current_user)):
    d = own_doc(db, did, user)
    return FileResponse(os.path.join(UPLOADS, d.stored), filename=d.filename)


@router.delete("/documents/{did}")
def delete_document(did: int, db=Depends(get_db), user=Depends(current_user)):
    d = own_doc(db, did, user)
    try:
        os.remove(os.path.join(UPLOADS, d.stored))
    except OSError:
        pass
    audit(db, user, "DOCUMENT_DELETE", d.filename)
    db.delete(d)
    db.commit()
    return {"deleted": did}


@router.get("/dashboard")
def dashboard(db=Depends(get_db), user=Depends(require(*MGR))):
    active = db.query(Employee).filter(Employee.status == "ACTIVE")
    today = date.today()
    month = today.strftime("%Y-%m")
    by_dept = db.query(Department.name, func.count(Employee.id)).outerjoin(Employee, (Employee.department_id == Department.id) & (Employee.status == "ACTIVE")).group_by(Department.name).all()
    risk = {"HIGH": active.filter(Employee.risk >= 70).count(), "MEDIUM": active.filter(Employee.risk >= 40, Employee.risk < 70).count(), "LOW": active.filter(Employee.risk < 40).count()}
    return {
        "active": active.count(),
        "left": db.query(Employee).filter(Employee.status == "LEFT").count(),
        "present_today": db.query(Attendance).filter(Attendance.day == today).count(),
        "pending_leaves": db.query(Leave).filter(Leave.status == "PENDING").count(),
        "payroll_month": month,
        "payroll_total": round(db.query(func.coalesce(func.sum(Payroll.net), 0)).filter(Payroll.month == month).scalar() or 0),
        "avg_salary": round(active.with_entities(func.avg(Employee.salary)).scalar() or 0),
        "by_department": [{"name": n, "count": c} for n, c in by_dept],
        "risk": [{"name": k, "value": v} for k, v in risk.items()],
        "open_interventions": db.query(Intervention).filter(Intervention.status != "DONE").count(),
    }


@router.get("/audit")
def audit_logs(limit: int = 100, db=Depends(get_db), user=Depends(require(*HR))):
    rows = db.query(Audit, User.name).outerjoin(User, User.id == Audit.user_id).order_by(Audit.id.desc()).limit(limit)
    return [row(a, user=n or "system") for a, n in rows]


@router.get("/reports/{kind}")
def report(kind: str, fmt: str = "xlsx", db=Depends(get_db), user=Depends(require(*HR))):
    import pandas as pd
    names = dept_name_map(db)
    if kind == "employees":
        df = pd.DataFrame([{"Name": e.name, "Email": e.email, "Department": names.get(e.department_id), "Title": e.title, "Salary": e.salary, "Status": e.status} for e in db.query(Employee)])
    elif kind == "attrition":
        df = pd.DataFrame([{"Name": e.name, "Department": names.get(e.department_id), "Risk %": e.risk, "Satisfaction": e.satisfaction, "Overtime": e.overtime, "Years since promotion": e.promo_gap} for e in db.query(Employee).filter(Employee.status == "ACTIVE").order_by(Employee.risk.desc())])
    elif kind == "payroll":
        df = pd.DataFrame([{"Month": p.month, "Employee": n, "Basic": p.basic, "Bonus": p.bonus, "Tax": p.tax, "Net": p.net} for p, n in db.query(Payroll, Employee.name).join(Employee, Employee.id == Payroll.employee_id)])
    elif kind == "attendance":
        df = pd.DataFrame([{"Date": a.day, "Employee": n, "Hours": a.hours, "Overtime": a.overtime} for a, n in db.query(Attendance, Employee.name).join(Employee, Employee.id == Attendance.employee_id)])
    else:
        raise HTTPException(404, "Unknown report")
    buf = io.BytesIO()
    if fmt == "xlsx":
        df.to_excel(buf, index=False)
        media, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        data = [list(df.columns)] + df.head(300).astype(str).values.tolist()
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4d3a")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
        SimpleDocTemplate(buf, pagesize=landscape(A4)).build([t])
        media, ext = "application/pdf", "pdf"
    buf.seek(0)
    audit(db, user, "REPORT_EXPORT", f"{kind}.{ext}")
    db.commit()
    return StreamingResponse(buf, media_type=media, headers={"Content-Disposition": f"attachment; filename={kind}-report.{ext}"})
