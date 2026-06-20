# Bookie Full-stack CV Upgrade Plan

Muc tieu cua file nay: bien Bookie tu mot project bookstore co nhieu tinh nang thanh mot portfolio project du suc dua vao CV apply Full-stack/Backend Intern. Ke hoach nay uu tien nhung viec lam tang diem voi reviewer/HR truoc, sau do moi den cac nang cap sau.

## 0. Cach dung file nay

- Tick `[x]` khi hoan thanh va da test.
- Giu `[ ]` cho viec chua lam.
- Dung `[~]` neu dang lam do dang.
- Moi task quan trong nen co commit rieng, ten commit ro y nghia.
- Moi phase chi nen merge khi dat "Definition of Done" cua phase do.

Ky hieu:

- `P0`: bat buoc, tac dong lon den CV/demo.
- `P1`: nen lam, giup project noi bat hon.
- `P2`: optional, lam khi con thoi gian.
- `CV impact`: tac dong truc tiep den cach viet CV/noi chuyen phong van.
- `Risk`: do rui ro khi sua code.

## 1. Trang thai hien tai

Danh gia cong tam hien tai: `7.2/10` cho Full-stack Intern.

Muc tieu sau khi lam plan:

- Ban toi thieu de dua CV: `8.0/10`.
- Ban dep de demo/phong van: `8.5/10`.
- Ban rat manh neu co deploy + payment sandbox + monitoring + README xin: `8.7-9.0/10`.

Nhung diem manh da co:

- Django full-stack app voi catalog, cart, checkout, order, wishlist, rating, profile, dashboard.
- Admin dashboard co quan ly user/book/coupon/order/audit log.
- RBAC 5 role: Customer, Staff, Manager, Support, Admin.
- Security da co: CSRF, rate limit, login lockout, IDOR checks, transaction/lock checkout, HTML sanitization.
- Docker Compose: web, worker, PostgreSQL, Redis.
- Background tasks bang Huey.
- Test backend va Playwright e2e.
- CI/CD security/quality baseline.
- PWA/offline reader va Redis cache.
- AI chatbot/DB-first recommendation voi Ollama.

Nhung diem con yeu:

- Chua co live demo public.
- README chua phai dang "ban duoc project" tot nhat.
- Chua co screenshot/demo video.
- Payment flow con nang tinh mock, chua that su production-grade.
- Observability/logging/health check con mong.
- API layer chua du ro neu apply role backend/full-stack co REST API.
- UI/UX can kiem tra responsive va polish bang screenshot browser that.

## 2. Thu tu uu tien tong quat

Lam theo thu tu nay de toi uu diem CV:

1. `P0` Demo packaging: README, screenshots, demo accounts, architecture, CV bullets.
2. `P0` Deploy public: app mo duoc bang link, co database demo, co smoke test.
3. `P0` Payment/checkout hardening: idempotency, status lifecycle, callback safety.
4. `P1` Observability: health endpoint, structured logs, audit/security logs.
5. `P1` API layer: REST-like endpoints cho books/cart/orders/profile hoac dashboard.
6. `P1` Browser e2e: cart, checkout, RBAC dashboard, mobile responsive.
7. `P1` UI/UX polish: dashboard, catalog, checkout, reader, empty states.
8. `P2` AI/RAG polish: prompt-injection guard, source grounding, eval cases.
9. `P2` Performance: query optimization, caching metrics, load smoke.

## 3. Phase 1 - Demo packaging va README chuyen nghiep

Muc tieu: nguoi xem GitHub hieu ngay project giai quyet gi, co gi dang gia, chay/test/deploy nhu the nao.

### 3.1 README chinh

- [x] `P0` Cap nhat README thanh cau truc portfolio:
  - Project overview.
  - Live demo.
  - Demo accounts.
  - Screenshots.
  - Feature highlights.
  - Architecture.
  - Security highlights.
  - Testing/CI.
  - Docker/deployment.
  - My contribution.
  - Roadmap.
- [x] `P0` Sua test badge/test count cho dung voi baseline moi nhat.
- [x] `P0` Them "Why this project matters" de tranh cam giac chi la CRUD bookstore.
- [x] `P0` Them "Production-oriented features" gom Docker, Redis, PostgreSQL, Huey, CI, security.
- [x] `P1` Them architecture diagram bang Mermaid.
- [x] `P1` Them table tech stack ro rang:
  - Backend: Python, Django, Django ORM.
  - Frontend: HTML, CSS, JavaScript, Bootstrap, AJAX.
  - Data: PostgreSQL, SQLite, Redis.
  - Infra: Docker, Docker Compose, Gunicorn, WhiteNoise.
  - Quality: Django TestCase, Playwright, GitHub Actions, pip-audit, bandit.
  - AI: Ollama/Qwen, DB-first chatbot, recommendation logic.

Acceptance criteria:

- README co anh/screenshot hoac placeholder ro rang.
- Reviewer co the hieu project trong 60 giay.
- Reviewer co the chay local bang 5-7 lenh.
- Co link toi plan nay.

### 3.2 Screenshots

- [ ] `P0` Tao folder `docs/screenshots/`.
- [ ] `P0` Chup it nhat 8 anh:
  - Home/catalog.
  - Book detail.
  - Cart.
  - Checkout.
  - Order detail/history.
  - Admin dashboard overview.
  - Dashboard orders/books/users.
  - Ebook reader.
  - Chatbot.
- [ ] `P1` Chup mobile screenshot cho catalog/checkout/reader.
- [ ] `P1` Nen dat ten file ro: `01-home.png`, `02-book-detail.png`, ...

Acceptance criteria:

- Anh dung kich thuoc, khong lo thong tin nhay cam.
- Anh hien thi data demo dep, khong qua trong.
- README render duoc anh tren GitHub.

### 3.3 Demo video

- [ ] `P0` Quay demo 2-4 phut:
  - Browse book.
  - Add to cart.
  - Checkout.
  - View order.
  - Admin update order.
  - Reader/chatbot.
- [ ] `P1` Them link video vao README.
- [ ] `P1` Them script demo ngan de noi khi phong van.

Suggested demo script:

```text
Bookie is a production-oriented Django bookstore platform. I built the core user flow from catalog to checkout, added role-based admin operations, secured sensitive flows such as login and checkout, and containerized the app with PostgreSQL, Redis, background workers, and automated tests.
```

## 4. Phase 2 - Deploy public

Muc tieu: co link public de HR/reviewer bam vao xem duoc.

### 4.1 Chon huong deploy

Lua chon khuyen nghi:

- [ ] `P0` Render/Railway/Fly.io neu muon nhanh.
- [ ] `P1` VPS neu muon hoc sau ve Linux, Nginx, SSL.
- [ ] `P2` PythonAnywhere neu muon don gian nhung it sat Docker hon.

Khuyen nghi cua minh: dung Render/Railway truoc de co link nhanh, sau do neu muon hoc DevOps thi lam VPS rieng.

### 4.2 Production config

- [x] `P0` Kiem tra `.env.example` du cac bien:
  - `DJANGO_ENV`
  - `DEBUG`
  - `SECRET_KEY`
  - `ALLOWED_HOSTS`
  - `CSRF_TRUSTED_ORIGINS`
  - `DATABASE_URL`
  - `REDIS_URL`
  - `SECURE_SSL_REDIRECT`
  - `SESSION_COOKIE_SECURE`
  - `CSRF_COOKIE_SECURE`
  - `EMAIL_*`
  - `OLLAMA_*`
- [x] `P0` Dam bao production khong dung secret dev.
- [x] `P0` Dam bao `DEBUG=False` chay duoc.
- [x] `P0` Dam bao static files collect duoc.
- [x] `P1` Them `DEPLOYMENT.md` rieng neu README qua dai.

Acceptance criteria:

- `python manage.py check --deploy` duoc review va giai thich ro cac warning neu co.
- App deploy mo duoc home/catalog/detail/checkout/login/dashboard.
- Co demo accounts reset duoc.

### 4.3 Database va seed data

- [x] `P0` Tao data demo dep:
  - It nhat 30-50 books.
  - 6-8 categories.
  - 5-10 orders.
  - Wishlist/rating/reading progress.
  - Admin audit logs.
- [x] `P0` Tao command seed idempotent:
  - Chay lai khong tao duplicate lung tung.
  - Co option `--reset-demo`.
- [x] `P1` Them cover images on dinh, khong phu thuoc link chet.

Acceptance criteria:

- Demo account login duoc.
- Dashboard co du lieu de nhin thuyet phuc.
- Catalog khong trong.

### 4.4 Deploy smoke test

- [ ] `P0` Tao checklist smoke test sau deploy:
  - Home `200`.
  - Login demo.
  - Add to cart.
  - Checkout COD.
  - Order detail.
  - Dashboard admin.
  - Reader.
  - Static files load dung.
- [ ] `P1` Tao command/script `smoke_deploy.md` hoac `scripts/smoke_test`.

Acceptance criteria:

- Co bang ket qua smoke test trong README hoac docs.
- Link demo trong CV khong bi loi 500/404.

## 5. Phase 3 - Payment/checkout hardening

Muc tieu: checkout khong chi "tao order", ma co thinking san pham that: status, idempotency, callback, security.

### 5.1 Payment state model

- [x] `P0` Review model `Order` hien tai:
  - `status`
  - `payment_method`
  - `payment_status`
  - `paid_at`
  - `transaction_id`
  - `payment_reference`
  - `idempotency_key`
- [x] `P0` Neu thieu, them field qua migration.
- [x] `P0` Dinh nghia state ro:
  - `pending`
  - `paid`
  - `failed`
  - `cancelled`
  - `refunded` optional.
- [x] `P1` Tach payment logic vao service rieng: `books/payment_services.py`.

Acceptance criteria:

- Order COD va order online co lifecycle khac nhau ro rang.
- Khong the confirm payment cua user khac.
- Khong the confirm payment 2 lan lam sai stock/revenue.

### 5.2 Idempotency

- [x] `P0` Them idempotency cho checkout/payment confirm.
- [x] `P0` Neu user double-click checkout, chi tao 1 order hoac xu ly khong lam tru stock 2 lan.
- [x] `P0` Payment callback lap lai khong lam order bi update sai.
- [x] `P1` Test concurrency/race cho idempotency.

Acceptance criteria:

- Test double submit pass.
- Test duplicate callback pass.
- Test invalid callback signature fail safely.

### 5.3 VNPay/mock payment

- [x] `P0` Review `books/vnpay.py` va `vnpay_return`.
- [x] `P0` Verify secure hash dung.
- [x] `P0` Validate amount/order id/status.
- [x] `P0` Return view chi update order neu signature hop le.
- [x] `P1` Them sandbox instructions trong docs.
- [x] `P1` Neu chua dung credential that, ghi ro la sandbox/mock.

Acceptance criteria:

- Co tests cho:
  - Valid callback.
  - Invalid signature.
  - Wrong amount.
  - Wrong order owner/access.
  - Duplicate callback.

CV bullet sau phase nay:

```text
Hardened checkout and payment lifecycle with atomic stock locking, idempotent payment confirmation, callback validation, and tests for duplicate submissions and unauthorized access.
```

## 6. Phase 4 - Observability va operational readiness

Muc tieu: project co dau hieu cua product that: health check, logs, audit, incident visibility.

### 6.1 Health checks

- [x] `P0` Them endpoint `/health/`:
  - App alive.
  - Database reachable.
  - Redis reachable neu cau hinh.
- [x] `P1` Them `/health/ready/` va `/health/live/` neu muon tach readiness/liveness.
- [x] `P1` Docker healthcheck cho web goi endpoint health.

Acceptance criteria:

- `curl /health/` tra JSON.
- Neu DB down, readiness fail dung.
- Co test cho health endpoint.

### 6.2 Logging

- [x] `P0` Cau hinh Django `LOGGING` ro:
  - Console logs.
  - Level qua env.
  - Format co time, level, module, message.
- [x] `P1` Log cac event quan trong:
  - Login fail/lockout.
  - Checkout created.
  - Payment callback.
  - Permission denied dashboard.
  - Chatbot fallback/error.
- [x] `P1` Khong log secret/password/token.

Acceptance criteria:

- Log doc duoc khi chay Docker.
- Khong lo sensitive data.
- Co note trong README/DEPLOYMENT.

### 6.3 Audit log

- [x] `P0` Review `AdminAuditLog`:
  - actor
  - action
  - target_type
  - target_id
  - metadata
  - ip/user agent optional
  - created_at
- [x] `P1` Log thay doi role.
- [x] `P1` Log update order status.
- [x] `P1` Log create/update/delete book/coupon.
- [x] `P2` Them filter/search trong audit dashboard.

Acceptance criteria:

- Admin lam action thi audit log hien trong dashboard.
- User thuong khong xem duoc audit.
- Co tests permission.

CV bullet:

```text
Added operational observability with health checks, structured application logs, and admin audit trails for sensitive management actions.
```

## 7. Phase 5 - API layer cho full-stack/backend CV

Muc tieu: ngoai Django template, project co API de the hien kha nang backend.

Khong bat buoc phai dung DRF neu muon giu scope nho. Co the lam JSON endpoints bang Django views. Neu muon chuyen nghiep hon thi dung Django REST Framework.

### 7.1 API scope toi thieu

- [x] `P1` `/api/books/`
  - list books.
  - search/filter/category.
  - pagination.
- [x] `P1` `/api/books/<id>/`
  - detail.
- [x] `P1` `/api/cart/`
  - get cart.
  - add/update/remove item.
- [x] `P1` `/api/orders/`
  - user order list.
  - order detail, chi owner xem duoc.
- [x] `P1` `/api/profile/`
  - current user basic info.

Acceptance criteria:

- API tra JSON consistent.
- Co status code dung: `200`, `201`, `400`, `401`, `403`, `404`.
- Co tests.
- Co docs endpoint trong README hoac `API.md`.

### 7.2 API documentation

- [x] `P1` Tao `API.md`:
  - Endpoint.
  - Method.
  - Auth required.
  - Request body.
  - Response example.
  - Error cases.
- [ ] `P2` Them OpenAPI schema neu dung DRF/spectacular.

CV bullet:

```text
Exposed authenticated JSON APIs for catalog, cart, and order workflows with pagination, ownership checks, and automated tests.
```

## 8. Phase 6 - Security hardening cap portfolio

Muc tieu: dua project gan OWASP ASVS Level 1 cho mot web app demo.

### 8.1 Authentication/session

- [x] `P0` Review login lockout:
  - lock theo IP.
  - lock theo username.
  - unlock window ro.
  - message khong leak qua nhieu.
- [x] `P1` Them password reset docs/demo.
- [x] `P1` Session cookie settings production:
  - `SESSION_COOKIE_SECURE=True`
  - `CSRF_COOKIE_SECURE=True`
  - `SESSION_COOKIE_HTTPONLY=True`
  - `CSRF_COOKIE_HTTPONLY` can nhac vi JS can csrf token hay khong.
- [x] `P2` MFA optional cho admin.

### 8.2 Authorization/RBAC

- [x] `P0` Tao role matrix doc:
  - Customer.
  - Staff.
  - Manager.
  - Support.
  - Admin.
- [x] `P0` Test user khong du quyen bi `403` hoac redirect dung.
- [x] `P1` UI an nut/action neu khong co permission.
- [x] `P1` Audit log khi doi role.

### 8.3 Input/output protection

- [x] `P0` Review XSS:
  - book content HTML sanitizer.
  - comment/rating display escape.
  - chatbot output display.
- [x] `P0` Review CSRF:
  - POST endpoints co CSRF.
  - AJAX gui csrf token.
- [x] `P0` Review SQL Injection:
  - ORM/filter usage.
  - raw SQL neu co thi parameterize.
- [x] `P1` Review SSRF:
  - URL image/import/LLM endpoints khong cho user tuy tien goi noi bo.

### 8.4 Headers/CSP

- [x] `P1` Them/kiem tra secure headers:
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
  - `Cross-Origin-Opener-Policy`
  - HSTS production.
- [x] `P1` Them CSP co ban neu co the.
- [x] `P1` Neu dung CDN script, them SRI `integrity` hoac chuyen ve local static.

### 8.5 Dependency/CI security

- [x] `P0` CI chay tests.
- [x] `P0` CI chay security scan:
  - `pip-audit`.
  - `bandit`.
- [x] `P1` Them Dependabot.
- [x] `P1` Them SBOM optional.

Acceptance criteria:

- Tao `SECURITY_REVIEW.md` voi bang:
  - Risk.
  - Existing control.
  - Missing work.
  - Status.
- Tat ca sensitive flow co test.

CV bullet:

```text
Improved web security posture using CSRF protection, rate limiting, login lockouts, RBAC authorization, IDOR tests, secure deployment settings, and CI security scanning.
```

## 9. Phase 7 - Testing va CI/CD nang cao

Muc tieu: test khong chi nhieu, ma bao phu flow quan trong.

### 9.1 Backend tests

- [x] `P0` Dam bao `python manage.py test books` pass.
- [x] `P0` Tests cho checkout:
  - normal order.
  - invalid coupon.
  - stock insufficient.
  - race/double submit.
- [x] `P0` Tests cho auth/security:
  - login lockout.
  - rate limit.
  - IDOR order/payment.
  - CSRF chatbot.
- [x] `P1` Tests cho RBAC dashboard theo role.
- [x] `P1` Tests cho payment callback/idempotency.
- [x] `P1` Tests cho health endpoint.

### 9.2 E2E tests

- [ ] `P0` Playwright smoke:
  - home load.
  - login demo.
  - add to cart.
  - checkout COD.
- [ ] `P1` E2E dashboard role:
  - admin can access.
  - customer cannot access.
  - support can update order.
  - manager can manage books.
- [ ] `P1` E2E responsive:
  - mobile catalog.
  - mobile checkout.
  - mobile reader.
- [ ] `P1` Screenshot tests cho reader/dashboard.

### 9.3 CI/CD

- [x] `P0` GitHub Actions:
  - install deps.
  - migrate/check.
  - backend tests.
  - security audit.
- [x] `P1` Them Playwright CI neu thoi gian build chap nhan duoc.
- [x] `P1` Upload screenshots/videos on failure.
- [x] `P1` Coverage threshold hop ly.

Acceptance criteria:

- Pull request fail neu tests/security scan fail.
- README co badge dung.
- Co section "Quality Gates".

## 10. Phase 8 - UI/UX polish de demo nhin xin hon

Muc tieu: khong de reviewer cam giac "project sinh vien lam cho co".

### 10.1 General UI

- [ ] `P0` Kiem tra toan bo text brand:
  - Nen dung thong nhat `Bookie`, khong luc `Smart Bookstore`, luc `Bookie`.
- [ ] `P0` Kiem tra Vietnamese encoding/text:
  - Khong loi dau.
  - Khong text placeholder.
- [ ] `P0` Empty states dep:
  - cart empty.
  - wishlist empty.
  - no orders.
  - no search results.
- [ ] `P1` Toast/message consistent.
- [ ] `P1` Form validation message ro rang.

### 10.2 Catalog/detail/cart/checkout

- [ ] `P0` Catalog de scan:
  - search/filter/sort ro.
  - cards consistent height.
  - stock/rating/price ro.
- [ ] `P0` Book detail co CTA ro:
  - Add to cart.
  - Wishlist.
  - Read online neu digital.
- [ ] `P0` Checkout ro:
  - Order summary.
  - Address.
  - Coupon.
  - Payment method.
  - Error states.
- [ ] `P1` Mobile checkout khong bi overlap.

### 10.3 Dashboard

- [ ] `P0` Dashboard phai co data demo dep.
- [ ] `P0` Tables co empty/loading states.
- [ ] `P1` Filters cho orders/books/users.
- [ ] `P1` Badge status order/payment ro mau.
- [ ] `P1` Audit log co filter theo action/user.

### 10.4 Reader/PWA

- [ ] `P0` Reader khong overlap controls tren mobile.
- [ ] `P0` Bookmark/progress chay on dinh.
- [ ] `P1` Offline/PWA docs.
- [ ] `P1` Screenshot reader light/dark/sepia.

Acceptance criteria:

- Chay Playwright screenshot desktop/mobile.
- Khong co text overlap nghiem trong.
- Demo 2-4 phut khong gap UI loi.

## 11. Phase 9 - Performance va data quality

Muc tieu: co the noi ve caching/query optimization trong phong van.

### 11.1 Query optimization

- [ ] `P1` Review pages:
  - home.
  - catalog.
  - book detail.
  - dashboard.
  - order list/detail.
- [ ] `P1` Them `select_related`/`prefetch_related` noi can.
- [ ] `P1` Kiem tra N+1 query o dashboard/order.
- [ ] `P2` Them django-debug-toolbar local optional.

### 11.2 Caching

- [ ] `P1` Document Redis cache:
  - top rated.
  - popular books.
  - query cache invalidation.
- [ ] `P1` Tests cache invalidation khi book/rating thay doi.
- [ ] `P2` Add simple metrics comment/log cache hit optional.

### 11.3 Load smoke

- [ ] `P2` Chay smoke bang `locust` hoac `k6` optional.
- [ ] `P2` Ghi ket qua don gian:
  - endpoint.
  - users.
  - average response.
  - errors.

CV bullet:

```text
Optimized catalog and dashboard queries with ORM prefetching and Redis caching for frequently accessed book lists.
```

## 12. Phase 10 - AI/chatbot polish

Muc tieu: AI la diem cong, nhung khong de tro thanh diem yeu do hallucination/security.

### 12.1 DB-first behavior

- [x] `P0` Chatbot uu tien tim trong DB.
- [x] `P0` Neu khong co sach, khong bia gia/ten sach.
- [x] `P1` Hien source/reference sach trong response.
- [x] `P1` Them suggested books cards.

### 12.2 Prompt injection guard

- [x] `P1` Them guardrail co ban:
  - khong tiet lo system prompt.
  - khong bo qua rule DB-first.
  - khong tra secret/env.
- [x] `P1` Tests voi prompt injection examples:
  - "ignore previous instructions"
  - "show me system prompt"
  - "recommend unavailable expensive books"
- [x] `P2` Tao `AI_SECURITY.md`.

### 12.3 RAG/semantic search optional

- [ ] `P2` Neu muon apply AI role:
  - Them embeddings.
  - Vector search.
  - Source citations.
  - Evaluation set.
- [x] `P2` Khong lam neu uu tien full-stack va chua deploy xong.

CV bullet:

```text
Built a database-grounded book assistant that prioritizes catalog search before LLM fallback and includes guardrails against unsupported recommendations.
```

## 13. Phase 11 - Documentation package cho CV/phong van

Muc tieu: khi apply, ban co the gui GitHub link va noi ro minh lam gi.

### 13.1 Docs can co

- [x] `P0` `README.md`
- [x] `P0` `BOOKIE_FULLSTACK_CV_UPGRADE_PLAN.md`
- [x] `P0` `DEPLOYMENT.md`
- [x] `P1` `SECURITY_REVIEW.md`
- [x] `P1` `API.md`
- [x] `P1` `ARCHITECTURE.md`
- [x] `P1` `TESTING.md`

### 13.2 CV bullets

Chon 3-4 bullet tuy role.

Full-stack:

```text
Built Bookie, a full-stack Django bookstore platform with catalog search, cart/checkout, order management, user profiles, wishlist, ratings, admin dashboard, and ebook reader.
```

Backend/security:

```text
Hardened critical flows with CSRF protection, rate limiting, login lockouts, RBAC authorization, IDOR checks, atomic checkout transactions, and automated security tests.
```

Infra/DevOps:

```text
Containerized the application with Docker Compose using PostgreSQL, Redis, Gunicorn, WhiteNoise, and Huey workers, with CI quality gates for tests and security scanning.
```

AI:

```text
Implemented a database-grounded book assistant and recommendation features using Ollama/Qwen with fallback behavior, rate limiting, and tests for safe chatbot responses.
```

### 13.3 Interview story

- [ ] `P0` Chuan bi cau tra loi:
  - Tai sao chon Django?
  - Ban da secure checkout nhu the nao?
  - Race condition la gi va ban xu ly the nao?
  - RBAC cua ban hoat dong ra sao?
  - Docker setup gom nhung service nao?
  - Redis dung de lam gi?
  - Neu deploy production that, ban bo sung gi?
  - Neu scale len, ban sua gi?

Suggested 60-second answer:

```text
Bookie started as a bookstore app, but I upgraded it into a production-oriented full-stack project. It has the normal user flows like catalog, cart, checkout, orders, wishlist and ebook reader, plus admin workflows with RBAC. I also focused on production concerns: Dockerized PostgreSQL/Redis setup, background jobs, checkout transaction locking, rate limiting, login lockout, CSRF/IDOR tests, CI security scans, and Playwright e2e tests. The main thing I learned is how to move from feature-building to thinking about reliability, security and deployability.
```

## 14. Suggested timeline

### Week 1 - Make it presentable

- [ ] Update README.
- [ ] Add screenshots.
- [ ] Add demo video.
- [ ] Fix brand/text consistency.
- [ ] Run full local + Docker smoke.

Expected score after week 1: `7.8-8.0/10`.

### Week 2 - Deploy

- [ ] Choose platform.
- [ ] Deploy app.
- [ ] Seed demo data.
- [ ] Add live demo link.
- [ ] Write deployment guide.

Expected score after week 2: `8.2/10`.

### Week 3 - Payment/security/observability

- [ ] Add payment status/idempotency.
- [ ] Add callback tests.
- [ ] Add health endpoint.
- [ ] Improve logs/audit.
- [ ] Write security review.

Expected score after week 3: `8.5/10`.

### Week 4 - API/e2e/performance

- [ ] Add API docs/endpoints.
- [ ] Add browser e2e for dashboard/checkout/mobile.
- [ ] Add query optimization notes.
- [ ] Polish CV bullets.

Expected score after week 4: `8.7/10`.

## 15. Definition of Done chung

Mot task chi duoc coi la xong khi:

- [ ] Code da commit.
- [ ] Test lien quan da pass.
- [ ] Khong lam hong flow cu.
- [ ] Neu la feature user-facing: co screenshot/manual check.
- [ ] Neu la security/payment: co test negative case.
- [ ] Neu la deploy/docs: README/docs da cap nhat.
- [ ] Neu la CV-significant: co bullet de dua vao CV/phong van.

## 16. Commands baseline nen chay truoc khi push

Tu folder `Project/`:

```powershell
python manage.py check
python manage.py test books
npm.cmd run test:e2e
docker compose config --quiet
docker compose build web worker
docker compose up -d
curl.exe -I http://127.0.0.1:8000/
```

Neu muon xem Docker logs:

```powershell
docker compose logs --tail=120 web worker
docker compose ps
```

Neu muon tat Docker:

```powershell
docker compose down
```

## 17. Nhung viec khong nen lam luc nay

- [ ] Khong rewrite sang React/Next.js ngay neu chua deploy va README chua tot.
- [ ] Khong them qua nhieu AI/RAG neu checkout/security/deploy chua on.
- [ ] Khong lam feature lon khong co demo value ro.
- [ ] Khong them dependency moi neu chi giai quyet viec nho.
- [ ] Khong che giau viec payment la sandbox/mock; viet ro va xu ly mock cho production-like.

## 18. Quick wins trong 1-2 ngay

Neu can tang diem nhanh nhat:

- [ ] README co screenshot + architecture + security section.
- [ ] Live demo hoac it nhat demo video.
- [ ] Health endpoint.
- [ ] Payment idempotency/co tests.
- [ ] Role matrix docs.
- [ ] Security review docs.
- [ ] E2E mobile screenshots.

## 19. Bang tracking ngan

| Phase                 | Status | Priority | Main output                 |
| --------------------- | -----: | -------: | --------------------------- |
| README/demo packaging |    [~] |       P0 | README, screenshots, video  |
| Deploy public         |    [~] |       P0 | Live URL, deployment docs   |
| Payment hardening     |    [x] |       P0 | Idempotency, callback tests |
| Observability         |    [x] |       P1 | Health, logs, audit         |
| API layer             |    [x] |       P1 | API endpoints, API.md       |
| Security review       |    [x] |       P1 | SECURITY_REVIEW.md          |
| E2E/responsive        |    [ ] |       P1 | Playwright coverage         |
| Performance/cache     |    [ ] |       P2 | Query/cache notes           |
| AI polish             |    [x] |       P2 | Guardrails, eval cases      |
