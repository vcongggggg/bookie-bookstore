# Bookie Security Architecture & Review

This document provides a comprehensive security review of the **Bookie** bookstore application. It maps out potential risks, implementation controls, testing strategies, and CI/CD quality gates designed to achieve professional production-grade security.

---

## 1. Authentication & Session Management

### Risks
* **Brute-Force Attacks:** Attackers guessing passwords to hijack customer or administrator accounts.
* **Session Hijacking / Leakage:** Credentials or sessions intercepted via network sniffing or XSS.

### Controls Implemented
* **Authenticating Lockout:** Implemented a sliding window lockout inside the authentication views (`books/views/auth.py`). After **5 failed attempts within 15 minutes**, both the IP address and the targeted username are locked out. Lockout events are logged with severity level `WARNING` for monitoring.
* **HTTP-Only Cookies:** Django session and CSRF cookies are configured with `HttpOnly=True` to prevent access via JavaScript.
* **Secure Cookie Bindings:** Configured for TLS production environments via:
  ```python
  SESSION_COOKIE_SECURE = True
  CSRF_COOKIE_SECURE = True
  SECURE_SSL_REDIRECT = True
  ```

---

## 2. Authorization & RBAC (Role-Based Access Control)

### Risks
* **IDOR (Insecure Direct Object Reference):** Users modifying URL parameters to view, cancel, or confirm payments of other customers' orders.
* **Privilege Escalation:** Regular users gaining access to administrative dashboards, inventory metrics, or audit logs.

### Controls Implemented
* **Strict Ownership Validation:** All user-facing views retrieve orders using filter constraints linked to the authenticated request user (e.g., `request.user.orders.all()`).
* **API Shielding:** The JSON detail API (`api_order_detail`) validates that the requesting user matches the order owner or holds `is_staff` privileges, returning a `403 Forbidden` JSON payload on unauthorized access.
* **Granular Role Hierarchy:** Defined a 5-role matrix (Customer, Support, Staff, Manager, Admin) using Django's group permission system, mapped visually inside the admin dashboards:
  * **Customer:** Browses books, reads ebooks, views their own orders.
  * **Support:** Can view and update status of orders.
  * **Manager:** Can manage categories and inventory.
  * **Admin:** Master access + audit logs.

---

## 3. Input & Output Protection

### Risks
* **Cross-Site Scripting (XSS):** Malicious inputs injected into comments, ratings, or ebook content rendering scripts in other users' browsers.
* **SQL Injection (SQLi):** Raw string interpolation in search fields exposing database schemas.
* **Prompt Injection (AI Chatbot):** Attackers instructing the chatbot to ignore constraints, output system instructions, or recommend unavailable products.

### Controls Implemented
* **HTML Sanitization:** A custom `HTMLParser` runs on uploaded ebook HTML blocks to strip out tags like `<script>`, `<iframe>`, and `<style>` while retaining formatting and Gutenberg image layouts.
* **ORM Parameterization:** The application queries books and catalogs exclusively using Django ORM syntax (`Book.objects.filter(...)`), which automatically escapes and parameterizes database variables to mitigate SQLi vectors.
* **Default Auto-Escaping:** Django templates utilize the auto-escape feature to output user-submitted fields as safe plain text.
* **Chatbot Injection Shields:** The AI query handler checks questions against a blacklist of prompt-injection keywords (e.g., `"ignore previous instructions"`, `"system prompt"`, `"you are now"`). Responses are blocked and safe fallback messages are rendered if threat criteria are met.

---

## 4. Transaction Integrity & Payment Security

### Risks
* **Race Conditions / Double-Submit:** Double clicking "Place Order" creating duplicate orders and deducting inventory twice.
* **Stock Exhaustion:** Multiple simultaneous checkouts for a book with 1 item remaining leading to negative stock counts.
* **Price Tampering:** Tampering with POST payload variables to buy a book for less.
* **Payment Hook Tampering:** Spoofing payment provider callbacks to mark orders as paid without completing transaction charges.

### Controls Implemented
* **Idempotency Keys:** Every checkout render injects a unique UUID token into a hidden input field. Order service logic saves this token inside the `Order` model under a `unique` constraint inside a locked transaction. Subsequent posts with the same token fail validation and trigger safe page updates.
* **Pessimistic Inventory Locking:** The checkout database transaction locks inventory rows using Django's `select_for_update(of=('self',))` inside an atomic block, verifying stock availability before committing deductions.
* **Backend Amount Verification:** The payment validation handler (`vnpay_return` and mock `payment_confirm` callbacks) extracts transaction metadata, re-calculates order formulas on the database layer, and validates matching values before setting the status to `paid`.
* **State Transition Locking:** Orders can transition to `paid` or `cancelled` status only once; repeated callbacks are skipped to prevent side effects.

---

## 5. Security & Static Analysis (CI/CD)

### Controls Implemented
* **Automatic Dependency Audit:** The GitHub Actions pipeline runs `pip-audit` to detect known vulnerabilities in third-party Python packages.
* **Codebase Scanning:** `bandit` scans for bad design choices (e.g., using `assert`, using unsafe random generators, raw subprocess executions) on every commit.

---

## 6. Security Posture Summary Matrix

| Risk Vector | Threat Target | Existing Control | Status |
| :--- | :--- | :--- | :--- |
| **Brute Force** | Admin/Customer Login | Sliding lockout window (5 attempts/15m) + Security Logs | **Secured** |
| **SQL Injection** | Catalog Search / API | 100% Parameterized Django ORM usage | **Secured** |
| **XSS** | Ebook Viewer / Ratings | HTML sanitizer + Django Template Auto-escape | **Secured** |
| **IDOR** | Order / Cart Details | User scoping on order views + `api_order_detail` ownership checks | **Secured** |
| **Price Tampering** | Payment Gateway | Server-side recalculation and validation in IPN callback | **Secured** |
| **Double Spend** | Checkout / VNPay | Concurrency row locks + unique Idempotency Keys | **Secured** |
| **AI Prompt Abuse**| Chatbot Assistant | Lexical screening & strict prompt anchoring | **Secured** |
