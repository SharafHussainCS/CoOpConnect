from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import sqlite3
import hashlib
import jwt
import os
import shutil
import re
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

app = FastAPI(title="Co-op Management System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "coop_secret_key_2024"
ALGORITHM = "HS256"
DB_PATH = "coop.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "reports").mkdir(exist_ok=True)
(UPLOAD_DIR / "evaluations").mkdir(exist_ok=True)
(UPLOAD_DIR / "resumes").mkdir(exist_ok=True)

# Database Setup -----------------------------------------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute(
        """CREATE TABLE IF NOT EXISTS applicants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        student_id TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        program TEXT,
        year TEXT,
        resume_path TEXT,
        applied_at TEXT DEFAULT (datetime('now')),
        provisional_status TEXT DEFAULT 'pending',  -- pending/accepted/rejected
        provisional_notes TEXT,
        final_status TEXT DEFAULT 'pending',         -- pending/accepted/rejected
        final_notes TEXT,
        reviewed_at TEXT
    )""")

    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,  -- student/supervisor/admin
        student_id TEXT,
        email TEXT UNIQUE NOT NULL,
        name TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute(
        """CREATE TABLE IF NOT EXISTS work_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        company TEXT NOT NULL,
        position TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        supervisor_email TEXT,
        report_path TEXT,
        report_submitted_at TEXT,
        eval_submitted_at TEXT,
        eval_path TEXT,
        eval_online_data TEXT,
        status TEXT DEFAULT 'active',  -- active/completed/rejected
        rejection_reason TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute(
        """CREATE TABLE IF NOT EXISTS supervisor_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supervisor_email TEXT NOT NULL,
        student_id TEXT NOT NULL,
        work_term_id INTEGER,
        added_at TEXT DEFAULT (datetime('now'))
    )""")

    # Default admin account (password: admin123)
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute(
        """INSERT OR IGNORE INTO users (username, password_hash, role, email, name)
             VALUES ('admin', ?, 'admin', 'admin@torontomu.ca', 'Co-op Coordinator')""", (admin_hash,))

    conn.commit()
    conn.close()

init_db()

# Auth Helpers ------------------------------------------------------------------

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def create_token(user_id: int, role: str, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return verify_token(credentials.credentials)

def require_role(*roles):
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker

# Static Files ----------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    return FileResponse("static/index.html")

@app.get("/{page}", response_class=HTMLResponse)
def serve_page(page: str):
    path = f"static/pages/{page}.html"
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse("static/index.html")

# Application Endpoints ----------------------------------------------------------------------------

@app.post("/api/apply")
async def apply(
    name: str = Form(...),
    student_id: str = Form(...),
    email: str = Form(...),
    program: str = Form(...),
    year: str = Form(...),
    resume: UploadFile = File(None)
):
    # Validate student ID format
    if not re.match(r'^\d{9}$', student_id):
        raise HTTPException(400, "Invalid student ID format. Must be 8-9 digits.")
    # Validate email format
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise HTTPException(400, "Invalid email format.")
    # Simulate university DB check: email must end in university domain
    if not email.endswith("@torontomu.ca"):
        raise HTTPException(400, "Email not found in university database. Use your university email.")

    resume_path = None
    if resume and resume.filename:
        ext = Path(resume.filename).suffix
        if ext.lower() not in ['.pdf', '.doc', '.docx']:
            raise HTTPException(400, "Resume must be PDF, DOC, or DOCX.")
        fname = f"{student_id}_resume{ext}"
        fpath = UPLOAD_DIR / "resumes" / fname
        with open(fpath, "wb") as f:
            shutil.copyfileobj(resume.file, f)
        resume_path = str(fpath)

    conn = get_db()
    try:
        conn.execute("""INSERT INTO applicants (name, student_id, email, program, year, resume_path)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (name, student_id, email, program, year, resume_path))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Student ID or email already applied.")
    finally:
        conn.close()
    return {"message": "Application submitted successfully."}


@app.post("/api/application-status")
def check_application_status(
    student_id: str = Form(...),
    email: str = Form(...)
):
    conn = get_db()
    row = conn.execute(
        "SELECT name, provisional_status, provisional_notes, final_status, final_notes, applied_at FROM applicants WHERE LOWER(student_id)=LOWER(?) AND LOWER(email)=LOWER(?)",
        (student_id, email)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "No application found for this Student ID and email combination.")
    return dict(row)

# Auth Endpoints ----------------------------------------------------------------------------

@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?) OR LOWER(email)=LOWER(?)", (username, username)).fetchone()
    conn.close()
    if not user or user["password_hash"] != hash_password(password):
        raise HTTPException(401, "Invalid credentials.")
    token = create_token(user["id"], user["role"], user["username"])
    return {"token": token, "role": user["role"], "name": user["name"], "username": user["username"]}

@app.post("/api/signup/student")
def signup_student(
    username: str = Form(...),
    password: str = Form(...),
    student_id: str = Form(...),
    email: str = Form(...)
):
    conn = get_db()
    # Must be provisionally or finally accepted
    app_row = conn.execute("""SELECT * FROM applicants WHERE student_id=? AND email=?
                               AND (provisional_status='accepted' OR final_status='accepted')""",
                           (student_id, email)).fetchone()
    if not app_row:
        conn.close()
        raise HTTPException(400, "No accepted application found for this Student ID and email.")
    try:
        conn.execute("""INSERT INTO users (username, password_hash, role, student_id, email, name)
                        VALUES (?, ?, 'student', ?, ?, ?)""",
                     (username, hash_password(password), student_id, email, app_row["name"]))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username or email already registered.")
    finally:
        conn.close()
    return {"message": "Student account created."}

@app.post("/api/signup/supervisor")
def signup_supervisor(
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    name: str = Form(...)
):
    conn = get_db()
    # Supervisor email must be pre-added by a student
    exists = conn.execute("SELECT 1 FROM supervisor_assignments WHERE supervisor_email=?", (email,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(400, "Your email has not been added by any co-op student. Ask your student to add you first.")
    try:
        conn.execute("""INSERT INTO users (username, password_hash, role, email, name)
                        VALUES (?, ?, 'supervisor', ?, ?)""",
                     (username, hash_password(password), email, name))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Username or email already registered.")
    finally:
        conn.close()
    return {"message": "Supervisor account created."}

# Student Endpoints ----------------------------------------------------------------------------

@app.get("/api/student/workterms")
def get_my_workterms(user=Depends(require_role("student"))):
    conn = get_db()
    u = conn.execute("SELECT student_id FROM users WHERE username=?", (user["username"],)).fetchone()
    terms = conn.execute("SELECT * FROM work_terms WHERE student_id=? ORDER BY start_date DESC", (u["student_id"],)).fetchall()
    conn.close()
    return [dict(t) for t in terms]

@app.post("/api/student/workterms")
def add_workterm(
    company: str = Form(...),
    position: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    supervisor_email: str = Form(...),
    user=Depends(require_role("student"))
):
    conn = get_db()
    u = conn.execute("SELECT student_id FROM users WHERE username=?", (user["username"],)).fetchone()
    cur = conn.execute("""INSERT INTO work_terms (student_id, company, position, start_date, end_date, supervisor_email)
                          VALUES (?, ?, ?, ?, ?, ?)""",
                       (u["student_id"], company, position, start_date, end_date, supervisor_email))
    wt_id = cur.lastrowid
    # Register supervisor email for sign-up eligibility
    conn.execute("""INSERT OR IGNORE INTO supervisor_assignments (supervisor_email, student_id, work_term_id)
                    VALUES (?, ?, ?)""", (supervisor_email, u["student_id"], wt_id))
    conn.commit()
    conn.close()
    return {"message": "Work term added.", "id": wt_id}

@app.post("/api/student/workterms/{wt_id}/report")
async def submit_report(
    wt_id: int,
    report: UploadFile = File(...),
    user=Depends(require_role("student"))
):
    conn = get_db()
    u = conn.execute("SELECT student_id FROM users WHERE username=?", (user["username"],)).fetchone()
    wt = conn.execute("SELECT * FROM work_terms WHERE id=? AND student_id=?", (wt_id, u["student_id"])).fetchone()
    if not wt:
        conn.close()
        raise HTTPException(404, "Work term not found.")

    # Check deadline
    end_date = datetime.strptime(wt["end_date"], "%Y-%m-%d")
    deadline = end_date + timedelta(days=30)
    if datetime.now() > deadline:
        conn.close()
        raise HTTPException(400, f"Report deadline was {deadline.strftime('%B %d, %Y')}. Submission is closed.")

    if not report.filename.endswith(".pdf"):
        conn.close()
        raise HTTPException(400, "Report must be a PDF file.")

    fname = f"{u['student_id']}_wt{wt_id}_report.pdf"
    fpath = UPLOAD_DIR / "reports" / fname
    with open(fpath, "wb") as f:
        shutil.copyfileobj(report.file, f)

    conn.execute("UPDATE work_terms SET report_path=?, report_submitted_at=datetime('now') WHERE id=?",
                 (str(fpath), wt_id))
    conn.commit()
    conn.close()
    return {"message": "Report submitted."}

@app.post("/api/student/workterms/{wt_id}/update-supervisor")
def update_supervisor(
    wt_id: int,
    supervisor_email: str = Form(...),
    user=Depends(require_role("student"))
):
    conn = get_db()
    u = conn.execute("SELECT student_id FROM users WHERE username=?", (user["username"],)).fetchone()
    wt = conn.execute("SELECT * FROM work_terms WHERE id=? AND student_id=?", (wt_id, u["student_id"])).fetchone()
    if not wt:
        conn.close()
        raise HTTPException(404, "Work term not found.")
    conn.execute("UPDATE work_terms SET supervisor_email=? WHERE id=?", (supervisor_email, wt_id))
    conn.execute("""INSERT OR IGNORE INTO supervisor_assignments (supervisor_email, student_id, work_term_id)
                    VALUES (?, ?, ?)""", (supervisor_email, u["student_id"], wt_id))
    conn.commit()
    conn.close()
    return {"message": "Supervisor updated."}

# Supervisor Endpoints ----------------------------------------------------------------------------

@app.get("/api/supervisor/students")
def get_supervisor_students(user=Depends(require_role("supervisor"))):
    conn = get_db()
    sup_user = conn.execute("SELECT email FROM users WHERE username=?", (user["username"],)).fetchone()
    terms = conn.execute("""
        SELECT wt.*, u.name as student_name
        FROM work_terms wt
        JOIN users u ON u.student_id = wt.student_id
        WHERE wt.supervisor_email=?
        ORDER BY wt.start_date DESC
    """, (sup_user["email"],)).fetchall()
    conn.close()
    return [dict(t) for t in terms]

@app.post("/api/supervisor/workterms/{wt_id}/evaluate")
async def submit_evaluation(
    wt_id: int,
    eval_type: str = Form(...),  # "pdf" or "online"
    # Online form fields
    technical_skills: Optional[str] = Form(None),
    communication: Optional[str] = Form(None),
    teamwork: Optional[str] = Form(None),
    attitude: Optional[str] = Form(None),
    overall_rating: Optional[str] = Form(None),
    comments: Optional[str] = Form(None),
    # PDF upload
    eval_pdf: UploadFile = File(None),
    user=Depends(require_role("supervisor"))
):
    conn = get_db()
    sup_user = conn.execute("SELECT email FROM users WHERE username=?", (user["username"],)).fetchone()
    wt = conn.execute("SELECT * FROM work_terms WHERE id=? AND supervisor_email=?",
                      (wt_id, sup_user["email"])).fetchone()
    if not wt:
        conn.close()
        raise HTTPException(404, "Work term not found or not assigned to you.")

    eval_path = None
    online_data = None

    if eval_type == "pdf" and eval_pdf:
        if not eval_pdf.filename.endswith(".pdf"):
            conn.close()
            raise HTTPException(400, "Evaluation must be a PDF.")
        fname = f"wt{wt_id}_eval.pdf"
        fpath = UPLOAD_DIR / "evaluations" / fname
        with open(fpath, "wb") as f:
            shutil.copyfileobj(eval_pdf.file, f)
        eval_path = str(fpath)
    elif eval_type == "online":
        import json
        online_data = json.dumps({
            "technical_skills": technical_skills,
            "communication": communication,
            "teamwork": teamwork,
            "attitude": attitude,
            "overall_rating": overall_rating,
            "comments": comments
        })
    else:
        conn.close()
        raise HTTPException(400, "Must provide either PDF or online evaluation.")

    conn.execute("""UPDATE work_terms SET eval_submitted_at=datetime('now'),
                    eval_path=?, eval_online_data=? WHERE id=?""",
                 (eval_path, online_data, wt_id))
    conn.commit()
    conn.close()
    return {"message": "Evaluation submitted."}

# Admin Endpoints ----------------------------------------------------------------------------

@app.get("/api/admin/applicants")
def admin_get_applicants(year: Optional[str] = None, user=Depends(require_role("admin"))):
    conn = get_db()
    if year:
        rows = conn.execute("SELECT * FROM applicants WHERE year=? ORDER BY applied_at DESC", (year,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM applicants ORDER BY applied_at DESC").fetchall()
    years = conn.execute("SELECT DISTINCT year FROM applicants ORDER BY year DESC").fetchall()
    conn.close()
    return {
        "applicants": [dict(r) for r in rows],
        "years": [r["year"] for r in years]
    }

@app.patch("/api/admin/applicants/{app_id}/provisional")
def update_provisional(
    app_id: int,
    status: str = Form(...),
    notes: str = Form(""),
    user=Depends(require_role("admin"))
):
    if status not in ("accepted", "rejected"):
        raise HTTPException(400, "Status must be accepted or rejected.")
    conn = get_db()
    conn.execute("""UPDATE applicants SET provisional_status=?, provisional_notes=?, reviewed_at=datetime('now')
                    WHERE id=?""", (status, notes, app_id))
    conn.commit()
    conn.close()
    return {"message": f"Provisional status updated to {status}."}

@app.patch("/api/admin/applicants/{app_id}/final")
def update_final(
    app_id: int,
    status: str = Form(...),
    notes: str = Form(""),
    user=Depends(require_role("admin"))
):
    if status not in ("accepted", "rejected"):
        raise HTTPException(400, "Status must be accepted or rejected.")
    conn = get_db()
    conn.execute("""UPDATE applicants SET final_status=?, final_notes=?, reviewed_at=datetime('now')
                    WHERE id=?""", (status, notes, app_id))
    conn.commit()
    conn.close()
    return {"message": f"Final status updated to {status}."}

@app.get("/api/admin/resume/{app_id}")
def view_resume(app_id: int, token: str = None):
    # Manually verify the token and check admin role
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = verify_token(token)
    except:
        raise HTTPException(401, "Invalid or expired token")
    if payload["role"] != "admin":
        raise HTTPException(403, "Insufficient permissions")

    conn = get_db()
    row = conn.execute(
        "SELECT resume_path, name FROM applicants WHERE id=?", (app_id,)
    ).fetchone()
    conn.close()

    if not row or not row["resume_path"]:
        raise HTTPException(404, "No resume found for this applicant.")

    path = Path(row["resume_path"])
    if not path.exists():
        raise HTTPException(404, "Resume file not found on server.")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        media_type = "application/pdf"
    elif suffix == ".doc":
        media_type = "application/msword"
    elif suffix == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(path),
        media_type=media_type,
        headers={"Content-Disposition": "inline"}
    )
    
@app.get("/api/admin/students")
def admin_get_students(user=Depends(require_role("admin"))):
    conn = get_db()
    students = conn.execute("""
        SELECT u.*, a.provisional_status, a.final_status
        FROM users u
        LEFT JOIN applicants a ON a.student_id = u.student_id
        WHERE u.role='student'
        ORDER BY u.created_at DESC
    """).fetchall()
    workterms = conn.execute("""
        SELECT wt.*, u.name as student_name
        FROM work_terms wt
        JOIN users u ON u.student_id = wt.student_id
        ORDER BY wt.start_date DESC
    """).fetchall()
    conn.close()
    return {
        "students": [dict(s) for s in students],
        "workterms": [dict(w) for w in workterms]
    }

@app.get("/api/admin/notifications")
def admin_notifications(user=Depends(require_role("admin"))):
    conn = get_db()
    # Students with overdue reports (past 30-day deadline, no report)
    overdue = conn.execute("""
        SELECT wt.*, u.name as student_name, u.email as student_email
        FROM work_terms wt
        JOIN users u ON u.student_id = wt.student_id
        WHERE wt.report_path IS NULL
          AND date(wt.end_date, '+30 days') < date('now')
        ORDER BY wt.end_date
    """).fetchall()
    # Missing evaluations
    no_eval = conn.execute("""
        SELECT wt.*, u.name as student_name
        FROM work_terms wt
        JOIN users u ON u.student_id = wt.student_id
        WHERE wt.eval_submitted_at IS NULL
          AND wt.supervisor_email IS NOT NULL
        ORDER BY wt.end_date
    """).fetchall()
    conn.close()
    return {
        "overdue_reports": [dict(r) for r in overdue],
        "missing_evaluations": [dict(r) for r in no_eval]
    }

@app.patch("/api/admin/workterms/{wt_id}/reject")
def reject_workterm(
    wt_id: int,
    reason: str = Form(...),
    user=Depends(require_role("admin"))
):
    conn = get_db()
    conn.execute("UPDATE work_terms SET status='rejected', rejection_reason=? WHERE id=?", (reason, wt_id))
    conn.commit()
    conn.close()
    return {"message": "Work term marked as rejected."}


@app.delete("/api/admin/students/{student_id}")
def delete_student(student_id: str, user=Depends(require_role("admin"))):
    conn = get_db()
    # Get user info first
    student = conn.execute("SELECT * FROM users WHERE student_id=? AND role='student'", (student_id,)).fetchone()
    if not student:
        conn.close()
        raise HTTPException(404, "Student not found.")
    # Delete work terms and related data
    conn.execute("DELETE FROM supervisor_assignments WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM work_terms WHERE student_id=?", (student_id,))
    # Delete applicant record
    conn.execute("DELETE FROM applicants WHERE student_id=?", (student_id,))
    # Delete user account
    conn.execute("DELETE FROM users WHERE student_id=? AND role='student'", (student_id,))
    conn.commit()
    conn.close()
    return {"message": "Student and all associated data deleted."}


@app.get("/api/admin/report/{wt_id}")
def view_report(wt_id: int, token: str = None):
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = verify_token(token)
    except:
        raise HTTPException(401, "Invalid or expired token")
    if payload["role"] != "admin":
        raise HTTPException(403, "Insufficient permissions")
    conn = get_db()
    row = conn.execute("SELECT report_path FROM work_terms WHERE id=?", (wt_id,)).fetchone()
    conn.close()
    if not row or not row["report_path"]:
        raise HTTPException(404, "No report found for this work term.")
    path = Path(row["report_path"])
    if not path.exists():
        raise HTTPException(404, "Report file not found on server.")
    return FileResponse(path=str(path), media_type="application/pdf", headers={"Content-Disposition": "inline"})

@app.get("/api/admin/evaluation/{wt_id}")
def view_evaluation(wt_id: int, token: str = None):
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = verify_token(token)
    except:
        raise HTTPException(401, "Invalid or expired token")
    if payload["role"] != "admin":
        raise HTTPException(403, "Insufficient permissions")
    conn = get_db()
    row = conn.execute("SELECT eval_path, eval_online_data FROM work_terms WHERE id=?", (wt_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Work term not found.")
    if row["eval_path"]:
        path = Path(row["eval_path"])
        if not path.exists():
            raise HTTPException(404, "Evaluation file not found on server.")
        return FileResponse(path=str(path), media_type="application/pdf", headers={"Content-Disposition": "inline"})
    elif row["eval_online_data"]:
        import json
        data = json.loads(row["eval_online_data"])
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
        <title>Evaluation</title>
        <style>body{{font-family:sans-serif;max-width:600px;margin:2rem auto;color:#1a2535}}
        h2{{color:#002D71}}table{{width:100%;border-collapse:collapse;margin-top:1rem}}
        td,th{{padding:0.6rem 1rem;border:1px solid #dde3ee;text-align:left}}
        th{{background:#f7f9fc;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em}}</style>
        </head><body>
        <h2>Online Evaluation</h2>
        <table>
        <tr><th>Category</th><th>Rating</th></tr>
        <tr><td>Technical Skills</td><td>{data.get('technical_skills','—')}</td></tr>
        <tr><td>Communication</td><td>{data.get('communication','—')}</td></tr>
        <tr><td>Teamwork</td><td>{data.get('teamwork','—')}</td></tr>
        <tr><td>Attitude</td><td>{data.get('attitude','—')}</td></tr>
        <tr><td>Overall Rating</td><td>{data.get('overall_rating','—')}</td></tr>
        </table>
        <h3 style="margin-top:1.5rem;color:#002D71">Comments</h3>
        <p style="color:#5a6778">{data.get('comments','No comments provided.')}</p>
        </body></html>"""
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)
    raise HTTPException(404, "No evaluation submitted for this work term.")

# Template Download ----------------------------------------------------------------------------

@app.get("/api/report-template")
def get_template():
    # Return a simple text-based template info; in production this would be a real PDF
    template_path = UPLOAD_DIR / "report_template.txt"
    if not template_path.exists():
        with open(template_path, "w") as f:
            f.write("CO-OP WORK TERM REPORT TEMPLATE\n")
            f.write("="*40 + "\n\n")
            f.write("Student Name: _______________\n")
            f.write("Student ID: _______________\n")
            f.write("Company: _______________\n")
            f.write("Work Term: _______________\n\n")
            f.write("1. EXECUTIVE SUMMARY\n...\n\n")
            f.write("2. COMPANY OVERVIEW\n...\n\n")
            f.write("3. JOB DESCRIPTION\n...\n\n")
            f.write("4. WORK ACCOMPLISHED\n...\n\n")
            f.write("5. LEARNING OUTCOMES\n...\n\n")
            f.write("6. CONCLUSIONS\n...\n")
    return FileResponse(template_path, filename="coop_report_template.txt")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
