# Bookie — Midnight Cosmic Bookstore ✦

[![Django CI](https://github.com/vcongggggg/bookie-bookstore/actions/workflows/django-tests.yml/badge.svg)](https://github.com/vcongggggg/bookie-bookstore/actions)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Bookie** is a production-oriented, full-stack bookstore platform designed with robust software engineering patterns. Moving beyond simple CRUD capabilities, it includes features focused on concurrency safety, offline reading, logging audit trails, structured security controls, background worker execution, and automated testing suites.

---

## 1. Project Overview & Features

### Core E-Commerce Workflows
- **Cosmic Catalog & Filtering:** Search, sort, and filter books using AJAX-driven queries and Bento grid category layouts.
- **AJAX Shopping Cart & Concurrency-Safe Checkout:** Interactive cart management, dynamic coupon code validations, and an order creation flow guarded by database-level row locks.
- **Ebook Reader (PWA):** Fluid e-reader supporting offline reading (via service workers), bookmark saving, progress synchronizations, and responsive layouts.
- **Admin Dashboard (RBAC):** High-level management panel with distinct views, actions, and credentials mapped across 5 Roles: Customer, Staff, Manager, Support, and Admin.

### Advanced AI Integrations
- **AI Recommendation Engine:** Content-based filtering matching user interests with book attributes, and sentiment analysis on reviews.
- **DB-Grounded Book Assistant:** Draggable chatbot utilizing Ollama (Qwen) with catalog search prioritizing database lookups before generating fallback answers, guarded against prompt injection.

---

## 2. Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | Django 6.1 (Python 3.12), Django ORM |
| **Frontend UI** | HTML5, CSS3 Variables, ES6+ Javascript, AJAX, GSAP (Animations) |
| **Databases & Cache** | PostgreSQL (Production), SQLite (Dev), Redis (Cache & Tasks Broker) |
| **Background Tasks** | Huey (Sqlite/Redis Backend) |
| **Containerization** | Docker, Multi-Stage builds (Non-root user) |
| **Quality & SecOps** | Django TestCase, Playwright (E2E), pip-audit, bandit, Coverage (fail-under 65%) |

---

## 3. Architecture & Production Features

### Concurrency & Transaction Integrity
During checkout, the system uses Django's `select_for_update()` to lock Book inventory rows within an atomic transaction. This prevents stock double-allocations and race conditions during high concurrent order volumes.

### Task Queue & Asynchronous Workloads
Rather than blocking HTTP requests, the application delegates CPU-bound or external network operations to a background **Huey** task queue:
- Generating and mailing order confirmation PDFs.
- Triggering admin alerts for inventory dip warnings (low stock alerts).
- Mailing user welcomes on registrations.

### Redis Cache & Invalidation Signals
High-traffic pages (homepage lists, category directories) query Redis cache before making database roundtrips. Custom model signals (`post_save`, `post_delete`) automatically evict corresponding cache keys upon Book, Category, Rating, or Order modifications.

### PWA Offline Support
Uses a custom Service Worker served from the root scope (`/service-worker.js`) to provide true **offline ebook reading**. App Shell assets and loaded ebook pages are cached using a *Network-First* fallback strategy.

### Observability & Health Checks
Includes JSON health endpoints for local verification and container orchestration:

| Endpoint | Purpose |
| :--- | :--- |
| `/health/` | Full application health summary with database/cache checks. |
| `/health/live/` | Liveness probe that only confirms the Django process is answering. |
| `/health/ready/` | Readiness probe that verifies database/cache dependencies before receiving traffic. |

---

## 4. Security & Hardening Controls

- **Authentication Lockout:** Brute-force protection locking out IPs and user accounts after 5 failed login attempts within a 15-minute sliding window.
- **Security Headers:** Strict implementation of security policies, including `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and secure cookie bindings (`SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SECURE`).
- **Input Sanitization:** Custom HTMLParser sanitizes ebook HTML inputs, discarding script/style blocks to protect against XSS injections.
- **Secure payment lifecycles:** VNPay webhook/IPN signature verifications and payment amount checking to mitigate price tampering.
- **Idempotency Key Protection:** Checkout forms contain hidden UUID idempotency keys to ensure resubmitted requests do not create duplicate orders or deduct inventory twice.
- **CI/CD Quality Gates:** GitHub Actions automatically audit dependencies for known CVEs (`pip-audit`) and scan source code for security anti-patterns (`bandit`) on every push.

---

## 5. Local Quick Start

To spin up the entire multi-container environment (Django + PostgreSQL + Redis + Huey worker):

```bash
# 1. Clone the repository
git clone https://github.com/vcongggggg/bookie-bookstore.git
cd bookie-bookstore/Project

# 2. Configure Environment Variables
cp .env.example .env
# Open .env and customize database / cache keys as needed

# 3. Spin up services via Docker Compose
docker compose up --build -d

# 4. Migrate database schemas and seed realistic demo data
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_fake_data --reset-demo
```

Access the system at `http://127.0.0.1:8000/`.

---

## 6. Testing & Quality Gates

The test suite validates both API functionality, role accessibility (RBAC), and security controls.

To run tests locally:
```bash
# Run unit test suite
python manage.py test books

# Run test suite with coverage report
coverage run --source=Project/books --omit="*/migrations/*,*/tests.py" Project/manage.py test books
coverage report --fail-under=65
```

---

## 7. Demo Credentials

The database seeding command creates representative users for all roles:

| Username | Password | Primary Role | Permissions |
| :--- | :--- | :--- | :--- |
| `demo` | `demo123` | Customer | Order books, read online, edit profile |
| `admin` | `admin123` | Admin | Access dashboard, view audit logs, adjust settings |
| `manager` | `manager123` | Manager | Manage books, categories, and inventory |
| `staff` | `staff123` | Staff | Access dashboard overview, export reports |
| `support` | `support123` | Support | View and update customer order statuses |
