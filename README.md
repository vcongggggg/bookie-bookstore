# Bookie - Django E-commerce Bookstore

[![Django Tests](https://github.com/vcongggggg/Python/actions/workflows/django-tests.yml/badge.svg)](https://github.com/vcongggggg/Python/actions/workflows/django-tests.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.x-092E20?logo=django&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-47%20passing-brightgreen)

Bookie is a Django bookstore project with a full e-commerce workflow, admin dashboard, AI-assisted book discovery features, and test/CI support. The active application lives in [`Project/`](Project/).

## Highlights

- Full bookstore flow: catalog, category filter/search, book detail, cart, checkout, coupons, orders, wishlist, ratings, user profile, reading history, and ebook reader.
- Admin workflows: user management, book/coupon/order management, revenue statistics, audit logs, CSV export, and role-based permissions.
- AI-assisted features: content-based recommendations, sentiment analysis, Reading DNA, and a database-grounded chatbot.
- Quality baseline: Django checks, automated tests, GitHub Actions workflow, CSRF-protected chatbot API, AJAX cart/wishlist tests, sitemap/robots.txt, and JSON-LD Book SEO.
- Local and Docker-ready workflows with seed commands and environment templates.

## Demo Status

- Live demo: not deployed yet
- Demo video: planned
- Screenshots: planned
- Local demo accounts after running `seed_fake_data --reset-demo`:
  - Customer: `demo / demo123`
  - Admin: `admin / admin123`

## My Contribution

- Built the full bookstore functionality across user-facing pages, admin workflows, cart/order flows, and AI-assisted features.
- Implemented dashboard and management screens for books, users, coupons, orders, revenue, and audit logs.
- Added tests and quality gates for the main web flows.
- Improved project setup so the application can be run locally or through Docker.

## Tech Stack

- Backend: Python, Django
- Database: SQLite for local development, PostgreSQL Docker support, MySQL-style production configuration
- Frontend: HTML, CSS, JavaScript, Bootstrap, Chart.js, GSAP, AJAX
- AI: Ollama/Qwen, recommendation logic, sentiment analysis, database-grounded chatbot behavior
- Dev tooling: Docker, Docker Compose, GitHub Actions

## Architecture

```text
Browser
  |
  v
Django Views + Templates
  |
  +-- Book catalog / cart / checkout / orders
  +-- Admin dashboard / RBAC / audit logs
  +-- Ebook reader / reading progress
  +-- AI assistant / recommendations / sentiment
  |
  v
SQLite (local) / PostgreSQL (Docker) / MySQL-style production config
  |
  +-- Optional Ollama/Qwen local LLM for chatbot responses
```

## Repository Structure

```text
.
|-- Project/
|   |-- books/            # Main Django app
|   |-- bookstore/        # Django settings and URL configuration
|   |-- templates/        # HTML templates
|   |-- static/           # CSS, JavaScript, images
|   |-- Dockerfile
|   |-- docker-compose.yml
|   |-- manage.py
|   `-- requirements.txt
|-- CODEBASE_CONTEXT.md
|-- PROJECT_STATUS_AND_TEST_PLAN.md
`-- README.md
```

## Core Features

### User Features

- Register, login, logout, and profile management.
- Browse catalog, filter/search by category, and view book details.
- Add books to cart/wishlist and complete checkout.
- Apply coupons and view order history/details.
- Rate/comment books.
- Read ebooks online and track reading progress.

### Admin Features

- Admin dashboard for revenue, orders, users, and books.
- Manage users, books, coupons, and orders.
- Export books/orders to CSV.
- Audit administrative actions.
- Role-based access for management screens.

### AI Features

- Content-based recommendation logic.
- Sentiment analysis for reviews/comments.
- Reading DNA visualization.
- Chatbot that searches the book database first before using a local LLM response.

## Run Locally

```powershell
cd Project
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_fake_data --reset-demo
python manage.py runserver
```

Open:

- App: http://127.0.0.1:8000
- Admin: http://127.0.0.1:8000/admin/

Demo accounts:

```text
Customer: demo / demo123
Admin:    admin / admin123
```

## Run Tests

From the repository root:

```powershell
python Project\manage.py check
python Project\manage.py test books
```

From `Project/`:

```powershell
python manage.py check
python manage.py test books
```

Current baseline: `47 tests passing`.

## Run with Docker

```powershell
cd Project
docker compose up --build
docker compose exec web python manage.py seed_fake_data --reset-demo
```

## Deployment Plan

This project is ready to be deployed as a portfolio demo. A typical setup would use:

- Render, Railway, Fly.io, or PythonAnywhere for the Django app
- PostgreSQL for the production-like database
- Environment variables from `Project/.env.example`
- Django's standard `collectstatic` flow for static files

Suggested post-deploy smoke test:

- Open the home/catalog page.
- Login with a demo account.
- Add a book to cart and wishlist.
- Complete checkout with seeded data.
- Open the admin dashboard.
- Run chatbot/database book search.

## Notes

- Do not commit `.env`, local databases, generated media, virtual environments, or cache files.
- Use `.env.example` as the safe configuration template.
- This is an academic/personal portfolio project, not a production bookstore.
