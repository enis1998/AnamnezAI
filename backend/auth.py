"""
AnamnezAI — Authentication & Yetkilendirme Modülü
JWT tabanlı, rol bazlı erişim kontrolü (HASTA | DOKTOR | PERSONEL | ADMIN)
"""

from datetime import datetime, timedelta
from typing import Optional
import sqlite3, hashlib, os, threading, json
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
SECRET_KEY  = os.getenv("JWT_SECRET_KEY", "anamnezai-super-secret-key-change-in-production-2026")
ALGORITHM   = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

DB_PATH     = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "anamnezai.db"))
_db_lock    = threading.Lock()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# ─────────────────────────────────────────────
#  Roller
# ─────────────────────────────────────────────
class Role:
    PATIENT   = "patient"     # Hasta — sadece kendi verisini görür
    DOCTOR    = "doctor"      # Doktor — tüm kuyruğu yönetir
    PERSONNEL = "personnel"   # Sağlık personeli — yardımcı mod
    ADMIN     = "admin"       # Admin — kullanıcı yönetimi

# ─────────────────────────────────────────────
#  Pydantic Models
# ─────────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = Role.PATIENT
    specialty: Optional[str] = None  # Doktorlar için (Acil, Dahiliye vb.)
    clinic_code: Optional[str] = None  # Doktor kaydı için klinik kodu

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
    """Kullanıcı ve hasta profil tablolarını oluşturur."""
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    email       TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role        TEXT NOT NULL DEFAULT 'patient',
                    specialty   TEXT,
                    clinic_code TEXT,
                    created_at  TEXT NOT NULL,
                    is_active   INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patient_profiles (
                    user_id         TEXT PRIMARY KEY,
                    birth_year      INTEGER,
                    gender          TEXT,
                    blood_type      TEXT,
                    chronic_diseases TEXT,  -- JSON list
                    medications      TEXT,  -- JSON list
                    allergies        TEXT,  -- JSON list
                    notes            TEXT,
                    updated_at      TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            # Oturumları kullanıcıya bağla (sessions tablosuna patient_id eklenir)
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN patient_id TEXT")
            except sqlite3.OperationalError:
                pass  # Zaten var
            conn.commit()

            # Demo doktor hesabı oluştur (eğer yoksa)
            import uuid
            demo_doctor_email = "doctor@anamnezai.tr"
            existing = conn.execute(
                "SELECT user_id FROM users WHERE email=?", (demo_doctor_email,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO users (user_id, name, email, password_hash, role, specialty, created_at) VALUES (?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), "Dr. Demo Kullanıcı", demo_doctor_email,
                     hash_password("doctor123"), Role.DOCTOR, "Acil Tıp",
                     datetime.utcnow().isoformat())
                )
                conn.commit()
                print("[Auth] Demo doktor hesabı oluşturuldu: doctor@anamnezai.tr / doctor123")

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
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE user_id=? AND is_active=1", (user_id,)).fetchone()
        return dict(row) if row else None

def create_user(data: UserCreate) -> dict:
    import uuid
    # Doktor kaydı için klinik kodu kontrolü
    if data.role == Role.DOCTOR:
        valid_codes = os.getenv("DOCTOR_CLINIC_CODES", "CLINIC2026,AYBU2026,DEMO2026").split(",")
        if not data.clinic_code or data.clinic_code.strip() not in valid_codes:
            raise HTTPException(
                status_code=403,
                detail="Geçersiz klinik kodu. Doktor kaydı için kurumunuzdan kod alın."
            )
    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute(
                    "INSERT INTO users (user_id,name,email,password_hash,role,specialty,clinic_code,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (user_id, data.name, data.email.lower().strip(),
                     hash_password(data.password), data.role,
                     data.specialty, data.clinic_code, now)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                raise HTTPException(status_code=409, detail="Bu e-posta zaten kayıtlı.")
    return {"user_id": user_id, "name": data.name, "email": data.email,
            "role": data.role, "specialty": data.specialty, "created_at": now}

def get_patient_profile(user_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM patient_profiles WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        p = dict(row)
        for f in ("chronic_diseases", "medications", "allergies"):
            try:
                p[f] = json.loads(p[f] or "[]")
            except Exception:
                p[f] = []
        return p

def upsert_patient_profile(user_id: str, profile: dict):
    now = datetime.utcnow().isoformat()
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO patient_profiles (user_id, birth_year, gender, blood_type,
                    chronic_diseases, medications, allergies, notes, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    birth_year=excluded.birth_year, gender=excluded.gender,
                    blood_type=excluded.blood_type,
                    chronic_diseases=excluded.chronic_diseases,
                    medications=excluded.medications, allergies=excluded.allergies,
                    notes=excluded.notes, updated_at=excluded.updated_at
            """, (user_id,
                  profile.get("birth_year"),
                  profile.get("gender"),
                  profile.get("blood_type"),
                  json.dumps(profile.get("chronic_diseases", []), ensure_ascii=False),
                  json.dumps(profile.get("medications", []), ensure_ascii=False),
                  json.dumps(profile.get("allergies", []), ensure_ascii=False),
                  profile.get("notes", ""),
                  now))
            conn.commit()

# ─────────────────────────────────────────────
#  FastAPI Auth Dependencies
# ─────────────────────────────────────────────
async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[dict]:
    """Token varsa kullanıcıyı döndürür, yoksa None (opsiyonel auth için)."""
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
    """Token zorunlu — yoksa 401."""
    user = await get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Giriş yapmanız gerekiyor.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def require_doctor(current_user: dict = Depends(require_auth)) -> dict:
    """Sadece doktor ve admin erişebilir."""
    if current_user["role"] not in (Role.DOCTOR, Role.ADMIN, Role.PERSONNEL):
        raise HTTPException(status_code=403, detail="Bu işlem için doktor yetkisi gerekiyor.")
    return current_user

async def require_admin(current_user: dict = Depends(require_auth)) -> dict:
    """Sadece admin erişebilir."""
    if current_user["role"] != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Bu işlem için admin yetkisi gerekiyor.")
    return current_user

