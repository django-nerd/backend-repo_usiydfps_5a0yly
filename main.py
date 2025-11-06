import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

# Database helpers
from database import create_document

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        # Try to import database module
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


class ContactIn(BaseModel):
    name: str
    email: EmailStr
    subject: Optional[str] = None
    message: str


def send_email_via_smtp(name: str, email: str, subject: str, message: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    to_email = os.getenv("SMTP_TO", user)

    if not host or not user or not password or not to_email:
        # SMTP not fully configured; skip sending
        return False

    full_subject = subject or "New Portfolio Contact Message"
    body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = full_subject
    msg["From"] = formataddr((name, user))
    msg["To"] = to_email

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_email], msg.as_string())
    return True


@app.post("/contact")
async def submit_contact(payload: ContactIn):
    # Save to database
    try:
        doc = {
            "name": payload.name,
            "email": payload.email,
            "subject": payload.subject,
            "message": payload.message,
        }
        await create_document("contactmessage", doc)
    except Exception as e:
        # Still proceed to email, but report DB issue
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)[:120]}")

    # Attempt email send (non-blocking perspective; errors bubble if SMTP configured incorrectly)
    sent = False
    try:
        sent = send_email_via_smtp(payload.name, payload.email, payload.subject or "Portfolio Contact", payload.message)
    except Exception:
        sent = False

    return {"ok": True, "email_sent": sent}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
