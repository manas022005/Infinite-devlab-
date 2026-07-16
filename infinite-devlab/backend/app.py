"""Infinite DevLab — Flask + MySQL backend.

Serves JSON API under /auth and /api, and the static frontend under /.
Compatible with the existing frontend (login.html posts form-encoded to
/auth/login and JSON to /auth/signup, stores `token` in localStorage).
"""
from __future__ import annotations

import os
import datetime as dt
from functools import wraps
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

load_dotenv()

# ---------- Config ----------
DB_URL = os.getenv("DATABASE_URL", "sqlite:///devlab.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", "24"))
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", "../frontend")).resolve()
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
PORT = int(os.getenv("PORT", "8000"))

# ---------- DB ----------
engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(190), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    avatar_url = Column(String(500))
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class Progress(Base):
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    module = Column(String(60), nullable=False)
    level = Column(Integer, default=0)
    score = Column(Integer, default=0)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "module", name="uniq_user_module"),)


class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(120), nullable=False)
    detail = Column(Text)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(engine)


# ---------- App ----------
app = Flask(__name__, static_folder=None)
CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}})


# ---------- robots.txt (must come before the catch-all "/<path:path>" route below) ----------
@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.root_path, 'robots.txt')


@app.teardown_appcontext
def remove_session(exc=None):
    SessionLocal.remove()


# ---------- Helpers ----------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "exp": dt.datetime.utcnow() + dt.timedelta(hours=JWT_EXPIRES_HOURS),
        "iat": dt.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def avatar_for(name: str, email: str) -> str:
    initial = (name or email or "?").strip()[:1].upper()
    return f"https://api.dicebear.com/9.x/initials/svg?seed={initial}&backgroundColor=3b82f6"


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"detail": "Missing token"}), 401
        token = header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"detail": "Token expired"}), 401
        except jwt.PyJWTError:
            return jsonify({"detail": "Invalid token"}), 401
        request.user_id = int(payload["sub"])
        return fn(*args, **kwargs)
    return wrapper


# ---------- Auth ----------
@app.post("/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"detail": "Name, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"detail": "Password must be at least 6 characters"}), 400
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as e:
        return jsonify({"detail": str(e)}), 400

    db = SessionLocal()
    if db.query(User).filter_by(email=email).first():
        return jsonify({"detail": "Email already registered"}), 409

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        avatar_url=avatar_for(name, email),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return jsonify({"id": user.id, "name": user.name, "email": user.email})


@app.post("/auth/login")
def login():
    # Accept form-encoded (OAuth2 style — frontend sends this) OR JSON
    if request.form:
        email = (request.form.get("username") or request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
    else:
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or data.get("username") or "").strip().lower()
        password = data.get("password") or ""

    db = SessionLocal()
    user = db.query(User).filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        return jsonify({"detail": "Invalid email or password"}), 401

    token = make_token(user)
    return jsonify({
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id, "name": user.name, "email": user.email,
            "avatar_url": user.avatar_url or avatar_for(user.name, user.email),
        },
    })


@app.get("/auth/me")
@auth_required
def me():
    db = SessionLocal()
    user = db.get(User, request.user_id)
    if not user:
        return jsonify({"detail": "Not found"}), 404
    return jsonify({
        "id": user.id, "name": user.name, "email": user.email,
        "avatar_url": user.avatar_url or avatar_for(user.name, user.email),
    })


# ---------- Progress / History ----------
@app.get("/api/progress")
@auth_required
def get_progress():
    db = SessionLocal()
    rows = db.query(Progress).filter_by(user_id=request.user_id).all()
    return jsonify([
        {"module": r.module, "level": r.level, "score": r.score,
         "updated_at": r.updated_at.isoformat() if r.updated_at else None}
        for r in rows
    ])


@app.post("/api/progress")
@auth_required
def upsert_progress():
    data = request.get_json(silent=True) or {}
    module = (data.get("module") or "").strip()
    level = int(data.get("level", 0))
    score = int(data.get("score", 0))
    if not module:
        return jsonify({"detail": "module required"}), 400
    db = SessionLocal()
    row = db.query(Progress).filter_by(user_id=request.user_id, module=module).first()
    if row:
        row.level = max(row.level, level)
        row.score = max(row.score, score)
    else:
        row = Progress(user_id=request.user_id, module=module, level=level, score=score)
        db.add(row)
    db.commit()
    return jsonify({"ok": True})


@app.get("/api/history")
@auth_required
def list_history():
    db = SessionLocal()
    rows = (db.query(History)
              .filter_by(user_id=request.user_id)
              .order_by(History.created_at.desc())
              .limit(100).all())
    return jsonify([
        {"action": r.action, "detail": r.detail,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ])


@app.post("/api/history")
@auth_required
def add_history():
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    if not action:
        return jsonify({"detail": "action required"}), 400
    db = SessionLocal()
    db.add(History(user_id=request.user_id, action=action, detail=data.get("detail")))
    db.commit()
    return jsonify({"ok": True})


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


# ---------- Static frontend ----------
@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:path>")
def static_proxy(path: str):
    target = (FRONTEND_DIR / path).resolve()
    try:
        target.relative_to(FRONTEND_DIR)
    except ValueError:
        abort(404)
    if target.is_dir():
        idx = target / "index.html"
        if idx.exists():
            return send_from_directory(target, "index.html")
        abort(404)
    if target.exists():
        return send_from_directory(target.parent, target.name)
    abort(404)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=True)
else:
    # gunicorn entry — ensure tables exist
    try:
        init_db()
    except Exception as e:
        print(f"[warn] init_db failed (will retry on first request): {e}")
