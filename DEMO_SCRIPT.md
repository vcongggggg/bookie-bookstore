# Bookie Demo Script

Target length: 2 to 4 minutes.

## 0:00 - 0:20 Opening

Bookie is a full-stack Django bookstore platform. I built it beyond basic CRUD by adding catalog search, cart and checkout, order management, RBAC dashboard, an offline ebook reader, background jobs, JSON APIs, health checks, and security-focused checkout/payment handling.

## 0:20 - 0:50 Catalog And Book Detail

Open the home page and catalog.

Show:

- Search/filter/sort.
- Book cards with price, stock, and category.
- Book detail page with rating, wishlist, and add-to-cart action.

Talk track:

The catalog uses Django ORM queries and pagination-style API behavior. The project also uses Redis caching for high-traffic book lists.

## 0:50 - 1:30 Cart, Checkout, And Payment

Add a book to cart, open cart, then checkout.

Show:

- Quantity update and stock-aware validation.
- Shipping address form.
- Coupon field.
- Payment method selection.
- COD checkout or simulated Momo payment.

Talk track:

Checkout is protected with idempotency keys and database row locking using `select_for_update()` so double-submit or concurrent checkout does not deduct stock twice. Momo payment is a local simulation, while VNPay uses a return handler with checksum, amount, method, and replay checks.

## 1:30 - 2:05 Orders

Open order detail/history.

Show:

- Order status.
- Payment status.
- Items and total.
- Invoice PDF action.

Talk track:

Order access is scoped to the owner. The JSON order detail API also blocks IDOR-style access unless the requester owns the order or is staff.

## 2:05 - 2:40 Admin Dashboard And RBAC

Login as `admin/admin123` or use an already logged-in admin browser.

Show:

- Dashboard overview.
- Orders page.
- Users or role management.
- Audit logs.

Talk track:

The dashboard has role-based access for Customer, Support, Staff, Manager, and Admin. Sensitive admin actions are captured in audit logs.

## 2:40 - 3:15 Reader And AI Assistant

Open the reader and chatbot.

Show:

- Ebook reader controls and progress.
- Chatbot response with book recommendation.

Talk track:

The reader supports PWA/offline behavior through a service worker. The assistant is database-grounded and includes basic prompt-injection guardrails to avoid recommending unavailable books or leaking system instructions.

## 3:15 - 3:45 Engineering Close

Show GitHub README or docs links.

Mention:

- `API.md` for JSON endpoints.
- `SECURITY_REVIEW.md` for security controls and gaps.
- `DEPLOYMENT.md` for Docker/deploy notes.
- Automated tests and CI security scans.

Closing line:

The main thing I learned from Bookie was how to move from building features to thinking like a product engineer: reliability, security, observability, deployability, and clear documentation.
