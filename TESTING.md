# Bookie Testing Workflow

Bookie uses layered tests so risky flows are checked at the backend, browser, and CI levels.

## Local Quality Gates

From the repository root:

```powershell
python Project\manage.py check
python Project\manage.py test books
cd Project
npm.cmd run test:e2e:smoke
npm.cmd run screenshots
docker compose config --quiet
```

Coverage gate:

```powershell
cd Project
coverage run --source=books --omit="*/migrations/*,*/tests.py,*/test_*.py" manage.py test books
coverage report --fail-under=65
```

## GitHub Actions

The canonical workflow is `.github/workflows/ci.yml`.

It runs:

- Backend: `python manage.py check`, Django tests, coverage `fail-under=65`.
- Security: `pip-audit`, `bandit`, and `.env.example` secret-pattern check.
- E2E: Playwright smoke suite for desktop and mobile Chromium.
- Docker: `docker compose config --quiet` and `docker compose build web worker`.

Playwright artifacts are uploaded on failure from `Project/playwright-report` and `Project/test-results`.

## Current Automated Coverage

Backend tests cover:

- Home, catalog, and book detail smoke behavior.
- Reader access and reading-progress save.
- Digital and physical checkout behavior.
- Coupon validation and fallback behavior.
- Checkout idempotency and stock locking.
- Payment confirmation method restrictions.
- VNPay return validation and replay safety.
- API method/input validation.
- Order/profile API access control.
- Login lockout, rate limiting, IDOR checks, and RBAC.
- Health probes.
- Chatbot prompt-injection guardrails.

Playwright smoke tests cover:

- Public pages without horizontal overflow.
- Demo login.
- Add to cart, cart view, checkout view.
- COD checkout to order detail.
- Simulated Momo payment to paid order state.
- Customer dashboard rejection.
- Admin dashboard access.
- Support order dashboard access.
- Liveness/readiness health JSON.
- Reader layout.
- Chatbot mocked response.

Screenshot automation captures portfolio images into `docs/screenshots/`.

## Branch Workflow

1. Start from updated `main`.
2. Create a focused branch: `feature/<name>`, `fix/<name>`, `hardening/<name>`, `testing/<name>`, or `docs/<name>`.
3. Add or update tests for touched behavior.
4. Run the relevant local quality gates.
5. Commit with a clear message.
6. Push branch and wait for CI.
7. Merge only after tests/security checks pass.

## Manual Demo Checklist

Use this before recording a demo video or sharing a public deploy:

1. Browse home, catalog, and book detail.
2. Add/remove/update cart items.
3. Checkout with COD.
4. Checkout with simulated Momo payment.
5. View order detail and invoice PDF.
6. Add/remove wishlist item.
7. Open Reading DNA as demo user.
8. Open digital reader and save progress.
9. Open chatbot and verify a catalog-grounded response.
10. Open dashboard as Admin and Support.

## When To Add Tests

Add tests whenever a change touches checkout/payment, cart/stock handling, permissions, admin actions, reader access/progress, user-generated content, chatbot/API behavior, or templates with non-trivial context.
