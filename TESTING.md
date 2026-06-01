# Bookie Testing Workflow

This project uses a practical web-project testing workflow: every change should pass automated checks, and risky user flows should also be tested manually in the browser.

## Quality Gates

Before merging into `main`, run:

```powershell
python Project\manage.py check
python Project\manage.py test books
coverage run Project\manage.py test books
coverage report
```

GitHub Actions also runs:

- dependency install from `Project/requirements.txt`
- `python Project/manage.py check`
- `coverage run Project/manage.py test books`
- `coverage report --fail-under=35`

## Branch Workflow

1. Start from updated `main`.
2. Create a focused branch:
   - `feature/<name>` for new features
   - `fix/<name>` for bugs
   - `hardening/<name>` for quality/UX cleanup
   - `testing/<name>` for test infrastructure
   - `docs/<name>` for documentation
3. Add or update tests for the touched behavior.
4. Run local checks.
5. Commit with a clear message.
6. Push branch.
7. Merge into `main` only after tests pass.
8. Re-run checks on `main`, then push `main`.

## Test Pyramid For This Project

- Model/unit tests: model properties such as order totals, coupon validity, stock behavior.
- View/integration tests: URLs, permissions, checkout, reader, dashboard, chatbot API.
- Manual browser tests: layout, AJAX interactions, mobile behavior, payment redirects, visual quality.
- External-service smoke tests: Ollama and VNPay only when local/sandbox services are configured.

## Current Automated Coverage

The Django test suite currently covers:

- home and book detail smoke tests
- reader access and reading-progress save
- paid digital preview/full access behavior
- digital checkout stock behavior
- physical checkout stock behavior
- coupon discount checkout behavior
- invalid coupon checkout fallback behavior
- dashboard URL reverse checks
- Reading DNA chart context
- invoice PDF access and response type
- chatbot rate limiting

## Manual Regression Checklist

Use `PROJECT_STATUS_AND_TEST_PLAN.md` for a full browser checklist.

Minimum manual smoke pass before demo:

1. Browse catalog and book detail.
2. Add/remove/update cart items.
3. Checkout with COD.
4. Apply valid and invalid coupons.
5. View order detail and download invoice PDF.
6. Add/remove wishlist item.
7. Open Reading DNA as demo user.
8. Open digital reader and save progress.
9. Open chatbot and verify fallback/rate-limit behavior.
10. Open dashboard as staff/admin and verify key pages.

## When To Add Tests

Add tests whenever a change touches:

- checkout or payment
- cart or stock handling
- permissions/authentication
- admin actions
- reader access/progress
- user-generated content
- chatbot/API behavior
- templates that depend on non-trivial context

