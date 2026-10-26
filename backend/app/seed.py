import datetime as dt
import random
from . import ml
from .core import Session, hash_pw
from .models import Attendance, Dataset, Department, Employee, Leave, Payroll, TrainingRow, User
from .routes_hr import tax_rate
from .services import raise_alert, recompute

FIRST = "Aarav Priya Rohan Meera Karthik Divya Arjun Sneha Vikram Ananya Rahul Kavya Suresh Nisha Imran Lakshmi Dev Pooja Naveen Ritu Faisal Sandhya Anil Harini Manoj Swathi Tarun Geeta Yusuf Deepa".split()
LAST = "Sharma Iyer Nair Reddy Menon Gupta Patel Khan Das Rao Pillar Bose Singh Verma Joshi Kumar".split()
DEPTS = {"Engineering": ["Software Engineer", "QA Engineer", "DevOps Engineer"], "Sales": ["Account Executive", "Sales Associate"], "Human Resources": ["HR Executive", "Recruiter"],
         "Finance": ["Accountant", "Financial Analyst"], "Customer Support": ["Support Agent", "Team Lead"], "Operations": ["Operations Analyst", "Coordinator"]}


def run():
    db = Session()
    if db.query(User).count():
        db.close()
        return
    random.seed(11)
    depts = {n: Department(name=n, description=f"{n} department") for n in DEPTS}
    db.add_all(depts.values())
    db.flush()
    synth = ml.synthetic(1500)
    ds = Dataset(version=1, filename="baseline_synthetic.csv", rows_ok=len(synth))
    db.add(ds)
    db.flush()
    db.bulk_insert_mappings(TrainingRow, [{**{c: float(r[c]) for c in ml.FEATURES}, "attrition": int(r["attrition"]), "dataset_id": ds.id} for _, r in synth.iterrows()])
    ds.accuracy = ml.train(synth)

    pool = ml.synthetic(110, seed=21)
    emps = []
    for i, r in pool.iterrows():
        dname = random.choice(list(DEPTS))
        first, last = random.choice(FIRST), random.choice(LAST)
        left = bool(r["attrition"]) and i % 2 == 0
        e = Employee(name=f"{first} {last}", email=f"{first}.{last}{i}@workforce.ai".lower(), phone=f"+91 9{random.randint(100000000, 999999999)}", title=random.choice(DEPTS[dname]),
                     department_id=depts[dname].id, salary=float(r["salary"]), hire_date=dt.date.today() - dt.timedelta(days=int(r["tenure"] * 365) + 30), status="LEFT" if left else "ACTIVE",
                     shift=random.choice(["Morning", "Evening", "Night"]), age=int(r["age"]), tenure=float(r["tenure"]), satisfaction=int(r["satisfaction"]), overtime=float(r["overtime"]),
                     performance=int(r["performance"]), absences=int(r["absences"]), promo_gap=float(r["promo_gap"]))
        emps.append(e)
    db.add_all(emps)
    db.flush()
    active = [e for e in emps if e.status == "ACTIVE"]
    for e in active:
        recompute(db, e, quiet=True)

    people = [("Asha Admin", "admin@workforce.ai", "ADMIN", "Admin@123"), ("Hari HR", "hr@workforce.ai", "HR", "Hr@12345"),
              ("Mala Manager", "manager@workforce.ai", "MANAGER", "Manager@123"), ("Eshan Employee", "employee@workforce.ai", "EMPLOYEE", "Employee@123")]
    for (name, email, role, pw), e in zip(people, active):
        e.name, e.email = name, email
        db.add(User(name=name, email=email, role=role, password_hash=hash_pw(pw), employee_id=e.id))

    today = dt.date.today()
    for e in active[:60]:
        for back in range(1, 15):
            d = today - dt.timedelta(days=back)
            if d.weekday() > 4:
                continue
            hrs = round(random.uniform(7, 10.5), 2)
            cin = dt.datetime.combine(d, dt.time(9, random.randint(0, 40)))
            db.add(Attendance(employee_id=e.id, day=d, check_in=cin, check_out=cin + dt.timedelta(hours=hrs), hours=hrs, overtime=round(max(0, hrs - 8), 2)))
    for i, e in enumerate(active[4:10]):
        s = today + dt.timedelta(days=3 + i)
        db.add(Leave(employee_id=e.id, kind=random.choice(["ANNUAL", "SICK", "CASUAL"]), start=s, end=s + dt.timedelta(days=1), days=2, reason="Personal", status="PENDING" if i % 2 else "APPROVED"))
    month = today.strftime("%Y-%m")
    for e in active:
        basic = round(e.salary / 12, 2)
        tax = round(basic * tax_rate(basic), 2)
        db.add(Payroll(employee_id=e.id, month=month, basic=basic, bonus=0, tax=tax, net=round(basic - tax, 2)))
    for e in sorted(active, key=lambda x: -x.risk)[:4]:
        raise_alert(db, e, e.risk, None)
    db.commit()
    db.close()
