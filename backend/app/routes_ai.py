import io
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from . import ml
from .core import get_db, now, require, row
from .models import Audit, Dataset, Department, Employee, Intervention, MonitorLog, Prediction, TrainingRow
from .services import audit, dept_name_map, level, recommend, recompute

router = APIRouter(prefix="/api/ai", tags=["ai"])
HR = ("ADMIN", "HR")
MGR = ("ADMIN", "HR", "MANAGER")
RANGES = {"age": (16, 75), "tenure": (0, 50), "salary": (1000, 1000000), "satisfaction": (1, 4), "overtime": (0, 200), "performance": (1, 5), "absences": (0, 365), "promo_gap": (0, 40)}


class IntervIn(BaseModel):
    employee_id: int
    action: str


class IntervUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.get("/datasets")
def datasets(db=Depends(get_db), user=Depends(require(*MGR))):
    return [row(d) for d in db.query(Dataset).order_by(Dataset.version.desc())]


@router.get("/datasets/template")
def template(user=Depends(require(*HR))):
    buf = io.StringIO()
    ml.synthetic(10, seed=1).to_csv(buf, index=False)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=dataset-template.csv"})


@router.post("/datasets", status_code=201)
async def upload_dataset(file: UploadFile = File(...), db=Depends(get_db), user=Depends(require(*HR))):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Upload a .csv file")
    try:
        df = pd.read_csv(io.BytesIO(await file.read()))
    except Exception:
        raise HTTPException(400, "CSV could not be parsed")
    cols = ml.FEATURES + ["attrition"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing columns: {', '.join(missing)}")
    failed, good = [], []
    for i, r in df[cols].iterrows():
        vals = pd.to_numeric(r, errors="coerce")
        bad = [c for c in cols if pd.isna(vals[c])]
        bad += [c for c, (lo, hi) in RANGES.items() if c not in bad and not lo <= vals[c] <= hi]
        if not bad and vals["attrition"] not in (0, 1):
            bad.append("attrition")
        if bad:
            failed.append({"row": int(i) + 2, "columns": bad})
        else:
            good.append(vals)
    clean = pd.DataFrame(good, columns=cols)
    dupes_in_file = int(clean.duplicated().sum())
    clean = clean.drop_duplicates()
    existing = pd.read_sql(db.query(*[getattr(TrainingRow, c) for c in cols]).statement, db.bind) if db.query(TrainingRow).count() else pd.DataFrame(columns=cols)
    merged = clean.astype(float).merge(existing.astype(float).drop_duplicates(), on=cols, how="left", indicator=True)
    fresh = merged[merged["_merge"] == "left_only"].drop(columns="_merge")
    dupes = dupes_in_file + len(clean) - len(fresh)
    if fresh.empty:
        raise HTTPException(400, f"No new valid rows. Failed: {len(failed)}, duplicates: {dupes}")
    version = (db.query(func.max(Dataset.version)).scalar() or 0) + 1
    ds = Dataset(version=version, filename=file.filename, rows_ok=len(fresh), rows_failed=len(failed), duplicates=dupes)
    db.add(ds)
    db.flush()
    db.bulk_insert_mappings(TrainingRow, [{**{c: float(r[c]) for c in cols[:-1]}, "attrition": int(r["attrition"]), "dataset_id": ds.id} for _, r in fresh.iterrows()])
    audit(db, user, "DATASET_UPLOAD", f"v{version} {file.filename}")
    db.commit()
    return {**row(ds), "failed_rows": failed[:25]}


@router.post("/train")
def train(db=Depends(get_db), user=Depends(require(*HR))):
    cols = ml.FEATURES + ["attrition"]
    df = pd.read_sql(db.query(*[getattr(TrainingRow, c) for c in cols]).statement, db.bind)
    if len(df) < 50 or df["attrition"].nunique() < 2:
        raise HTTPException(400, "Need at least 50 rows with both outcomes to train")
    acc = ml.train(df)
    latest = db.query(Dataset).order_by(Dataset.version.desc()).first()
    latest.accuracy = acc
    audit(db, user, "MODEL_TRAIN", f"accuracy {acc}")
    db.commit()
    return {"accuracy": acc, "rows": len(df), "importances": ml.importances()}


@router.post("/predict-all")
def predict_all(db=Depends(get_db), user=Depends(require(*HR))):
    emps = db.query(Employee).filter(Employee.status == "ACTIVE").all()
    for e in emps:
        recompute(db, e)
    audit(db, user, "PREDICT_ALL", len(emps))
    db.commit()
    return {"predicted": len(emps), "high_risk": sum(1 for e in emps if e.risk >= 70)}


@router.post("/predict/{eid}")
def predict_one(eid: int, db=Depends(get_db), user=Depends(require(*MGR))):
    e = db.get(Employee, eid)
    if not e or e.status != "ACTIVE":
        raise HTTPException(404, "Active employee not found")
    risk = recompute(db, e)
    db.commit()
    return {"employee": e.name, "risk": risk, "level": level(risk), "confidence": round(abs(risk - 50) * 2, 1), "recommendations": recommend(db, e)}


@router.get("/predictions/{eid}")
def history(eid: int, db=Depends(get_db), user=Depends(require(*MGR))):
    return [row(p) for p in db.query(Prediction).filter(Prediction.employee_id == eid).order_by(Prediction.id.desc()).limit(50)]


@router.get("/risk/high")
def high_risk(min_risk: float = 70, db=Depends(get_db), user=Depends(require(*MGR))):
    names = dept_name_map(db)
    emps = db.query(Employee).filter(Employee.status == "ACTIVE", Employee.risk >= min_risk).order_by(Employee.risk.desc()).limit(100).all()
    return [row(e, department=names.get(e.department_id), level=level(e.risk), recommendations=recommend(db, e)[:2]) for e in emps]


@router.get("/risk/logs")
def risk_logs(limit: int = 60, db=Depends(get_db), user=Depends(require(*MGR))):
    rows = db.query(MonitorLog, Employee.name).outerjoin(Employee, Employee.id == MonitorLog.employee_id).order_by(MonitorLog.id.desc()).limit(limit)
    return [row(m, employee=n) for m, n in rows]


@router.get("/feed")
def feed(db=Depends(get_db), user=Depends(require(*MGR))):
    logs = [{"at": m.created_at, "type": "RISK", "text": m.message} for m in db.query(MonitorLog).order_by(MonitorLog.id.desc()).limit(15)]
    acts = [{"at": a.created_at, "type": "ACTIVITY", "text": f"{a.action}: {a.detail or ''}"} for a in db.query(Audit).order_by(Audit.id.desc()).limit(15)]
    return sorted(logs + acts, key=lambda x: x["at"], reverse=True)[:25]


@router.get("/analytics")
def analytics(db=Depends(get_db), user=Depends(require(*MGR))):
    names = dept_name_map(db)
    depts = []
    for did, name in names.items():
        qs = db.query(Employee).filter(Employee.department_id == did)
        active, left = qs.filter(Employee.status == "ACTIVE").count(), qs.filter(Employee.status == "LEFT").count()
        avg = db.query(func.avg(Employee.risk)).filter(Employee.department_id == did, Employee.status == "ACTIVE").scalar() or 0
        depts.append({"name": name, "active": active, "left": left, "turnover_pct": round(left / (active + left) * 100, 1) if active + left else 0, "avg_risk": round(avg, 1), "high_risk": qs.filter(Employee.status == "ACTIVE", Employee.risk >= 70).count()})
    trend = db.query(func.date(Prediction.created_at), func.avg(Prediction.risk)).group_by(func.date(Prediction.created_at)).order_by(func.date(Prediction.created_at)).limit(30).all()
    total_active = sum(d["active"] for d in depts)
    total_left = sum(d["left"] for d in depts)
    return {
        "departments": depts,
        "turnover_pct": round(total_left / (total_active + total_left) * 100, 1) if total_active + total_left else 0,
        "trend": [{"day": str(d), "avg_risk": round(r, 1)} for d, r in trend],
        "drivers": ml.importances(),
        "latest_accuracy": (db.query(Dataset.accuracy).filter(Dataset.accuracy.isnot(None)).order_by(Dataset.version.desc()).first() or [None])[0],
    }


@router.get("/forecast")
def forecast(months: int = 12, db=Depends(get_db), user=Depends(require(*MGR))):
    months = max(1, min(months, 24))
    names = dept_name_map(db)
    base = db.query(Employee).filter(Employee.status == "ACTIVE").all()
    annual = sum((e.risk or 0) / 100 for e in base) / max(len(base), 1)
    monthly_rate = 1 - (1 - min(annual, 0.95)) ** (1 / 12)
    head, rows = float(len(base)), []
    for i in range(1, months + 1):
        exits = head * monthly_rate
        head -= exits
        rows.append({"month": i, "headcount": round(head, 1), "expected_exits": round(exits, 1), "retention_pct": round(head / max(len(base), 1) * 100, 1)})
    depts = []
    for did, name in names.items():
        es = [e for e in base if e.department_id == did]
        avg = sum((e.risk or 0) for e in es) / len(es) if es else 0
        depts.append({"name": name, "headcount": len(es), "stability_score": round(100 - avg, 1), "expected_exits_year": round(sum((e.risk or 0) / 100 for e in es), 1)})
    return {"current_headcount": len(base), "yearly_exit_rate_pct": round(annual * 100, 1), "monthly": rows, "departments": depts, "stability": "STABLE" if annual < 0.2 else "WATCH" if annual < 0.35 else "UNSTABLE"}


@router.get("/recommendations/{eid}")
def recommendations(eid: int, db=Depends(get_db), user=Depends(require(*MGR))):
    e = db.get(Employee, eid)
    if not e:
        raise HTTPException(404, "Employee not found")
    return {"employee": e.name, "risk": e.risk, "recommendations": recommend(db, e)}


@router.get("/interventions")
def interventions(status: str | None = None, db=Depends(get_db), user=Depends(require(*MGR))):
    qs = db.query(Intervention, Employee.name).join(Employee, Employee.id == Intervention.employee_id)
    if status:
        qs = qs.filter(Intervention.status == status)
    return [row(i, employee=n) for i, n in qs.order_by(Intervention.id.desc()).limit(100)]


@router.post("/interventions", status_code=201)
def add_intervention(body: IntervIn, db=Depends(get_db), user=Depends(require(*HR))):
    if not db.get(Employee, body.employee_id):
        raise HTTPException(404, "Employee not found")
    i = Intervention(**body.model_dump())
    db.add(i)
    audit(db, user, "INTERVENTION_ADD", body.action)
    db.commit()
    return row(i)


@router.put("/interventions/{iid}")
def update_intervention(iid: int, body: IntervUpdate, db=Depends(get_db), user=Depends(require(*HR))):
    i = db.get(Intervention, iid)
    if not i:
        raise HTTPException(404, "Intervention not found")
    if body.status:
        if body.status not in ("OPEN", "IN_PROGRESS", "DONE"):
            raise HTTPException(400, "Invalid status")
        i.status = body.status
    if body.notes is not None:
        i.notes = body.notes
    audit(db, user, "INTERVENTION_UPDATE", f"{iid} {i.status}")
    db.commit()
    return row(i)
