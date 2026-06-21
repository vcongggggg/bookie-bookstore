# Bookie CV Bullets

Use these bullets depending on the role you apply for. Keep 2-4 bullets on a one-page CV.

## Full-stack Intern

- Built Bookie, a full-stack Django bookstore platform with catalog search, cart/checkout, order management, user profiles, wishlist, ratings, RBAC dashboard, and offline ebook reader.
- Delivered responsive portfolio UI with automated Playwright smoke tests and screenshot generation across home, catalog, checkout, dashboard, reader, and chatbot flows.

## Backend / Security Intern

- Hardened checkout and payment flows with atomic stock locking, idempotency keys, one-time payment state transitions, duplicate transaction protection, and tests for replay/invalid payment scenarios.
- Implemented session-authenticated JSON APIs for catalog, cart, orders, and profile with method restrictions, stock validation, ownership checks, and consistent error responses.
- Improved web security posture with CSRF protection, login lockout, RBAC authorization, IDOR tests, secure headers, SRI for pinned CDN assets, local payment assets, and CI security scanning.

## DevOps / CI

- Containerized Bookie with Docker Compose using Django/Gunicorn, PostgreSQL, Redis, WhiteNoise, and Huey worker services, including liveness/readiness health endpoints.
- Consolidated GitHub Actions into a canonical CI pipeline with backend tests/coverage, `pip-audit`, `bandit`, Playwright smoke tests, and Docker Compose build validation.

## AI / Chatbot

- Built a database-grounded book assistant that prioritizes catalog search before LLM fallback and includes guardrails against prompt injection and unsupported recommendations.

## Interview Short Pitch

Bookie started as a bookstore app, but I upgraded it into a production-oriented full-stack project. It includes catalog, cart, checkout, orders, wishlist, ebook reader, RBAC dashboard, JSON APIs, Dockerized PostgreSQL/Redis setup, Huey background jobs, health checks, checkout transaction locking, idempotency, payment replay protection, CI security scans, Playwright e2e tests, and portfolio screenshots.
