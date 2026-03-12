# CoOpConnect

A full-stack co-op program management web application built with **FastAPI** (Python), **SQLite**, and **vanilla HTML/CSS/JS**.

## Project Structure
```
coop_app/
├── main.py                    # FastAPI backend (all API routes)
├── requirements.txt           # Python dependencies
├── coop.db                    # Auto-created SQLite database
├── uploads/                   # Uploaded files (auto-created)
│   ├── reports/
│   └── evaluations/
└── static/
    ├── index.html             # Welcome / Home page
    ├── css/
    │   └── shared.css         # Shared styles for all pages
    └── pages/
        ├── apply.html         # Application form (multi-step)
        ├── login.html         # Login & Signup page
        ├── student.html       # Student dashboard
        ├── supervisor.html    # Supervisor dashboard
        └── admin.html         # Admin / Coordinator dashboard
```

## Setup & Running

### 1. Install dependencies
```bash
pip install fastapi uvicorn python-multipart PyJWT
```

### 2. Run the server
```bash
python -m uvicorn main:app --reload --port 8000
```

### 3. Open in browser
```
  http://localhost:8000
```

## Default Admin Account

Username: `admin`
Password: `admin123`

## Features

### Welcome Page (`/`)
- Landing page with two options: Apply to Co-op, or Sign In

### Application Page (`/pages/apply`)
- 4-step multi-step form: Personal Info → Program → Documents → Legal Agreement
- Validates student ID format (8–9 digits)
- Validates university email domain
- Requires confirmation of 3 legal checkboxes
- Thank you confirmation screen after submission

### Co-op Portal (`/pages/login`)
- Unified login for students, supervisors, and admins
- Signup for **students**: requires accepted application (student ID + email must match)
- Signup for **supervisors**: email must first be added by a student

### Student Dashboard (`/pages/student`)
- View all work terms with status indicators
- Add new work terms (triggers supervisor email registration)
- Submit work term report as **PDF upload** or **built-in template** (fills out and submits)
- 30-day deadline enforcement from work term end date
- Update supervisor email for existing work terms

### Supervisor Dashboard (`/pages/supervisor`)
- View all assigned students
- Submit evaluations via **PDF upload** or **online form** (5-dimension rating)
- Can resubmit evaluations; work term marked as evaluated regardless

### Admin Dashboard (`/pages/admin`)
- **Applicants page**: 
  - Filter by year via dropdown chips
  - Expandable rows for each applicant
  - Provisional accept/reject with notes
  - Final accept/reject with notes
  - Stats: total, provisionally accepted, finally accepted, rejected
- **Co-op Students page**:
  - All work terms with report/evaluation status
  - Reject a work term assignment with reason
  - Notifications sub-page: overdue reports + missing evaluations


## Database Tables
`applicants` -  Co-op applications with provisional/final status
`users` -  Accounts for students, supervisors, and admins
`work_terms` -  Work placements with reports and evaluations
`supervisor_assignments` -  Links supervisor emails to students


## API Endpoints

POST:   `/api/apply`                                      -  Submit co-op application
POST:   `/api/login`                                      -  Authenticate user
POST:   `/api/signup/student`                             -  Create student account
POST:   `/api/signup/supervisor`                          -  Create supervisor account
GET:    `/api/student/workterms`                          -  List student's work terms
POST:   `/api/student/workterms`                          -  Add work term
POST:   `/api/student/workterms/{id}/report`              -  Submit report
POST:   `/api/student/workterms/{id}/update-supervisor`   -  Update supervisor
GET:    `/api/supervisor/students`                        -  List supervisor's students
POST:   `/api/supervisor/workterms/{id}/evaluate`         -  Submit evaluation
GET:    `/api/admin/applicants`                           -  List all applicants
PATCH:  `/api/admin/applicants/{id}/provisional`          -  Set provisional status
PATCH:  `/api/admin/applicants/{id}/final`                -  Set final status
GET:    `/api/admin/students`                             -  List students + work terms
GET:    `/api/admin/notifications`                        -  Get overdue/missing items
PATCH:  `/api/admin/workterms/{id}/reject`                -  Reject a work term
GET:    `/api/report-template`                            -  Download report template

## Notes

- University email validation accepts: `@torontomu.ca`
- Tokens expire after 8 hours (JWT-based)
- All file uploads stored in `uploads/` -  directory
- Admin account is build in
