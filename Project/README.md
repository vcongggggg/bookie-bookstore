# 🌌 Bookie — Next-Gen AI Bookstore ✦

[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django)](https://www.djangoproject.com/)
[![Ollama](https://img.shields.io/badge/AI-Ollama-FBDB41?style=for-the-badge&logo=ollama)](https://ollama.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)

**Bookie** không chỉ là một nhà sách trực tuyến, mà là một trải nghiệm **Midnight Cosmic** cao cấp. Chúng tôi tái định nghĩa cách người dùng tương tác với tri thức thông qua Trí tuệ nhân tạo (AI), hiệu ứng 3D điện ảnh và hệ thống phân tích dữ liệu chuyên sâu.

---

## 🚀 Tính năng Đột phá (Core Highlights)

### 1. Trợ lý ảo Thông minh (AI Chatbot)
*   **Kiến trúc Streaming:** Phản hồi ngay lập tức (Real-time) giống như ChatGPT.
*   **Database-Grounded:** AI tra cứu trực tiếp trong kho sách thực tế để tư vấn chính xác, tránh hiện tượng "hallucination" (bịa đặt).
*   **Giao diện linh hoạt:** Chatbot có khả năng kéo thả (Draggable) và thu nhỏ cực kỳ mượt mà.

### 2. Reading DNA Dashboard (Dữ liệu thị giác)
*   **Radar Chart:** Phân tích "sức mạnh" sở thích qua 5 nhóm chủ đề chính.
*   **Trend Analysis:** Biểu đồ đường theo dõi phong độ đọc sách trong 6 tháng gần nhất.
*   **AI Persona:** Bookie AI tự động nhận diện hệ độc giả của bạn (Explorer, Dreamer, Builder...) dựa trên hành vi mua sắm.

### 3. Trải nghiệm Midnight Cosmic (UI/UX)
*   **3D Landing Page:** Giao diện trang chủ sử dụng GSAP và hiệu ứng Aurora Mesh sống động.
*   **Cinematic Book Cards:** Thẻ sách với hiệu ứng phản chiếu ánh sáng (Glare) và tương tác vật lý.
*   **Glassmorphism:** Toàn bộ hệ thống sử dụng hiệu ứng kính mờ cao cấp, tối ưu cho chế độ tối (Dark Mode).

---

## 🛠 Technology Stack

| Thành phần | Công nghệ |
| :--- | :--- |
| **Backend** | Django 6.0 (Python 3.12) |
| **Database** | **PostgreSQL 15** (Containerized) |
| **AI Engine** | **Ollama** (Model: **Qwen 2.5 7B**) |
| **Frontend** | GSAP, Chart.js, Vanilla JS, Bootstrap 5 |
| **DevOps** | **Docker**, Docker Compose |
| **Cache** | **Redis 7** (Alpine) |

---

## 📦 Hướng dẫn Cài đặt nhanh (Docker)

Cách nhanh nhất để chạy dự án mà không cần cài đặt Python hay Database:

1. **Chuẩn bị:** Cài đặt [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. **Cấu hình .env:** Tạo file `.env` tại thư mục gốc:
   ```env
   DEBUG=1
   SECRET_KEY=your-secret-key
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   ```
3. **Khởi chạy:**
   ```bash
   docker-compose up --build
   ```
4. **Khởi tạo dữ liệu (Chạy 1 lần duy nhất):**
   ```bash
   # Migrate Database
   docker-compose exec web python manage.py migrate
   # Seed dữ liệu sách mẫu
   docker-compose exec web python manage.py seed_books --limit 50
   # Tạo tài khoản Admin
   docker-compose exec web python manage.py createsuperuser
   ```
5. **Truy cập:** Mở trình duyệt tại `http://localhost:8000`.

---

## 📖 Hướng dẫn Phát triển (Local Development)

Nếu bạn muốn chạy thủ công không dùng Docker:

```bash
# 1. Cài đặt thư viện
pip install -r requirements.txt

# 2. Setup Database (SQLite mặc định)
python manage.py migrate
python manage.py seed_books --limit 20

# 3. Chạy Server
python manage.py runserver
```

---

## 🛡️ Bảo mật & Hiệu năng
*   **Environment Variables:** Toàn bộ thông số nhạy cảm được quản lý qua file `.env`.
*   **Asset Optimization:** Tự động nén ảnh bìa và tối ưu hóa file tĩnh qua Django Static Files.
*   **Security:** Tích hợp CSRF Protection, Password Hashing và XSS filtering chuẩn Django.

---
**Dự án được thực hiện bởi:** Nhóm 13 (PBL Python) — *Dẫn đầu trải nghiệm tri thức số.*
 Cài đặt thư viện
pip install django

# 2. Khởi tạo Database
python manage.py makemigrations
python manage.py migrate

# 3. Seed dữ liệu thực tế (Hàng chục đầu sách từ Open Library)
python manage.py seed_books --limit 50

# 4. Tạo quản trị viên
python manage.py createsuperuser

# 5. Khởi chạy
python manage.py runserver
```

---

## 7. Thông tin nhóm thực hiện

- **Đề tài:** Website gợi ý sản phẩm thông minh (Smart Bookstore)
- **Môn học:** Lập trình Python
- **Nhóm:** 13
- **Tính năng đặc biệt:** Mock Payment, Draggable AI Chatbot, Reading DNA, Sentiment Analysis.

---
*Dự án hoàn thiện 100% các yêu cầu về nghiệp vụ và tích hợp công nghệ AI.*
