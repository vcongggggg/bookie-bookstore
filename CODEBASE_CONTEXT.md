# Bookie Codebase Context

## Current Shape

- Main Django project is under `Project/`. The old root-level Django tree has been removed from tracking to avoid import conflicts.
- Active Git branch: `feature/reader-mode`.
- Recent commits added Ollama chatbot/recommendations, payment work, digital reader/progress, and admin dashboard management.
- Current working tree is dirty. Notable modified files: `Project/books/views.py`, `Project/books/urls.py`, `Project/books/chatbot.py`, `Project/books/tests.py`, `Project/bookstore/settings.py`, `Project/README.md`, and `Project/.env`.

## Main Features Already Present

- Book catalog with categories, details, ratings, wishlist, cart, checkout, order tracking, coupons, CSV exports.
- AI features: Ollama-backed Bookie chatbot, content/popularity recommendations, sentiment helpers, Reading DNA.
- E-commerce: COD, Momo/VNPay UI flow, VNPay helper module, order status lifecycle.
- Reader groundwork: `Book.is_digital`, `Book.content_text`, `ReadingProgress`, `reader.html`.
- Admin groundwork: Django admin registrations, custom dashboard templates, `AdminAuditLog` model.

## Current Risks Before New Upgrades

- `Project/manage.py` switches into `Project/` before running commands, so root-invoked commands such as `python Project/manage.py test books` use the intended app.
- `Project/.env` is now ignored and removed from the Git index; `Project/.env.example` contains safe placeholder config.
- `Project/bookstore/settings.py` now uses SQLite automatically for tests or when `DB_HOST` is absent, while retaining MySQL for configured local/prod runs.
- Reader routes, progress API routes, and custom dashboard routes are restored in `Project/books/urls.py`.
- Chatbot streaming now calls `BookieChatbot.build_prompt(...)`; one legacy sync fallback remains renamed as `api_chatbot_sync_unused`.
- `Project/books/tests.py` has basic page tests plus smoke coverage for reader/progress and restored dashboard URL names.

## Upgrade Priority Recommendation

1. Stabilize the current branch: restore missing routes/views, fix chatbot streaming, restore meaningful tests, and make tests runnable without a live MySQL service.
2. Secure configuration: stop tracking real `.env`, add `.env.example`, and document setup.
3. Finish reader basics: reader URL, progress API, preview/purchase checks, then personalization/TTS.
4. Improve payment sandbox only after checkout/order flows are covered by tests.
5. Add AI/RAG or semantic search after there is a clean ingestion path for digital content and a stable chatbot API.
