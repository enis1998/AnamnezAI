"""
AnamnezAI — Authentication & Yetkilendirme Modülü
JWT tabanlı, rol bazlı erişim kontrolü (HASTA | DOKTOR | PERSONEL | ADMIN)
"""

from datetime import datetime, timedelta
from typing import Optional
import os, json
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

import psycopg2.errors
from database import get_cursor

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
SECRET_KEY  = os.getenv("JWT_SECRET_KEY", "anamnezai-super-secret-key-change-in-production-2026")
ALGORITHM   = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# ─────────────────────────────────────────────
#  Roller
# ─────────────────────────────────────────────
class Role:
    PATIENT   = "patient"
    DOCTOR    = "doctor"
    PERSONNEL = "personnel"
    ADMIN     = "admin"

# ─────────────────────────────────────────────
#  Pydantic Models
# ─────────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = Role.PATIENT
    specialty: Optional[str] = None
    clinic_code: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    specialty: Optional[str] = None
    created_at: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ─────────────────────────────────────────────
#  DB Helpers
# ─────────────────────────────────────────────
def init_auth_tables():
    """Kullanıcı ve hasta profil tablolarını oluşturur (idempotent)."""
    # Tablolar database.py / pg_init_db() tarafından oluşturulur.
    # Burada yalnızca demo hesapları oluşturuyoruz.
    _ensure_demo_accounts()

def _ensure_demo_accounts():
    """Demo doktor ve admin hesaplarını oluşturur (yoksa)."""
    import uuid
    now = datetime.utcnow().isoformat()

    accounts = [
        (str(uuid.uuid4()), "Dr. Demo Kullanıcı", "doctor@anamnezai.tr",
         hash_password("doctor123"), Role.DOCTOR, "Acil Tıp", now),
        (str(uuid.uuid4()), "Sistem Yöneticisi", "admin@anamnezai.tr",
         hash_password("admin123"), Role.ADMIN, None, now),
    ]

    for (uid, name, email, pw_hash, role, specialty, created_at) in accounts:
        try:
            with get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, name, email, password_hash, role, specialty, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    (uid, name, email, pw_hash, role, specialty, created_at)
                )
            existing = get_user_by_email(email)
            if existing and existing["name"] == name:
                print(f"[Auth] Demo hesap hazır: {email}")
        except Exception as e:
            print(f"[Auth] Demo hesap oluşturma hatası ({email}): {e}")

# ─────────────────────────────────────────────
#  Password Hashing
# ─────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ─────────────────────────────────────────────
#  JWT
# ─────────────────────────────────────────────
def create_access_token(data: dict, expires_hours: int = ACCESS_TOKEN_EXPIRE_HOURS) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=expires_hours)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

# ─────────────────────────────────────────────
#  DB User Operations
# ─────────────────────────────────────────────
def get_user_by_email(email: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s AND is_active = 1", (email,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE user_id = %s AND is_active = 1", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def create_user(data: UserCreate) -> dict:
    import uuid
    if data.role == Role.DOCTOR:
        valid_codes = os.getenv("DOCTOR_CLINIC_CODES", "CLINIC2026,AYBU2026,DEMO2026").split(",")
        if not data.clinic_code or data.clinic_code.strip() not in valid_codes:
            raise HTTPException(
                status_code=403,
                detail="Geçersiz klinik kodu. Doktor kaydı için kurumunuzdan kod alın."
            )
    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, name, email, password_hash, role, specialty, clinic_code, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, data.name, data.email.lower().strip(),
                 hash_password(data.password), data.role,
                 data.specialty, data.clinic_code, now)
            )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Bu e-posta zaten kayıtlı.")
    return {"user_id": user_id, "name": data.name, "email": data.email,
            "role": data.role, "specialty": data.specialty, "created_at": now}

def get_patient_profile(user_id: str) -> Optional[dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM patient_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        p = dict(row)
        for f in ("chronic_diseases", "medications", "allergies"):
            val = p.get(f)
            if isinstance(val, list):
                pass  # JSONB already parsed by psycopg2
            elif isinstance(val, str):
                try:
                    p[f] = json.loads(val)
                except Exception:
                    p[f] = []
            else:
                p[f] = []
        return p

def upsert_patient_profile(user_id: str, profile: dict):
    now = datetime.utcnow().isoformat()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO patient_profiles
                (user_id, birth_year, gender, blood_type,
                 chronic_diseases, medications, allergies, notes, updated_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                birth_year       = EXCLUDED.birth_year,
                gender           = EXCLUDED.gender,
                blood_type       = EXCLUDED.blood_type,
                chronic_diseases = EXCLUDED.chronic_diseases,
                medications      = EXCLUDED.medications,
                allergies        = EXCLUDED.allergies,
                notes            = EXCLUDED.notes,
                updated_at       = EXCLUDED.updated_at
            """,
            (user_id,
             profile.get("birth_year"),
             profile.get("gender"),
             profile.get("blood_type"),
             json.dumps(profile.get("chronic_diseases", []), ensure_ascii=False),
             json.dumps(profile.get("medications", []), ensure_ascii=False),
             json.dumps(profile.get("allergies", []), ensure_ascii=False),
             profile.get("notes", ""),
             now)
        )

# ─────────────────────────────────────────────
#  FastAPI Auth Dependencies
# ─────────────────────────────────────────────
async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[dict]:
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return get_user_by_id(user_id)

async def require_auth(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    user = await get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Giriş yapmanız gerekiyor.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def require_doctor(current_user: dict = Depends(require_auth)) -> dict:
    if current_user["role"] not in (Role.DOCTOR, Role.ADMIN, Role.PERSONNEL):
        raise HTTPException(status_code=403, detail="Bu işlem için doktor yetkisi gerekiyor.")
    return current_user

async def require_admin(current_user: dict = Depends(require_auth)) -> dict:
    if current_user["role"] != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Bu işlem için admin yetkisi gerekiyor.")
    return current_user


# ─────────────────────────────────────────────
#  Audit Log
# ─────────────────────────────────────────────
def audit(action: str, user_id: str = "", user_role: str = "",
          resource: str = "", details: str = ""):
    """Kullanıcı eylemlerini PostgreSQL audit_log tablosuna kaydeder."""
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (action, user_id, user_role, resource, details, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (action, user_id, user_role, resource, details,
                 datetime.utcnow().isoformat())
            )
    except Exception as e:
        print(f"[Audit] Log hatası: {e}")
