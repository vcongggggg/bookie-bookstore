# Bookie Feature Screenshot Index

Generated on 2026-06-23 from the local Docker app at `http://127.0.0.1:8000`.

## Public And Auth

- `01-public-home.png` - home page and product positioning
- `02-public-book-catalog.png` - book catalog
- `03-public-search-results.png` - catalog search results
- `04-public-ebook-library.png` - ebook/online reading library
- `05-public-book-detail-top.png` - book detail, price, stock, actions
- `06-public-book-detail-reviews-sentiment.png` - reviews and sentiment area
- `07-public-categories.png` - category overview
- `08-public-category-detail.png` - category detail listing
- `09-public-about.png` - about page
- `10-public-contact.png` - contact page
- `11-auth-login.png` - login page
- `12-auth-register.png` - registration page
- `13-auth-password-reset.png` - password reset page

## Customer Account And Commerce

- `14-customer-profile.png` - user profile summary
- `15-customer-profile-edit.png` - profile edit form
- `16-customer-change-password.png` - password change form
- `17-customer-reading-dna.png` - Reading DNA analytics
- `18-customer-reading-history.png` - reading progress/history
- `19-customer-wishlist.png` - wishlist
- `20-customer-order-list.png` - order history
- `21-customer-order-detail.png` - order detail
- `23-customer-book-detail-rating-form.png` - rating form on book detail
- `24-customer-book-sentiment-analysis.png` - AI sentiment summary from reviews
- `25-commerce-cart.png` - cart
- `26-commerce-checkout-cod.png` - checkout with COD
- `27-commerce-checkout-momo-selected.png` - checkout with Momo selected
- `28-commerce-payment-momo-mock.png` - simulated Momo payment page
- `29-commerce-paid-order-detail.png` - paid order detail after mock confirmation

## Reader And AI

- `30-reader-default.png` - online reader
- `31-reader-settings-panel.png` - reader settings panel
- `32-ai-chatbot-open.png` - chatbot with mocked recommendation response

## API And Operations

- `33-api-profile-json.png` - profile API JSON
- `34-api-orders-json.png` - orders API JSON
- `45-api-stats-json.png` - stats API JSON
- `46-health-live-json.png` - liveness health endpoint
- `47-health-ready-json.png` - readiness health endpoint

## Admin And RBAC

- `35-admin-dashboard-analytics.png` - dashboard analytics
- `36-admin-user-management.png` - user management
- `37-admin-user-detail-rbac.png` - user detail and RBAC controls
- `38-admin-book-management.png` - book management
- `39-admin-book-create-form.png` - book create form
- `40-admin-coupon-management.png` - coupon management
- `41-admin-coupon-create-form.png` - coupon create form
- `42-admin-order-management.png` - order management
- `43-admin-audit-log.png` - audit log
- `44-django-admin-panel.png` - Django admin panel

## Notes

- `22-customer-invoice-pdf-preview.png` is intentionally skipped because the
  invoice route returns a PDF download in headless Chromium instead of a
  renderable HTML page.
- The screenshot run uncovered and fixed a sentiment bug where book detail pages
  could fail with `NameError: _POSITIVE_WORDS is not defined`.
