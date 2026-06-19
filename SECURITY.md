# Security Policy

This document outlines the security controls, practices, and vulnerability reporting procedures for **Bookie — Next-Gen AI Bookstore**.

## Security Controls Implemented

Bookie is built with multiple layers of defense to protect user accounts, transaction data, and system resources.

### 1. Authentication & Session Security
- **Soft Account Lockout:** Protects accounts from brute-force attempts. After **5 failed attempts**, the IP and username are locked out for **15 minutes**.
- **Secure Cookies:** Standardized HTTP-only sessions. Configurable secure cookies for TLS environments.

### 2. Transaction Integrity & Race Condition Protection
- **Atomic Transactions:** Uses Django's `transaction.atomic()` to prevent partial order creation.
- **Stock Lockouts:** Utilizes `select_for_update()` to lock stock records during ordering and cancellation, preventing race conditions like double-purchasing limited inventory.
- **Decimal Math:** Standardized on `Decimal` precision for all pricing and discount calculations to avoid float inaccuracies.
- **Payment State Checking:** Ensures that order status can only transition from `pending` to `confirmed` upon payment verification, ignoring re-submitted or completed states.

### 3. API Security & Rate Limiting
- **CSRF Protection:** Required for all modifying endpoints, including cart adjustments and chatbot requests.
- **Shared Rate Limiting:** Dynamic rate limit enforcement by IP or authenticated user ID across Chatbot, User Registration, Coupon validation, and Checkout APIs.
- **GET request restriction:** Modifying operations (like adding or removing items from the cart) reject GET requests and require POST.

### 4. Content Safety
- **HTML Sanitization:** Raw ebook HTML is dynamically sanitized to strip out unsafe tags (e.g. `<script>`, `<iframe>`, `<style>`) while preserving formatting and Gutenberg images.

---

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it immediately:
1. **Do not** open a public issue on GitHub.
2. Email details of the issue to the development team or administrator.
3. Include clear steps or scripts to reproduce the issue.

We will review the report and coordinate a patch promptly. Thank you for helping keep Bookie safe!
