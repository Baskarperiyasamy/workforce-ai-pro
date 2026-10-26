from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from .core import Base, now


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="EMPLOYEE", nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id", use_alter=True, name="fk_user_employee"), nullable=True)
    reset_token = Column(String(100), nullable=True)
    reset_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(String(255))


class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(30))
    title = Column(String(80), default="Staff")
    department_id = Column(Integer, ForeignKey("departments.id"), index=True)
    salary = Column(Float, nullable=False)
    hire_date = Column(Date)
    status = Column(String(10), default="ACTIVE", index=True)
    shift = Column(String(15), default="Morning")
    age = Column(Integer, default=30)
    tenure = Column(Float, default=0)
    satisfaction = Column(Integer, default=3)
    overtime = Column(Float, default=0)
    performance = Column(Integer, default=3)
    absences = Column(Integer, default=0)
    promo_gap = Column(Float, default=0)
    risk = Column(Float, index=True)
    created_at = Column(DateTime, default=now)


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    day = Column(Date, index=True, nullable=False)
    check_in = Column(DateTime, nullable=False)
    check_out = Column(DateTime)
    hours = Column(Float, default=0)
    overtime = Column(Float, default=0)


class Leave(Base):
    __tablename__ = "leaves"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    kind = Column(String(15), nullable=False)
    start = Column(Date, nullable=False)
    end = Column(Date, nullable=False)
    days = Column(Integer, nullable=False)
    reason = Column(String(255))
    status = Column(String(10), default="PENDING", index=True)
    decided_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=now)


class Payroll(Base):
    __tablename__ = "payroll"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    month = Column(String(7), index=True, nullable=False)
    basic = Column(Float)
    bonus = Column(Float, default=0)
    tax = Column(Float)
    net = Column(Float)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    message = Column(String(300), nullable=False)
    priority = Column(String(10), default="LOW")
    kind = Column(String(20), default="INFO")
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now, index=True)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    body = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    filename = Column(String(200), nullable=False)
    stored = Column(String(200), nullable=False)
    size = Column(Integer)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=now)


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True)
    version = Column(Integer, unique=True, nullable=False)
    filename = Column(String(200))
    rows_ok = Column(Integer, default=0)
    rows_failed = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    accuracy = Column(Float)
    created_at = Column(DateTime, default=now)


class TrainingRow(Base):
    __tablename__ = "training_rows"
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), index=True, nullable=False)
    age = Column(Float)
    tenure = Column(Float)
    salary = Column(Float)
    satisfaction = Column(Float)
    overtime = Column(Float)
    performance = Column(Float)
    absences = Column(Float)
    promo_gap = Column(Float)
    attrition = Column(Integer)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    risk = Column(Float, nullable=False)
    confidence = Column(Float)
    level = Column(String(10))
    created_at = Column(DateTime, default=now, index=True)


class MonitorLog(Base):
    __tablename__ = "monitor_logs"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    old_risk = Column(Float)
    new_risk = Column(Float)
    message = Column(String(300))
    created_at = Column(DateTime, default=now, index=True)


class Intervention(Base):
    __tablename__ = "interventions"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True, nullable=False)
    action = Column(String(300), nullable=False)
    status = Column(String(15), default="OPEN", index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Audit(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(60), nullable=False)
    detail = Column(String(300))
    created_at = Column(DateTime, default=now, index=True)
