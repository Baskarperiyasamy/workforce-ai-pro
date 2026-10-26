import datetime as dt
import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from .core import check_pw, current_user, get_db, hash_pw, make_token, now, row
from .models import Employee, User
from .services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=64)


@router.post("/register", status_code=201)
def register(body: RegisterIn, db=Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    emp = db.query(Employee).filter(Employee.email == email).first()
    user = User(name=body.name, email=email, password_hash=hash_pw(body.password), role="EMPLOYEE", employee_id=emp.id if emp else None)
    db.add(user)
    audit(db, user, "REGISTER", email)
    db.commit()
    return row(user)


@router.post("/login")
def login(body: LoginIn, db=Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not check_pw(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    audit(db, user, "LOGIN", user.email)
    db.commit()
    return {"access_token": make_token(user), "token_type": "bearer", "user": row(user)}


@router.get("/me")
def me(user=Depends(current_user)):
    return row(user)


@router.post("/forgot-password")
def forgot(body: ForgotIn, db=Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    out = {"message": "If the account exists, a reset token has been generated"}
    if user:
        user.reset_token = secrets.token_urlsafe(24)
        user.reset_expires = now() + dt.timedelta(minutes=30)
        db.commit()
        out["reset_token"] = user.reset_token
    return out


@router.post("/reset-password")
def reset(body: ResetIn, db=Depends(get_db)):
    user = db.query(User).filter(User.reset_token == body.token).first()
    if not user or not user.reset_expires or user.reset_expires < now():
        raise HTTPException(400, "Reset token is invalid or expired")
    user.password_hash = hash_pw(body.password)
    user.reset_token = user.reset_expires = None
    audit(db, user, "PASSWORD_RESET", user.email)
    db.commit()
    return {"message": "Password updated"}
