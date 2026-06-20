# Bookie - Django E-commerce Bookstore

[![Django Tests](https://github.com/vcongggggg/Python/actions/workflows/django-tests.yml/badge.svg)](https://github.com/vcongggggg/Python/actions/workflows/django-tests.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.x-092E20?logo=django&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-70%20passing-brightgreen)

Bookie is a Django bookstore project featuring full e-commerce workflows, an admin dashboard, an offline PWA ebook reader, background tasks, Redis caching, and robust security controls. 

The primary, production-ready implementation resides in the [`Project/`](Project/) directory. For a comprehensive overview of the design patterns, system architecture, security controls, and local quick start, please refer directly to the detailed [**Project/README.md**](Project/README.md).

## Project Features at a Glance

- **Complete E-Commerce Flow:** Catalog search/sorting, category filters, interactive cart, coupon discounts, order placement, wishlist, ratings, and user profiles.
- **PWA Ebook Reader:** Serves a custom Service Worker at the root scope, supporting offline ebook reading, bookmarking, and visual progress tracking.
- **Operations & Caching:** Redis caching for popular lists, model signals for automatic cache invalidation, and background task queues utilizing Huey (email confirmation, low-stock warnings).
- **Security & Hardening:** Brute-force protection (lockout by IP and username), database transaction row locking (`select_for_update`) to prevent double stock reduction, API rate limits, secure cookies, HTML sanitization against XSS, and signature validation on VNPay callbacks.
- **Observability:** Custom health check endpoint (`/health/`) monitoring PostgreSQL and Redis backend liveness, and structured application logs.
- **Quality Gate CI/CD:** Pipeline runs tests, enforces a 65% coverage gate (currently at 67%), scans python dependencies (`pip-audit`), and audits codebase security (`bandit`).

## Run Tests Locally

From `Project/`:
```bash
python manage.py check
python manage.py test books
```

Current baseline: `70 tests passing`.

---
*For installation instructions, docker usage, and demo credentials, see [Project/README.md](Project/README.md).*
