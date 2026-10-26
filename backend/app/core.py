import os
import datetime as dt
import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:baskar123@localhost:3306/workforce_ai")
SECRET = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "60"))

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10)
Session = sessionmaker(bind=engine, autoflush=False)
bearer = HTTPBearer(auto_error=False)


class Base(DeclarativeBase):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()


def hash_pw(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def check_pw(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())


def make_token(user):
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, SECRET, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired, please log in again")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")


def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)):
    from .models import User
    if not cred:
        raise HTTPException(401, "Not authenticated")
    user = db.get(User, int(decode_token(cred.credentials)["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require(*roles):
    def check(user=Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "You do not have permission for this action")
        return user
    return check


def row(o, **extra):
    d = {c.name: getattr(o, c.name) for c in o.__table__.columns if c.name not in ("password_hash", "reset_token")}
    d.update(extra)
    return d