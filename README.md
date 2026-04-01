# CoOpConnect

A full-stack co-op program management web application built with **Python** (FastAPI), **SQL** (SQLite), and **Standard HTML/CSS/JS**.

## Project Structure
```
CoOpConnect/
├── main.py                    # FastAPI backend (all API routes)
├── coop.db                    # Auto-created SQLite database
├── uploads/                   # Uploaded files (auto-created)
│   ├── reports/
│   ├── resumes/  
│   └── evaluations/
└── static/
    ├── index.html             # Home page
    ├── css/
    │   ├── shared.css         # Shared styles for all pages
    │   ├── index.css          # Styles for index page
    │   ├── apply.css          # Styles for apply page
    │   ├── login.css          # Styles for login page
    │   ├── student.css        # Styles for student page
    │   ├── supervisor.css     # Styles for supervisor page
    │   └── admin.css          # Styles for admin page
    └── pages/
        ├── apply.html         # Application form
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

Username: `admin`\
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
- **Work Terms** tab: view all work terms with status indicators (report due/overdue, evaluation pending)
- **To Do** tab: highlights work terms with outstanding actions; red badge shows count
- Add new work terms (triggers supervisor email registration)
- Submit work term report as **PDF upload** (drag-and-drop) or **built-in template** (generates and submits PDF)
- 30-day report deadline enforced from work term end date
- Update supervisor email for existing work terms
- Pop-up notification on login when coordinator has sent a reminder

### Supervisor Dashboard (`/pages/supervisor`)
- **Co-op Employees** tab: view all assigned students with evaluation status
- **To Do** tab: lists students whose evaluations are still pending; red badge shows count
- Submit evaluations via **PDF upload** (drag-and-drop) or **online form** (5-dimension rating)
- Can resubmit evaluations at any time
- Pop-up notification on login when coordinator has sent a reminder

### Admin Dashboard (`/pages/admin`)
- **Applicants page**:
  - Filter by year and by status (Pending, Provisionally Accepted, Rejected)
  - Expandable rows per applicant with provisional and final decision controls
  - Rejecting provisional auto-rejects final; final accept blocked until provisional accepted
  - Stats cards: total applied, provisionally accepted, finally accepted, rejected
- **Co-op Students page**:
  - Filter by: All, Missing Reports, Missing Evals, Fully Complete
  - Drill into a student to view all work terms with report/evaluation status
  - Notify button beside each pending Report or Evaluation — sends a pop-up reminder to the student or supervisor on their next login
  - Reject a work term with a reason; Remove a student and all associated data
- **Notifications page**:
  - Lists students with overdue reports (past 30-day deadline)
  - Lists work terms with missing supervisor evaluations


## Database Tables
`applicants` -  Co-op applications with provisional/final status\
`users` -  Accounts for students, supervisors, and admins\
`work_terms` -  Work placements with reports and evaluations\
`supervisor_assignments` -  Links supervisor emails to students\
`notifications` -  Admin-sent reminders for pending reports/evaluations

## API Endpoints

### Public
POST:   `/api/apply`                                           -  Submit co-op application\
POST:   `/api/application-status`                              -  Check application status\
POST:   `/api/login`                                           -  Authenticate user\
POST:   `/api/signup/student`                                  -  Create student account\
POST:   `/api/signup/supervisor`                               -  Create supervisor account\
GET:    `/api/report-template`                                 -  Download report template

### Student
GET:    `/api/student/workterms`                               -  List student's work terms\
POST:   `/api/student/workterms`                               -  Add work term\
POST:   `/api/student/workterms/{id}/report`                   -  Submit work term report\
POST:   `/api/student/workterms/{id}/update-supervisor`        -  Update supervisor email

### Supervisor
GET:    `/api/supervisor/students`                             -  List assigned students\
POST:   `/api/supervisor/workterms/{id}/evaluate`              -  Submit evaluation (PDF or online form)

### Admin
GET:    `/api/admin/applicants`                                -  List all applicants (filter by year)\
PATCH:  `/api/admin/applicants/{id}/provisional`               -  Set provisional accept/reject\
PATCH:  `/api/admin/applicants/{id}/final`                     -  Set final accept/reject\
GET:    `/api/admin/resume/{app_id}`                           -  View applicant resume\
GET:    `/api/admin/students`                                  -  List all students and work terms\
GET:    `/api/admin/notifications`                             -  Get overdue reports and missing evaluations\
PATCH:  `/api/admin/workterms/{id}/reject`                     -  Reject a work term\
POST:   `/api/admin/notify`                                    -  Send notification to student or supervisor\
DELETE: `/api/admin/students/{student_id}`                     -  Remove student and all associated data\
GET:    `/api/admin/report/{wt_id}`                            -  View a student's submitted report\
GET:    `/api/admin/evaluation/{wt_id}`                        -  View a submitted evaluation

### Notifications
GET:    `/api/notifications/my`                                -  Fetch current user's unread notifications\
POST:   `/api/notifications/dismiss`                           -  Dismiss a notification

## Notes

- University email validation accepts: `@torontomu.ca`
- Tokens expire after 8 hours (JWT-based)
- All file uploads stored in `uploads/` -  directory
- Admin account is build in
