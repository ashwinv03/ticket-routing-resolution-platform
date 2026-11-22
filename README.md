# AI-Powered Ticket Routing & Resolution Platform (TicketFlow)

A production-ready web platform for managing the lifecycle, intelligent routing, and resolution of enterprise support tickets. Built with **Python, Flask, PySQLite, and Cloud LLM APIs**, specifically architected to run smoothly on resource-constrained development environments (such as a **4 GB RAM laptop**) without requiring heavy local machine learning models or background database servers.

---

## 🚀 Key Architectural Highlights for 4 GB RAM Environments

* **Zero-Server Overhead Database (PySQLite)**: Uses `sqlite3` via `Flask-SQLAlchemy`. No MySQL or MongoDB background daemons consuming idle system memory. The database resides in a lightweight local file (`tickets.db`), keeping memory consumption under **150 MB RAM**.
* **Zero Local ML Weight Footprint**: Rather than loading multi-gigabyte PyTorch/TensorFlow models locally, natural language capabilities are offloaded via lightweight REST API calls to **Google Gemini API** (with built-in offline heuristic fallback).
* **Two-Stage Routing Engine**:
  1. **Configurable Rule-Based Department Routing**: Scans incoming ticket subjects and descriptions against prioritized keyword patterns.
  2. **Workload-Aware Agent Allocation**: Determines the active ticket load of eligible staff in the assigned team and dynamically assigns the ticket to the agent with the lowest active load.
* **ITIL-Compliant SLA Engine**: Computes Priority dynamically from **Impact × Urgency** (P1 Critical to P4 Low), tracks target response and resolution deadlines, flags SLA breaches, and pauses the SLA clock when tickets are placed on hold (`Pending User`).
* **Requester Confidentiality**: SLA target dates and breach badges are strictly hidden from requesters, visible only to support staff and administrators.
* **Universal Search Engine**: A top navigation search bar that enables searching tickets by ticket number (`INC-YYYYMMDD-XXXX` or partial digits like `0001`) with direct jump-to-ticket navigation or filtered queue search.
* **Role-Based Access Control (RBAC)**:
  * **System Administrator**: Full system-wide oversight, department CRUD, global routing rules, SLA policies, and user role management.
  * **Team Admin / Supervisor**: Scoped access to their assigned department only (departmental analytics dashboard, adding/removing agents, and department keyword routing rules).
  * **Support Agent**: Access to assigned tickets, team queues, the AI Resolution Workstation, internal notes, and cross-team ticket reassignment.
  * **Requester**: Submits tickets, tracks updates, replies to agents, and submits 1–5 star CSAT ratings upon resolution.
* **AI Resolution Assistant**:
  * One-Click Ticket Summarization
  * Knowledge Base-Assisted Resolution Suggestions
  * AI Draft Reply Generator with one-click insertion into the conversation feed.
* **Full Audit Trail**: Every creation, routing match, reassignment, status transition, and comment is logged with timestamps in `ticket_history`.

---

## 📁 Project Structure

```
AI-Powered Ticket Routing & Resolution Platform/
│
├── app/
│   ├── __init__.py              # Application factory & Blueprint registration
│   ├── config.py                # Environment configuration & SQLite settings
│   ├── models.py                # PySQLite SQLAlchemy data models
│   │
│   ├── auth/                    # Authentication (Login, Register, Profile)
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── tickets/                 # Ticket CRUD, Workstation, Comments, Universal Search & CSAT
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── team_admin/              # Department-Scoped Management
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── admin/                   # Global Admin Operations & Management
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── kb/                      # Searchable Knowledge Base
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── api/                     # REST Endpoints (AI Actions, Dashboard Metrics)
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── services/                # Core Business Logic Engines
│   │   ├── routing_engine.py    # 2-stage rule matching & workload allocation
│   │   ├── sla_service.py       # Priority matrix, SLA clock, pause & breach
│   │   ├── ai_service.py        # Cloud Gemini LLM integration & offline mock
│   │   └── audit_service.py     # Immutable ticket activity logger
│   │
│   ├── static/
│   │   ├── css/custom.css       # Clean UI styles, badges & timeline
│   │   ├── js/main.js           # AJAX AI buttons, dynamic priority preview
│   │   └── uploads/             # Ticket file attachments directory
│   │
│   └── templates/               # Responsive Jinja2 templates (Bootstrap 5)
│       ├── base.html            # Master layout with universal search & dynamic navbar
│       ├── auth/                # login.html (1-click demo buttons), register.html, profile.html
│       ├── tickets/             # list.html, create.html, detail.html (Agent Workstation & Reassign Modal)
│       ├── team_admin/          # dashboard.html, agents.html, routing_rules.html
│       ├── kb/                  # list.html, view.html, create.html
│       ├── admin/               # dashboard.html, routing_rules.html, sla_policies.html, users.html, teams.html
│       └── errors/              # 403.html, 404.html, 500.html
│
├── tests/                       # Automated regression & integration test suite
│   └── test_basic.py
├── seed_data.py                 # Database seeder (7 Teams, 28 Staff, SLA, Rules, KB, Tickets)
├── run.py                       # Lightweight local application server
├── workflow.txt                 # Functionalities guide & step-by-step presentation script
├── requirements.txt             # Minimal dependencies
├── .env.example                 # Environment variables template
└── README.md
```

---

## ⚡ Quick Start Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional for Cloud AI)
Copy `.env.example` to `.env`:
```bash
# In .env (Add your free Google Gemini API key if you want live cloud AI):
GEMINI_API_KEY=your_actual_key_here
```
*(Note: If no API key is provided, the platform automatically activates structured offline fallback responses so you can still present and test every AI feature without an internet connection or API account).*

### 3. Initialize and Seed Database
Run the seeder script to initialize the PySQLite schema and populate demo teams, staff, rules, and tickets:
```bash
python seed_data.py
```

### 4. Start the Application Server
```bash
python run.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 🏢 Support Departments & Staff Roster

The system comes pre-seeded with **7 departments**, each staffed with **1 Team Lead (`team_admin`)** and **3 Working Members (`agent`)** (all staff accounts share default password `agent123`):

| Department | Team Lead (`team_admin`) | Working Members (`agent`) | Configured Routing Scope |
| :--- | :--- | :--- | :--- |
| **Network & Infrastructure** | `agent_net` (Alex Rivera) | `ben_net`, `chris_net`, `dana_net` | VPN, Wi-Fi, routers, firewalls, subnets, gateways |
| **Software & Applications** | `sam_dev` (Samantha Chen) | `agent_it` (David Kim), `emma_soft`, `frank_soft` | ERP crashes, SQL exceptions, application bugs, 500 errors |
| **Hardware & Peripherals** | `agent_hw` (Marcus Vance) | `grace_hw`, `henry_hw`, `ivy_hw` | Laptops, monitors, screens, printers, docks, battery |
| **Cloud & DevOps** | `liam_cloud` (Liam Gallagher) | `jack_cloud`, `karen_cloud`, `leo_cloud` | AWS, Azure, GCP, Docker, Kubernetes, CI/CD pipelines |
| **Cybersecurity & Identity (IAM)** | `sophia_sec` (Sophia Zhang) | `mike_sec`, `nina_sec`, `oscar_sec` | SSO, 2FA/MFA, credentials, phishing, access grants |
| **HR & Payroll Operations** | `rachel_hr` (Rachel Green) | `paul_hr`, `quinn_hr`, `ross_hr` | Payroll, salary, benefits, leave, tax forms |
| **Billing & Finance Operations** | `monica_fin` (Monica Geller) | `steve_fin`, `tina_fin`, `uma_fin` | Invoices, reimbursement claims, expense reports |

### Global Accounts
* **System Administrator**: `admin` / `admin123`
* **Requesters (End-Users)**: `john_user` / `user123`, `sarah_user` / `user123`

*(The login screen also features 1-click quick credentials buttons for instant demonstration during presentations).*
