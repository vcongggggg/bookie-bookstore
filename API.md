# Bookie JSON API Reference

This document describes the JSON REST-like API endpoints exposed by Bookie. These endpoints allow client-side application flows or external services to interact with books, carts, orders, and user profiles.

## Base URL
All API paths are relative to the root URL (e.g., `http://localhost:8000`).

---

## 1. Catalog & Books

### List Books
Retrieve a paginated list of books, with support for search, category filtering, and sorting.

* **URL:** `/api/books/`
* **Method:** `GET`
* **Authentication Required:** No
* **Query Parameters:**
  * `page` (integer, default: `1`): The page number to retrieve.
  * `per_page` (integer, default: `20`, max: `50`): Number of books per page.
  * `q` (string): Search query matching book titles or authors.
  * `category` (integer): ID of the category to filter by.
  * `sort` (string, default: `title`): Sorting criteria. Prefix with `-` for descending (e.g. `-price`, `price`, `title`).

* **Response Example (200 OK):**
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
      "description": "An epic cosmic journey exploring the depths of the universe...",
      "url": "/books/1/"
    }
  ]
}
```

---

### Book Detail
Retrieve detailed information for a single book, including average rating and AI review sentiment.

* **URL:** `/api/books/<int:pk>/`
* **Method:** `GET`
* **Authentication Required:** No

* **Response Example (200 OK):**
```json
{
  "id": 1,
  "title": "Midnight Stars",
  "author": "A. Asteroid",
  "price": 125000.0,
  "description": "An epic cosmic journey exploring the depths of the universe...",
  "category": "Sci-Fi",
  "published_year": 2024,
  "num_pages": 320,
  "stock": 15,
  "in_stock": true,
  "cover_image": "/media/covers/midnight_stars.jpg",
  "avg_rating": 4.5,
  "rating_count": 12,
  "sentiment": {
    "summary": "Highly recommended for fans of hard sci-fi. Readers appreciate the pacing.",
    "polarity": "Positive",
    "score": 0.85
  }
}
```

---

### Global Stats
Retrieve public summary metrics of the bookstore.

* **URL:** `/api/stats/`
* **Method:** `GET`
* **Authentication Required:** No

* **Response Example (200 OK):**
```json
{
  "total_books": 39,
  "total_categories": 6,
  "total_ratings": 24,
  "avg_rating": 4.21
}
```

---

## 2. Shopping Cart

### View or Update Cart
Retrieve current session-based cart items or perform state operations (add, update, remove items).

* **URL:** `/api/cart/`
* **Method:** `GET` | `POST`
* **Authentication Required:** No (uses session cookies)

#### GET Request
Retrieves the list of books currently in the user's cart.

* **Response Example (200 OK):**
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

#### POST Request
Modifies items in the cart. Requires a JSON payload.

* **Headers:** `Content-Type: application/json`, `X-CSRFToken: <token>`
* **Payload Fields:**
  * `action` (string, required): Choice of `"add"`, `"update"`, or `"remove"`.
  * `book_id` (integer/string, required): The ID of the book.
  * `quantity` (integer, optional): The quantity to add or update (defaults to `1` for add).

* **Payload Example (Add):**
```json
{
  "action": "add",
  "book_id": 1,
  "quantity": 1
}
```

* **Payload Example (Update):**
```json
{
  "action": "update",
  "book_id": 1,
  "quantity": 3
}
```

* **Payload Example (Remove):**
```json
{
  "action": "remove",
  "book_id": 1
}
```

* **Response Example (200 OK):** Returns the updated cart payload matching the GET response format.

---

## 3. Orders & Profile

### List User Orders
Retrieve a chronological list of orders associated with the authenticated user.

* **URL:** `/api/orders/`
* **Method:** `GET`
* **Authentication Required:** Yes (via session/cookie)

* **Response Example (200 OK):**
```json
{
  "orders": [
    {
      "id": 10,
      "status": "pending",
      "status_vi": "Chờ thanh toán",
      "payment_method": "vnpay",
      "payment_status": "unpaid",
      "total": 350000.0,
      "created_at": "2026-06-20T10:15:30Z"
    }
  ]
}
```

---

### Order Details
Retrieve itemized contents and payment metadata of a specific order. Owners and staff users only.

* **URL:** `/api/orders/<int:pk>/`
* **Method:** `GET`
* **Authentication Required:** Yes (Owner-only or Staff-only verification)

* **Response Example (200 OK):**
```json
{
  "id": 10,
  "status": "paid",
  "status_vi": "Đã thanh toán",
  "payment_method": "vnpay",
  "payment_status": "paid",
  "paid_at": "2026-06-20T10:17:12Z",
  "transaction_id": "VNP12345678",
  "discount_amount": 0.0,
  "subtotal": 350000.0,
  "total": 350000.0,
  "shipping_address": "123 Cosmic Way, Hanoi",
  "note": "Deliver in the evening",
  "created_at": "2026-06-20T10:15:30Z",
  "items": [
    {
      "book_id": 1,
      "title": "Midnight Stars",
      "quantity": 2,
      "price": 125000.0,
      "subtotal": 250000.0
    },
    {
      "book_id": 5,
      "title": "Cosmic Nebulae",
      "quantity": 1,
      "price": 100000.0,
      "subtotal": 100000.0
    }
  ]
}
```

* **Error Example (403 Forbidden):**
```json
{
  "status": "error",
  "message": "Bạn không có quyền xem đơn hàng này."
}
```

---

### User Profile
Retrieve profile data and RBAC permissions for the currently authenticated user.

* **URL:** `/api/profile/`
* **Method:** `GET`
* **Authentication Required:** Yes

* **Response Example (200 OK):**
```json
{
  "username": "democustomer",
  "email": "customer@bookie.local",
  "first_name": "Demo",
  "last_name": "Customer",
  "date_joined": "2026-06-18T08:00:00Z",
  "is_staff": false,
  "primary_role": "Customer"
}
```
