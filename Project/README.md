# Bookie - Production-Oriented Django Bookstore

[![Bookie CI](https://github.com/vcongggggg/bookie-bookstore/actions/workflows/ci.yml/badge.svg)](https://github.com/vcongggggg/bookie-bookstore/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-6.x-092E20.svg)](https://www.djangoproject.com/)
[![Tests](https://img.shields.io/badge/tests-75%2B%20passing-brightgreen.svg)](../TESTING.md)

Bookie is a full-stack Django bookstore platform built as a portfolio-grade project: catalog, cart, checkout, order management, RBAC dashboard, offline ebook reader, background jobs, JSON APIs, health checks, and security-focused payment handling.

## 1. Feature Highlights

### Core E-commerce

- Catalog search, category filtering, sorting, wishlist, ratings, and user profiles.
- Session cart with AJAX-style updates and stock validation.
- Checkout with coupons, idempotency keys, and atomic stock locking.
- Order history, order detail, invoice PDF generation, and payment status tracking.

### Admin And RBAC

- Dashboard roles: Customer, Support, Staff, Manager, and Admin.
- Admin tools for users, books, coupons, orders, audit logs, and CSV exports.
- Audit trail for sensitive dashboard operations.

### Reader And AI

- PWA ebook reader with service worker support, bookmarks, and progress tracking.
- Database-grounded chatbot/recommendation flow with prompt-injection guardrails.

## 2. Tech Stack

| Layer | Technologies |
| :--- | :--- |
| Backend | Python 3.12, Django, Django ORM |
| Frontend | HTML, CSS, JavaScript, Bootstrap, AJAX-style interactions |
| Data | PostgreSQL, SQLite for local/tests, Redis cache |
| Background Jobs | Huey worker |
| Infra | Docker Compose, Gunicorn, WhiteNoise |
| Quality | Django TestCase, Playwright, Coverage, GitHub Actions |
| Security Tooling | pip-audit, bandit |
| AI | Ollama/Qwen-compatible local model flow, DB-first recommendation logic |

## 3. Production-Oriented Details

### Checkout Integrity

Checkout uses `transaction.atomic()` and `select_for_update()` to lock inventory rows before stock deduction. Idempotency keys prevent duplicate order creation when users double-submit the form.

### Payment Safety

Payment state changes are centralized through `mark_order_paid()`. VNPay uses a return handler with checksum, amount, method, required-field, and duplicate-transaction checks. Momo payment is clearly treated as a local simulation. COD cannot be manually marked paid through the mock endpoint.

### Observability

| Endpoint | Purpose |
| :--- | :--- |
| `/health/` | Full health summary with database/cache checks. |
| `/health/live/` | Liveness probe, no DB/cache dependency. |
| `/health/ready/` | Readiness probe with DB/cache checks. |

### Security Controls

- Login lockout by IP and username.
- CSRF protection for session-backed POST flows.
- Owner/staff checks for order APIs to prevent IDOR.
- HTML sanitization for ebook rendering.
- Secure production cookie/HTTPS settings in configuration.
- CI security scans using `pip-audit` and `bandit`.

## 4. Local Quick Start

```powershell
copy .env.example .env
python manage.py migrate
python manage.py seed_fake_data --reset-demo
python manage.py runserver
```

Docker:

```powershell
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_fake_data --reset-demo
```

Open `http://127.0.0.1:8000/`.

## 5. Testing

```powershell
python manage.py check
python manage.py test books
npm.cmd run test:e2e:smoke
npm.cmd run screenshots
```

Current verified baseline: `75+ backend tests passing` plus Playwright smoke flows for public pages, cart/checkout, COD checkout, simulated Momo payment, RBAC dashboard access, health probes, reader, and chatbot.

## 6. Demo Credentials

The `seed_fake_data --reset-demo` command creates representative users for all roles:

| Username | Password | Primary Role | Permissions |
| :--- | :--- | :--- | :--- |
| `demo` | `demo123` | Customer | Order books, read online, edit profile |
| `admin` | `admin123` | Admin | Access dashboard, view audit logs, manage roles |
| `manager` | `manager123` | Manager | Manage books, categories, and inventory |
| `staff` | `staff123` | Staff | Access dashboard overview and exports |
| `support` | `support123` | Support | View and update customer order statuses |

## 7. Documentation

- [Architecture](../ARCHITECTURE.md)
- [API Reference](../API.md)
- [Security Review](../SECURITY_REVIEW.md)
- [Deployment Guide](../DEPLOYMENT.md)
- [AI Security](../AI_SECURITY.md)
- [Testing Workflow](../TESTING.md)
- [Demo Script](../DEMO_SCRIPT.md)
- [Screenshot Checklist](../docs/screenshots/README.md)
