# Bookie Screenshot Checklist

Use this folder for portfolio screenshots shown in `README.md` and GitHub previews.

## Naming Convention

Desktop screenshots use `desktop-XX-name.png`.

Mobile screenshots use `mobile-XX-name.png`.

Keep screenshots free of real secrets, personal email inboxes, production tokens, or private user data.

## Desktop Screenshots

| File | View | Notes |
| :--- | :--- | :--- |
| `desktop-01-home.png` | Home | Show the Bookie brand, featured books, and navigation. |
| `desktop-02-catalog.png` | Catalog | Include search/filter/sort UI with demo data. |
| `desktop-03-book-detail.png` | Book detail | Show price, rating, stock, wishlist/cart CTA. |
| `desktop-04-cart.png` | Cart | Show quantity controls and totals. |
| `desktop-05-checkout.png` | Checkout | Show shipping form, coupon, order summary, payment method. |
| `desktop-06-payment-momo.png` | Momo mock payment | Must clearly show this is simulated payment. |
| `desktop-07-order-detail.png` | Order detail | Show payment/order status and invoice action. |
| `desktop-08-dashboard.png` | Admin dashboard | Use demo admin account only. |
| `desktop-09-reader.png` | Ebook reader | Show content and reader controls. |
| `desktop-10-chatbot.png` | Chatbot | Show catalog-grounded recommendation response. |

## Mobile Screenshots

| File | View | Notes |
| :--- | :--- | :--- |
| `mobile-01-home.png` | Home | No horizontal overflow. |
| `mobile-02-catalog.png` | Catalog | Cards and filters should fit. |
| `mobile-03-checkout.png` | Checkout | Form fields and summary should not overlap. |
| `mobile-04-reader.png` | Reader | Controls should remain usable. |

## Capture Command

After Phase 5, screenshots should be generated automatically by:

```powershell
cd Project
npm.cmd run screenshots
```

Manual screenshots are acceptable before automation exists, but keep the same filenames.
