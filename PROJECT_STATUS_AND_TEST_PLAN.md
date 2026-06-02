# Thống Kê Project Bookie Và Kế Hoạch Kiểm Thử Web

## 1. Phạm Vi Project

Bookie là website bán sách xây bằng Django. Source code chạy web nằm trong thư mục `Project/`.

Mục tiêu hiện tại là ổn định một web bán sách có thể demo/vận hành nhỏ: catalog sách, giỏ hàng, checkout, đơn hàng, ebook reader, hồ sơ người dùng, dashboard quản trị, phân quyền 5 role, chatbot hỗ trợ vừa đủ và dữ liệu mẫu có thể seed/import lại.

## 2. Stack Và Cách Chạy

- Backend: Django 6, Python 3.12.
- Database local mặc định: SQLite `Project/db.sqlite3`.
- Database Docker: PostgreSQL 16.
- Chatbot local: Ollama host, mặc định `qwen2.5:3b`.
- Docker compose dev: `web + db`, Django gọi Ollama qua `host.docker.internal`.

Chạy local:

```powershell
cd Project
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_fake_data --reset-demo
python manage.py runserver
```

Chạy Docker:

```powershell
cd Project
docker compose up --build
docker compose exec web python manage.py seed_fake_data --reset-demo
```

Copy sách từ SQLite local sang PostgreSQL Docker, bỏ trùng `title + author`:

```powershell
docker compose exec web python manage.py import_sqlite_books
```

## 3. Model Chính

- `Category`: thể loại sách.
- `Book`: catalog sách, giá, tồn kho, cover, ebook content.
- `ReadingProgress`: tiến độ đọc ebook theo user.
- `Wishlist`: sách yêu thích.
- `Coupon`: mã giảm giá.
- `Order`, `OrderItem`: đơn hàng và item.
- `Rating`: đánh giá sách.
- `AdminAuditLog`: log thao tác quản trị.
- Django `User`, `Group`, `Permission`: tài khoản và phân quyền.

## 4. Chức Năng Hiện Có

### Người Dùng

- Đăng ký, đăng nhập, đăng xuất.
- Hồ sơ cá nhân, chỉnh sửa họ tên/email.
- Đổi mật khẩu bằng form chuẩn Django.
- Catalog sách, tìm kiếm, lọc theo thể loại, xem chi tiết.
- Trang `Đọc sách online` tại `/ebooks/`, tách riêng ebook khỏi catalog sách giấy.
- Giỏ hàng, checkout, coupon, mock payment.
- Xem danh sách/chi tiết đơn hàng.
- Tải hóa đơn PDF, chỉ chủ đơn mới tải được.
- Wishlist.
- Rating/comment sách.
- Reading DNA.
- Lịch sử đọc sách trong menu tài khoản, hiển thị tiến độ và nút đọc tiếp.
- Ebook reader giao diện mới: đọc online miễn phí, đọc từng trang, progress, chuyển trang bằng nút/phím, tùy chỉnh theme/cỡ chữ/độ rộng, lưu tiến độ đọc khi đã đăng nhập.
- Giá sách trên catalog/chi tiết/giỏ hàng là giá sách giấy; đọc online không có giá E-book riêng.

### Quản Trị/Dashboard

- Dashboard tổng quan doanh thu, đơn hàng, user, sách.
- Quản lý users: xem danh sách, xem hồ sơ user, khóa/mở tài khoản, gán role.
- Quản lý sách: xem/thêm/sửa/xóa theo quyền.
- Quản lý coupon: xem/thêm/sửa/xóa theo quyền.
- Quản lý đơn hàng: xem/cập nhật trạng thái theo quyền.
- Audit log.
- Export CSV sách và đơn hàng.

### Chatbot

- Dùng Ollama local nhưng không là lõi chính của project.
- Ưu tiên tìm sách trong database trước khi gọi LLM.
- Nếu không có sách trong kho thì nói chưa tìm thấy, không bịa tên sách/giá.
- Streaming endpoint có fallback khi Ollama lỗi.
- Rate limit cho cả chatbot thường và streaming.
- Chatbot API dùng CSRF protection, frontend gửi `X-CSRFToken` khi gọi API.

## 5. Phân Quyền

Project hiện đã có phân quyền mức vận hành nhỏ/đồ án tốt, chưa phải enterprise hoàn chỉnh.

5 role hiện dùng:

- `Customer`: user thường, mua hàng, wishlist, rating, đọc ebook, xem đơn của mình.
- `Staff`: xem dữ liệu cơ bản như user/sách/coupon/đơn hàng.
- `Manager`: quản lý sách và xem một số dữ liệu vận hành.
- `Support`: xem đơn hàng và cập nhật trạng thái đơn.
- `Admin`: toàn quyền dashboard, user role, coupon, sách, đơn, audit log.

Đã có:

- Module `books/rbac.py` định nghĩa role/quyền tập trung.
- `seed_rbac` tạo group/permission, bỏ role cũ `Accountant`.
- Dashboard Users có dropdown gán role.
- Test tự động cho Customer, Manager, Support, Admin.

Chưa phải hoàn thiện tuyệt đối vì còn thiếu:

- Ma trận quyền hiển thị đẹp trong UI.
- Lịch sử thay đổi role chi tiết hơn.
- Chính sách mật khẩu/MFA nâng cao.
- Test browser/e2e cho toàn bộ dashboard theo role.

## 6. Dữ Liệu Mẫu

Command chính:

```powershell
python manage.py seed_fake_data --reset-demo
```

Tạo dữ liệu cho:

- Users: `demo`, `admin`, `alice`, `bob`, `staff`, `manager`, `support`.
- Groups/roles.
- Categories, books, ebooks.
- Coupons.
- Orders, order items.
- Ratings.
- Wishlist.
- Reading progress.
- Audit logs.

Tài khoản mẫu:

- `demo / demo123`
- `admin / admin123`
- `staff / staff123`
- `manager / manager123`
- `support / support123`
- `alice / alice123`
- `bob / bob123`

## 7. Test Tự Động

Lệnh chính:

```powershell
python Project\manage.py check
python Project\manage.py test books
```

Baseline hiện tại:

```text
45 tests OK
```

Đã test tự động:

- Trang chủ và chi tiết sách.
- Trang chi tiết sách có JSON-LD `Book` structured data.
- Trang `/ebooks/` chỉ hiển thị sách digital.
- Trang `/ebooks/` không hiển thị giá hoặc nút mua E-book.
- Navbar có link `Đọc sách online`.
- Reader ebook đọc full online miễn phí, chia nội dung dài thành nhiều trang, lưu tiến độ đọc khi đăng nhập.
- AJAX cart: thêm sách, giới hạn theo tồn kho, xóa item và cập nhật số lượng.
- AJAX wishlist: thêm/xóa yêu thích và cập nhật số lượng.
- Checkout chỉ dành cho sách giấy.
- Coupon hợp lệ/không hợp lệ.
- Dashboard URL reverse.
- Reading DNA context.
- Lịch sử đọc sách theo user.
- Hóa đơn PDF và quyền chủ đơn.
- Chatbot CSRF protection, rate limit, fallback, DB-first catalog search.
- `robots.txt` và `sitemap.xml` cho SEO cơ bản.
- Category normalization.
- Seed reader timeout.
- 5-role RBAC: Customer, Staff, Manager, Support, Admin.
- Admin xem hồ sơ user.
- User đổi mật khẩu.

Chưa test đủ:

- Responsive/mobile layout bằng browser thật.
- AJAX wishlist/cart bằng browser thật.
- VNPay sandbox với credential thật.
- UI dashboard theo từng role bằng e2e.
- Render PDF bằng kiểm tra hình ảnh.

## 8. Checklist Test Thủ Công

### Catalog Và Checkout

- Mở `/books/`, tìm kiếm, lọc category, sắp xếp.
- Mở chi tiết sách, thêm vào giỏ.
- Checkout với COD/Momo mock.
- Áp coupon `SAVE10`, `FREESHIP`, `VIP20`.
- Kiểm tra tồn kho sách giấy giảm sau checkout.

### Tài Khoản

- Đăng nhập `demo / demo123`.
- Mở `/profile/`.
- Chỉnh sửa hồ sơ.
- Đổi mật khẩu tại `/profile/password/`.
- Mở wishlist, orders, reading DNA.

### Ebook

- Mở `/ebooks/` từ Navbar `Đọc sách online`.
- Tìm kiếm/lọc sách đọc online theo thể loại.
- Mở sách đọc online, không thấy giá E-book hoặc nút mua E-book.
- Kiểm tra reader, chuyển trang bằng nút/phím mũi tên, mở panel tùy chỉnh, đổi theme/cỡ chữ/độ rộng, lưu tiến độ.

### Dashboard Và RBAC

- Đăng nhập `admin / admin123`.
- Mở `/dashboard/`.
- Vào Users, xem hồ sơ user, đổi role.
- Đăng nhập `manager / manager123`: kiểm tra quản lý sách, không quản lý user.
- Đăng nhập `support / support123`: kiểm tra xem/cập nhật đơn hàng.
- Đăng nhập `staff / staff123`: kiểm tra chỉ xem dữ liệu cơ bản.
- Đăng nhập customer: xác nhận không vào dashboard.

### Chatbot

- Hỏi `sách hay về python`: phải trả sách trong DB kèm giá.
- Hỏi chủ đề không có trong DB: phải nói chưa tìm thấy, không bịa.
- Tắt Ollama và kiểm tra fallback.
- Gửi nhiều request nhanh để kiểm tra rate limit.

## 9. Nhận Xét Chất Lượng Hiện Tại

Điểm tốt:

- Project đã ổn định hơn, có Docker dev, seed data, import SQLite sang PostgreSQL.
- Có GitHub Actions quality gate chạy `manage.py check` và `python manage.py test books` khi push/PR.
- RBAC 5 role đã có code, UI gán role và test.
- Chatbot đã giảm hallucination bằng DB-first search.
- Test tăng lên 45 case.
- Đã có SEO foundation: `robots.txt`, `sitemap.xml`, structured data cho trang sách.
- Chatbot API đã bỏ `csrf_exempt` và có test CSRF.
- Các thay đổi chính đều đi qua branch riêng, test rồi merge.

Rủi ro/cần cải thiện:

- `books/views.py` còn lớn, nên tách theo domain về lâu dài.
- Một số template/text vẫn còn không dấu hoặc chưa đồng nhất.
- Dashboard RBAC có đủ dùng nhưng chưa phải enterprise-grade.
- Cần e2e/browser test cho UX thật.

## 10. Việc Nên Làm Tiếp

1. Polish UI dashboard users/role bằng tiếng Việt có dấu và badge rõ hơn.
2. Thêm e2e/browser test cho cart, checkout, wishlist, dashboard role.
3. Tách `views.py` theo domain.
4. Kiểm thử VNPay sandbox khi có credential.
5. Thêm trang quản lý role/permission trực quan nếu muốn nâng cấp RBAC sâu hơn.
6. Bổ sung monitoring/logging lỗi production nếu deploy thật.
