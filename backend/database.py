"""
AnamnezAI — PostgreSQL Veritabanı Yönetimi
psycopg2 + ThreadedConnectionPool kullanır.

Bağlantı önceliği:
  1. DATABASE_URL ortam değişkeni (tam connection string)
  2. POSTGRES_* ayrı değişkenler
  3. Geliştirme ortamı varsayılanları
"""

import os
import threading
import psycopg2
import psycopg2.extras
import psycopg2.pool
import psycopg2.errors
from contextlib import contextmanager
from typing import Optional

# ─────────────────────────────────────────────
#  Bağlantı Yapılandırması
# ─────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")

POSTGRES_HOST     = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT     = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB       = os.getenv("POSTGRES_DB", "anamnezai")
POSTGRES_USER     = os.getenv("POSTGRES_USER", "anamnezai")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "anamnezai_secret")

def _build_dsn() -> str:
    if DATABASE_URL:
        return DATABASE_URL
    return (
        f"host={POSTGRES_HOST} port={POSTGRES_PORT} "
        f"dbname={POSTGRES_DB} user={POSTGRES_USER} "
        f"password={POSTGRES_PASSWORD} "
        f"connect_timeout=10 application_name=anamnezai"
    )

# ─────────────────────────────────────────────
#  Bağlantı Havuzu
# ─────────────────────────────────────────────
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()

def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=20,
                    dsn=_build_dsn(),
                )
                print(f"[DB] PostgreSQL bağlantı havuzu başlatıldı — host={POSTGRES_HOST} db={POSTGRES_DB}")
    return _pool


@contextmanager
def get_conn():
    """Thread-safe bağlantı context manager — havuzdan al, işten sonra geri koy."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(cursor_factory=psycopg2.extras.RealDictCursor):
    """Cursor context manager — commit & kapatma otomatik."""
    with get_conn() as conn:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


# ─────────────────────────────────────────────
#  Tablo İlk Kurulumu
# ─────────────────────────────────────────────
INIT_SQL = """
-- Oturumlar
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions (created_at DESC);

-- Klinik özetler
CREATE TABLE IF NOT EXISTS summaries (
    session_id  TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Kullanıcılar
CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'patient',
    specialty     TEXT,
    clinic_code   TEXT,
    created_at    TEXT NOT NULL,
    is_active     INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- Hasta profilleri
CREATE TABLE IF NOT EXISTS patient_profiles (
    user_id          TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    birth_year       INTEGER,
    gender           TEXT,
    blood_type       TEXT,
    chronic_diseases JSONB DEFAULT '[]',
    medications      JSONB DEFAULT '[]',
    allergies        JSONB DEFAULT '[]',
    notes            TEXT,
    updated_at       TEXT
);

-- Denetim kaydı
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    action      TEXT NOT NULL,
    user_id     TEXT,
    user_role   TEXT,
    resource    TEXT,
    details     TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at DESC);
"""

def init_db():
    """Tüm tabloları oluşturur (idempotent)."""
    with get_cursor() as cur:
        cur.execute(INIT_SQL)
    print("[DB] PostgreSQL tabloları hazır.")


def close_pool():
    """Uygulama kapanırken havuzu temiz kapat."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        print("[DB] PostgreSQL bağlantı havuzu kapatıldı.")

