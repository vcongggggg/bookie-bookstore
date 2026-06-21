# Bookie JSON API Reference

This document describes the JSON REST-like API exposed by Bookie for catalog browsing, cart operations, order lookup, profile lookup, and operational health checks.

## Base URL

Local development base URL: `http://localhost:8000`

Versioned API base path: `/api/v1`

## Response Conventions

Successful responses keep the endpoint-specific payload shape shown below.

Error responses use this minimal shape:

```json
{
  "status": "error",
  "message": "Human-readable error message"
}
```

Common status codes:

| Status | Meaning |
| :--- | :--- |
| `200 OK` | Request succeeded. |
| `302 Found` | Session-authenticated endpoint redirected an anonymous user to login. |
| `400 Bad Request` | Invalid input, invalid action, invalid JSON, invalid category, or stock validation failure. |
| `403 Forbidden` | Authenticated user is not allowed to access the requested resource. |
| `404 Not Found` | Resource does not exist. |
| `405 Method Not Allowed` | Endpoint does not support the HTTP method. |

---

## Catalog

### List Books

Returns a paginated list of books with optional search, category filtering, and sorting.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/books/` |
| Method | `GET` |
| Auth | Public |

Query parameters:

| Parameter | Type | Notes |
| :--- | :--- | :--- |
| `page` | integer | Defaults to `1`; invalid values safely fall back to `1`. |
| `per_page` | integer | Defaults to `20`; capped at `50`. |
| `q` | string | Searches book title/author. |
| `category` | integer | Category ID. Non-integer values return `400`. |
| `sort` | string | Supports existing catalog sort keys, for example `title`, `price`, `-price`. |

Response example:

```json
{
  "count": 39,
  "num_pages": 2,
  "current_page": 1,
  "results": [
    {
      "id": 1,
      "title": "Midnight Stars",
      "author": "A. Asteroid",
      "price": 125000.0,
      "category": "Sci-Fi",
      "published_year": 2024,
      "stock": 15,
      "in_stock": true,
      "cover_image": "/media/covers/midnight_stars.jpg",
      "description": "An epic cosmic journey...",
      "url": "/books/1/"
    }
  ]
}
```

### Book Detail

Returns detailed information for one book, including rating aggregates and sentiment summary.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/books/<id>/` |
| Method | `GET` |
| Auth | Public |

Response example:

```json
{
  "id": 1,
  "title": "Midnight Stars",
  "author": "A. Asteroid",
  "price": 125000.0,
  "description": "An epic cosmic journey...",
  "category": "Sci-Fi",
  "published_year": 2024,
  "num_pages": 320,
  "stock": 15,
  "in_stock": true,
  "cover_image": "/media/covers/midnight_stars.jpg",
  "avg_rating": 4.5,
  "rating_count": 12,
  "sentiment": {
    "summary": "Readers respond positively to the pacing.",
    "polarity": "Positive",
    "score": 0.85
  }
}
```

### Stats

Returns public bookstore metrics.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/stats/` |
| Method | `GET` |
| Auth | Public |

Response example:

```json
{
  "total_books": 39,
  "total_categories": 6,
  "total_ratings": 24,
  "avg_rating": 4.21
}
```

---

## Cart

### View Cart

Returns the current session cart.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/cart/` |
| Method | `GET` |
| Auth | Public session cookie |

Response example:

```json
{
  "cart_items": [
    {
      "book_id": 1,
      "title": "Midnight Stars",
      "price": 125000.0,
      "quantity": 2,
      "subtotal": 250000.0,
      "cover_image": "/media/covers/midnight_stars.jpg"
    }
  ],
  "cart_total": 250000.0
}
```

### Update Cart

Adds, updates, or removes a cart item.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/cart/` |
| Method | `POST` |
| Auth | Public session cookie plus CSRF token |

Headers:

```text
Content-Type: application/json
X-CSRFToken: <token>
```

Payload fields:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `action` | string | Required. One of `add`, `update`, `remove`. |
| `book_id` | integer/string | Required. |
| `quantity` | integer | Required for `update`, optional for `add` with default `1`. Must be positive. |

Add example:

```json
{
  "action": "add",
  "book_id": 1,
  "quantity": 1
}
```

Stock validation:

- Adding an out-of-stock book returns `400`.
- Adding a quantity that would make the session cart exceed current stock returns `400`.
- Updating a quantity beyond current stock returns `400`.

Success response returns the same shape as `GET /api/v1/cart/`.

---

## Orders And Profile

### List Orders

Returns orders owned by the authenticated user.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/orders/` |
| Method | `GET` |
| Auth | Required |

Response example:

```json
{
  "orders": [
    {
      "id": 10,
      "status": "pending",
      "status_vi": "Awaiting payment",
      "payment_method": "vnpay",
      "payment_status": "pending",
      "total": 350000.0,
      "created_at": "2026-06-20T10:15:30+00:00"
    }
  ]
}
```

### Order Detail

Returns one order with itemized contents. Owners and staff users can access the resource.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/orders/<id>/` |
| Method | `GET` |
| Auth | Required |

Authorization rule:

- Owner: allowed.
- Staff: allowed.
- Other authenticated users: `403`.

Response example:

```json
{
  "id": 10,
  "status": "paid",
  "status_vi": "Paid",
  "payment_method": "vnpay",
  "payment_status": "paid",
  "paid_at": "2026-06-20T10:17:12+00:00",
  "transaction_id": "VNP12345678",
  "discount_amount": 0.0,
  "subtotal": 350000.0,
  "total": 350000.0,
  "shipping_address": "123 Cosmic Way, Da Nang",
  "note": "Deliver in the evening",
  "created_at": "2026-06-20T10:15:30+00:00",
  "items": [
    {
      "book_id": 1,
      "title": "Midnight Stars",
      "quantity": 2,
      "price": 125000.0,
      "subtotal": 250000.0
    }
  ]
}
```

### Profile

Returns the authenticated user's profile and primary RBAC role.

| Field | Value |
| :--- | :--- |
| URL | `/api/v1/profile/` |
| Method | `GET` |
| Auth | Required |

Response example:

```json
{
  "username": "democustomer",
  "email": "customer@bookie.local",
  "first_name": "Demo",
  "last_name": "Customer",
  "date_joined": "2026-06-18T08:00:00+00:00",
  "is_staff": false,
  "primary_role": "Customer"
}
```

---

## Operational Health

Health endpoints are not versioned because they are operational probes, not product API resources.

| URL | Method | Purpose | Dependency Checks |
| :--- | :--- | :--- | :--- |
| `/health/` | `GET` | Full application health summary. | Database and cache. |
| `/health/live/` | `GET` | Liveness probe for process availability. | None. |
| `/health/ready/` | `GET` | Readiness probe before routing traffic. | Database and cache. |

Use `/health/live/` for container liveness checks and `/health/ready/` for readiness checks.
