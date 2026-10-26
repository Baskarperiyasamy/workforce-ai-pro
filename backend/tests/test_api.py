import os
import tempfile
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def login(email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_auth_flow():
    with TestClient(app) as c:
        assert c.post("/api/auth/register", json={"name": "Test User", "email": "t@x.com", "password": "Passw0rd!"}).status_code == 201
        assert c.post("/api/auth/register", json={"name": "Test User", "email": "t@x.com", "password": "Passw0rd!"}).status_code == 409
        assert c.post("/api/auth/login", json={"email": "t@x.com", "password": "wrong"}).status_code == 401
        token = c.post("/api/auth/forgot-password", json={"email": "t@x.com"}).json()["reset_token"]
        assert c.post("/api/auth/reset-password", json={"token": token, "password": "NewPass123"}).status_code == 200
        assert c.post("/api/auth/login", json={"email": "t@x.com", "password": "NewPass123"}).status_code == 200
        assert c.get("/api/auth/me").status_code == 401


def test_rbac_and_employee_crud():
    with TestClient(app) as c:
        h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "hr@workforce.ai", "password": "Hr@12345"}).json()["access_token"]}
        e = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "employee@workforce.ai", "password": "Employee@123"}).json()["access_token"]}
        assert c.get("/api/employees", headers=e).status_code == 403
        body = {"name": "New Hire", "email": "new.hire@workforce.ai", "salary": 52000, "age": 29, "satisfaction": 1, "overtime": 40, "promo_gap": 5, "department_id": 1}
        r = c.post("/api/employees", json=body, headers=h)
        assert r.status_code == 201
        eid = r.json()["id"]
        assert c.get("/api/employees?q=New Hire", headers=h).json()["total"] >= 1
        assert c.put(f"/api/employees/{eid}", json={**body, "title": "Analyst"}, headers=h).json()["title"] == "Analyst"
        assert c.delete(f"/api/employees/{eid}", headers=h).status_code == 200


def test_attendance_triggers_prediction():
    with TestClient(app) as c:
        h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "employee@workforce.ai", "password": "Employee@123"}).json()["access_token"]}
        assert c.post("/api/attendance/check-in", json={}, headers=h).status_code == 201
        r = c.post("/api/attendance/check-out?simulate_hours=14", json={}, headers=h)
        assert r.status_code == 200 and r.json()["overtime"] == 6 and r.json()["employee_risk"] is not None


def test_leave_payroll_ai():
    with TestClient(app) as c:
        hr = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "hr@workforce.ai", "password": "Hr@12345"}).json()["access_token"]}
        em = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "employee@workforce.ai", "password": "Employee@123"}).json()["access_token"]}
        assert c.post("/api/leaves", json={"kind": "ANNUAL", "start": "2030-01-10", "end": "2030-01-12"}, headers=em).status_code == 201
        assert c.post("/api/leaves", json={"kind": "SICK", "start": "2030-02-01", "end": "2030-03-30"}, headers=em).status_code == 400
        lid = c.get("/api/leaves?status=PENDING", headers=hr).json()[0]["id"]
        assert c.put(f"/api/leaves/{lid}/decision", json={"status": "APPROVED"}, headers=hr).status_code == 200
        assert c.post("/api/payroll/generate", json={"month": "2031-01", "bonus_pct": 5}, headers=hr).json()["created"] > 0
        assert c.get("/api/ai/risk/high", headers=hr).status_code == 200
        f = c.get("/api/ai/forecast", headers=hr).json()
        assert len(f["monthly"]) == 12 and f["stability"] in ("STABLE", "WATCH", "UNSTABLE")
        assert c.post("/api/ai/train", headers=hr).json()["accuracy"] > 0.6
        bad = b"age,tenure,salary,satisfaction,overtime,performance,absences,promo_gap,attrition\n30,3,50000,3,10,3,2,1,0\n30,3,50000,3,10,3,2,1,0\nabc,3,50000,3,10,3,2,1,1\n"
        r = c.post("/api/ai/datasets", files={"file": ("d.csv", bad, "text/csv")}, headers=hr)
        assert r.status_code == 201 and r.json()["rows_failed"] == 1 and r.json()["duplicates"] == 1
        assert c.get("/api/reports/employees?fmt=xlsx", headers=hr).status_code == 200
        assert c.get("/api/reports/attrition?fmt=pdf", headers=hr).status_code == 200
