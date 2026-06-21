# Bookie Deployment Guide

This document describes how to deploy and configure **Bookie** in development, testing, and production environments.

---

## 1. Prerequisites

Ensure you have the following installed on your machine or target server:
* **Docker & Docker Compose** (for multi-container deployment)
* **Python 3.12** (for local native execution)
* **Git**

---

## 2. Local Multi-Container Deployment (Docker Compose)

To spin up all services including Django, PostgreSQL, Redis, and the Huey background worker:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/vcongggggg/bookie-bookstore.git
   cd bookie-bookstore/Project
   ```

2. **Configure Environment Variables:**
   Create a `.env` file by copying the template:
   ```bash
   cp .env.example .env
   ```
   *Edit `.env` and fill in custom database credentials, secrets, or mail server variables.*

3. **Start the Docker Containers:**
   ```bash
   docker compose up --build -d
   ```
   *This commands runs the following containers in the background:*
   * `web`: The Gunicorn web server mapping to port `8000`.
   * `worker`: The Huey background task executor.
   * `db`: The PostgreSQL relational database server.
   * `redis`: The cache store and background task message broker.

4. **Initialize Database & Seed Realistic Demo Data:**
   ```bash
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py seed_fake_data --reset-demo
   ```
   *After completion, you can login with the seeded accounts at `http://127.0.0.1:8000/`:*
   * **Customer:** `democustomer` / `customer123`
   * **Staff:** `demostaff` / `staff123`
   * **Manager:** `demomanager` / `manager123`
   * **Support:** `demosupport` / `support123`
   * **Admin:** `demoadmin` / `admin123`

---

## 3. Health Probes

Bookie exposes three operational health endpoints:

| Endpoint | Purpose | Dependency Checks |
| :--- | :--- | :--- |
| `/health/` | Full application health summary for manual checks. | Database and cache. |
| `/health/live/` | Liveness probe: confirms the Django process can answer HTTP. | None. |
| `/health/ready/` | Readiness probe: confirms the app can safely receive traffic. | Database and cache. |

Suggested usage:

```bash
curl http://127.0.0.1:8000/health/live/
curl http://127.0.0.1:8000/health/ready/
```

Use `/health/live/` for container liveness checks and `/health/ready/` for load balancer or platform readiness checks.

---

## 4. Production Environment Variables Checklist

Ensure the following variables are correctly configured in production hosting environments (e.g., Render, Railway, Fly.io, or VPS) to enforce security locks:

| Variable Name | Recommended Value | Purpose |
| :--- | :--- | :--- |
| `DJANGO_ENV` | `production` | Switches Django configurations to strict production behaviors. |
| `DEBUG` | `False` | Disables debug screens to prevent metadata leakage on 500 errors. |
| `SECRET_KEY` | *[random 50+ character string]* | Secures cryptographic signatures and session keys. |
| `ALLOWED_HOSTS` | `yourdomain.com,your-app.render.com` | Restricts HTTP Host header validation. |
| `CSRF_TRUSTED_ORIGINS` | `https://yourdomain.com` | Authorized origins for incoming POST requests. |
| `DATABASE_URL` | `postgresql://user:pass@host:port/dbname` | Database connection URL. |
| `REDIS_URL` | `redis://default:password@redis-host:6379/0` | Connection URL for Caching and Background tasks. |
| `SECURE_SSL_REDIRECT` | `True` | Automatically redirects all HTTP requests to HTTPS. |
| `SESSION_COOKIE_SECURE` | `True` | Restricts cookies to HTTPS transfers only. |
| `CSRF_COOKIE_SECURE` | `True` | Restricts CSRF tokens to HTTPS transfers only. |

---

## 5. Production Deployment Methods

### A. Render (PaaS)
1. **Database:** Provision a PostgreSQL Instance on Render. Copy the Database connection URL.
2. **Cache:** Provision a Redis Instance on Render. Copy the Redis URL.
3. **Web Service:** Create a new Web Service pointing to your repository.
   * **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --no-input`
   * **Start Command:** `gunicorn bookstore.wsgi:application --bind 0.0.0.0:$PORT`
   * **Environment Variables:** Define all variables from Section 4.
4. **Worker Service:** Create a new Private Service on Render.
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python manage.py run_huey`

### B. Railway (PaaS)
1. Create a new project.
2. Add PostgreSQL and Redis services from the Railway dashboard.
3. Add a Web Service pointing to your repo. Railway will automatically detect the Dockerfile or python requirements.
4. Define variables; Railway automatically injects matching `DATABASE_URL` and `REDIS_URL`.

### C. VPS (Ubuntu + Nginx + Gunicorn)
1. Set up Docker Compose on your VPS or run Django natively using Gunicorn and a systemd process.
2. Configure **Nginx** to bind to port 80/443 and proxy request payloads to Gunicorn running locally on port 8000:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
3. Use **Certbot** to install free Let's Encrypt SSL certificates automatically.
