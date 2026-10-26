from . import ml
from .core import now
from .models import Audit, Department, Employee, Intervention, MonitorLog, Notification, Prediction, User

HIGH, MEDIUM = 70, 40


def level(risk):
    return "HIGH" if risk >= HIGH else "MEDIUM" if risk >= MEDIUM else "LOW"


def audit(db, user, action, detail=""):
    db.add(Audit(user_id=user.id if user else None, action=action, detail=str(detail)[:300]))


def notify(db, user_ids, message, priority="LOW", kind="INFO"):
    for uid in user_ids:
        db.add(Notification(user_id=uid, message=message[:300], priority=priority, kind=kind))


def notify_hr(db, message, priority="HIGH", kind="RISK"):
    ids = [u.id for u in db.query(User.id).filter(User.role.in_(["ADMIN", "HR"]))]
    notify(db, [i[0] if isinstance(i, tuple) else i for i in ids], message, priority, kind)


def features(e):
    return {f: getattr(e, f) or 0 for f in ml.FEATURES}


def recommend(db, e):
    avg = db.query(Employee).filter(Employee.department_id == e.department_id, Employee.status == "ACTIVE").with_entities(Employee.salary).all()
    dept_avg = sum(a[0] for a in avg) / len(avg) if avg else e.salary
    tips = []
    if e.satisfaction <= 2:
        tips.append("Schedule a career conversation with the manager and agree on a satisfaction action plan")
    if e.overtime > 30:
        tips.append("Rebalance workload or add support; overtime is well above a healthy level")
    if e.promo_gap > 3:
        tips.append("Review promotion eligibility; long gap since the last promotion")
    if e.salary < dept_avg * 0.9:
        tips.append("Run a compensation review against the department average")
    if e.absences > 10:
        tips.append("Hold a wellbeing check-in to understand the rising absences")
    if e.performance >= 4 and e.promo_gap > 2:
        tips.append("High performer at risk: consider a retention bonus or stretch role")
    return tips or ["Continue regular check-ins and recognise recent contributions"]


def raise_alert(db, e, risk, old):
    prio = "CRITICAL" if risk >= 85 else "HIGH"
    msg = f"High attrition risk: {e.name} is now at {risk:.0f}%"
    notify_hr(db, msg, prio)
    db.add(MonitorLog(employee_id=e.id, old_risk=old, new_risk=risk, message=msg))
    if not db.query(Intervention).filter(Intervention.employee_id == e.id, Intervention.status != "DONE").first():
        db.add(Intervention(employee_id=e.id, action=recommend(db, e)[0]))


def recompute(db, e, quiet=False):
    if e.status != "ACTIVE":
        return None
    risk = ml.score([features(e)])[0]
    prev = db.query(Prediction).filter(Prediction.employee_id == e.id).order_by(Prediction.id.desc()).first()
    old = prev.risk if prev else None
    db.add(Prediction(employee_id=e.id, risk=risk, confidence=round(abs(risk - 50) * 2, 1), level=level(risk)))
    e.risk = risk
    if not quiet:
        if old is not None and abs(risk - old) >= 5:
            db.add(MonitorLog(employee_id=e.id, old_risk=old, new_risk=risk, message=f"Risk for {e.name} moved {old:.0f}% to {risk:.0f}%"))
        if risk >= HIGH and (old is None or old < HIGH or risk - old >= 10):
            raise_alert(db, e, risk, old)
    return risk


def dept_name_map(db):
    return {d.id: d.name for d in db.query(Department)}
