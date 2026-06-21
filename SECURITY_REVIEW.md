# Bookie Security Review

This document maps Bookie's main web security risks to the controls currently implemented in the repository. It is intentionally precise: items marked as implemented are backed by code, tests, or documented production configuration. Remaining gaps are listed explicitly.

## 1. Authentication And Session Management

### Implemented

- Login lockout is implemented in `books/views/auth.py`: after 5 failed attempts within a 15-minute window, both the source IP and targeted username are locked out.
- Lockout events and failed login attempts are logged for operational visibility.
- Django sessions are configured with `SESSION_COOKIE_HTTPONLY = True`.
- Production settings support HTTPS-only cookies and SSL redirect through `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and `SECURE_SSL_REDIRECT`.
- `CSRF_COOKIE_HTTPONLY = False` in base settings so AJAX/browser code can read and submit the CSRF token where needed. CSRF protection still applies to Django form and session-backed POST flows.

### Remaining Gap

- Admin MFA is not implemented.
- Production deployment must provide real `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, HTTPS, and secure cookie settings.

## 2. Authorization And RBAC

### Implemented

- User-facing order views scope access by `request.user`.
- `api_order_detail` allows only the owner or staff users and returns `403` for unauthorized authenticated users.
- Dashboard access is protected by role/permission helpers for Customer, Support, Staff, Manager, and Admin flows.
- Sensitive dashboard actions are recorded through admin audit logging.

### Tested

- IDOR-style order access and dashboard role restrictions are covered by backend tests.

### Remaining Gap

- More browser-level RBAC tests are planned for the Playwright suite.

## 3. Input And Output Protection

### Implemented

- Django ORM is used for catalog/API/database queries, avoiding raw SQL string interpolation.
- Django template auto-escaping protects normal user-submitted text.
- Ebook HTML content is sanitized before rendering dangerous tags such as scripts/iframes/styles.
- Chatbot prompts are screened for common prompt-injection phrases and constrained to catalog-grounded recommendations.

### Remaining Gap

- The prompt-injection filter is intentionally lightweight and should be expanded with a stronger evaluation set before real production use.
- CSP should remain aligned with frontend assets; external CDN usage requires SRI or local assets.

## 4. Checkout, Inventory, And Payment Integrity

### Implemented

- Checkout uses idempotency keys to prevent duplicate order creation on double-submit.
- Inventory rows are locked with Django `select_for_update()` inside an atomic transaction before stock is decremented.
- Payment state transitions are centralized through `mark_order_paid()` so paid orders are processed once.
- `transaction_id` has a conditional database uniqueness constraint when present, preventing payment replay at DB level.
- Mock payment confirmation is restricted to Momo simulation only.
- COD orders cannot be manually marked paid through the mock endpoint.
- VNPay orders must go through the VNPay return handler.
- VNPay return handling validates checksum, required fields, payment method, transaction amount, order status, and duplicate transaction IDs before marking an order paid.
- Confirmation email dispatch is queued only on the first successful paid transition.
- Payment logos and simulated QR visuals are served from local static assets instead of third-party image/QR services.

### Tested

- Backend tests cover duplicate checkout idempotency, COD/VNPay mock confirmation rejection, Momo mock success, missing VNPay fields, amount mismatch, duplicate transaction IDs, and duplicate callback side-effect suppression.

### Remaining Gap

- Current VNPay integration is a browser return handler, not a server-to-server IPN/webhook endpoint.
- Real production payment should add provider sandbox credentials, server-to-server IPN if available, reconciliation logs, refund/cancel lifecycle, and monitoring alerts.

## 5. API Method And Input Safety

### Implemented

- Read-only JSON APIs are restricted to `GET`.
- Cart API allows only `GET` and `POST`.
- Cart API validates JSON, action, book ID, positive quantity, stock availability, and current cart quantity against stock.
- API errors use the shape `{"status": "error", "message": "..."}`.

### Tested

- Backend tests cover unsupported methods, invalid JSON/action/book/quantity, over-stock add/update, and out-of-stock add.

## 6. Operational Security And CI

### Implemented

- `/health/` checks database/cache dependencies.
- `/health/live/` confirms the Django process is answering without touching DB/cache.
- `/health/ready/` checks dependencies before traffic is routed.
- Structured console logging is configured for local/Docker visibility.
- GitHub Actions currently run backend tests and security scans with `pip-audit` and `bandit`.
- Version-pinned CDN assets for Bootstrap, Bootstrap Icons, Chart.js, Three.js, GSAP, and ScrollTrigger include `integrity` and `crossorigin="anonymous"` attributes.

### Remaining Gap

- Public deployment still needs platform-level HTTPS, secrets management, log retention, alerting, dependency update policy, and backup/restore procedures.
- The two current GitHub Actions workflows should be consolidated into one canonical CI workflow.

## 7. Security Posture Matrix

| Area | Existing Control | Evidence | Status |
| :--- | :--- | :--- | :--- |
| Brute force | IP + username lockout | Auth view + tests/logs | Implemented |
| Session cookies | HttpOnly sessions, production secure-cookie settings | Django settings | Implemented |
| CSRF | Django CSRF middleware/forms/AJAX token usage | Views/templates/settings | Implemented |
| SQL injection | Django ORM query construction | Views/services/API | Implemented |
| XSS | Auto-escape + ebook sanitizer | Templates/sanitizer | Implemented |
| IDOR | Owner/staff checks for orders | Views/API/tests | Tested |
| RBAC | Role helpers and dashboard restrictions | RBAC/dashboard/tests | Implemented |
| Checkout race condition | Atomic transaction + `select_for_update()` | Order service/tests | Tested |
| Double submit | Checkout idempotency key | Model/service/tests | Tested |
| Payment replay | Unique `transaction_id` + paid transition service | Model/service/tests | Tested |
| VNPay tampering | Checksum, amount, method, required fields | Return handler/tests | Tested |
| Mock payment abuse | Mock endpoint restricted to Momo | View/tests | Tested |
| AI prompt injection | Keyword guard + catalog grounding | Chatbot/tests | Implemented |
| Dependency security | `pip-audit`, `bandit` | GitHub Actions | Implemented |
| CDN/SRI | SRI on version-pinned JS/CSS CDN assets | Templates | Implemented |
| Production monitoring | Health endpoints and logs exist | Views/settings | Partial |
