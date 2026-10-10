import os
import time
import hmac
import secrets
import sqlite3
from contextlib import closing
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from telegram import Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_SECRET = os.environ["API_SECRET"]
DB_PATH = os.environ.get("DB_PATH", "virtual_numbers.db")
CODE_TTL_SECONDS = int(os.environ.get("CODE_TTL_SECONDS", "300"))

app = FastAPI(title="Private Messenger Virtual Number API")
bot = Bot(BOT_TOKEN)

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS codes (
            phone TEXT PRIMARY KEY,
            code_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0
        )""")
        db.commit()

@app.on_event("startup")
def startup():
    init_db()

def require_secret(x_api_key):
    if not x_api_key or not hmac.compare_digest(x_api_key, API_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")

class RequestCode(BaseModel):
    phone: str = Field(min_length=12, max_length=12, pattern=r"^\+7\d{10}$")

class VerifyCode(BaseModel):
    phone: str = Field(min_length=12, max_length=12, pattern=r"^\+7\d{10}$")
    code: str = Field(min_length=5, max_length=5, pattern=r"^\d{5}$")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/auth/request-code")
async def request_code(body: RequestCode, x_api_key: str | None = Header(default=None)):
    require_secret(x_api_key)
    with closing(sqlite3.connect(DB_PATH)) as db:
        row = db.execute("SELECT chat_id FROM users WHERE phone=?", (body.phone,)).fetchone()
        if not row:
            # Do not reveal whether a number exists.
            return {"ok": True, "message": "If this virtual ID exists, a code was sent."}
        chat_id = row[0]
        code = f"{secrets.randbelow(100000):05d}"
        code_hash = hmac.new(API_SECRET.encode(), f"{body.phone}:{code}".encode(), "sha256").hexdigest()
        db.execute("INSERT OR REPLACE INTO codes(phone, code_hash, expires_at, attempts) VALUES (?, ?, ?, 0)",
                   (body.phone, code_hash, int(time.time()) + CODE_TTL_SECONDS))
        db.commit()
    await bot.send_message(chat_id=chat_id, text=f"Код входа в твоё приложение: {code}\nДействует 5 минут. Никому его не сообщай.")
    return {"ok": True, "message": "If this virtual ID exists, a code was sent."}

@app.post("/auth/verify-code")
def verify_code(body: VerifyCode, x_api_key: str | None = Header(default=None)):
    require_secret(x_api_key)
    with closing(sqlite3.connect(DB_PATH)) as db:
        row = db.execute("SELECT code_hash, expires_at, attempts FROM codes WHERE phone=?", (body.phone,)).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired code")
        code_hash, expires_at, attempts = row
        if attempts >= 5 or int(time.time()) > expires_at:
            db.execute("DELETE FROM codes WHERE phone=?", (body.phone,))
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid or expired code")
        expected = hmac.new(API_SECRET.encode(), f"{body.phone}:{body.code}".encode(), "sha256").hexdigest()
        if not hmac.compare_digest(expected, code_hash):
            db.execute("UPDATE codes SET attempts=attempts+1 WHERE phone=?", (body.phone,))
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid or expired code")
        db.execute("DELETE FROM codes WHERE phone=?", (body.phone,))
        db.commit()
    # Production apps should issue a signed session token here.
    return {"ok": True, "authenticated": True, "phone": body.phone}
