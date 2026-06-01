# Thống Kê Project Bookie Và Kế Hoạch Kiểm Thử Web

## 1. Phạm Vi Project

Bookie là website bán sách xây bằng Django. Toàn bộ mã nguồn đang dùng để chạy web nằm trong thư mục `Project/`.

Mục tiêu chính của project là tạo một trải nghiệm nhà sách trực tuyến dùng được trong thực tế: duyệt sách, xem chi tiết, giỏ hàng, thanh toán, đơn hàng, hồ sơ người dùng, dashboard quản trị, chatbot hỗ trợ vừa đủ, và đọc sách số nếu sách có nội dung ebook.

Cấu trúc mã nguồn hiện tại:

- `Project/books/`: app chính, gồm models, views, URLs, forms, chatbot, tests và seed commands.
- `Project/bookstore/`: cấu hình Django và root URL config.
- `Project/templates/`: giao diện HTML.
- `Project/static/`: CSS, JavaScript và hình ảnh.
- `Project/.env.example`: file mẫu cấu hình môi trường an toàn.
- `Project/requirements.txt`: danh sách thư viện Python.

## 2. Các Model Dữ Liệu Chính

- `Category`: thể loại sách.
- `Book`: sách trong catalog, gồm giá, tồn kho, ảnh bìa, thông tin ebook.
- `ReadingProgress`: tiến độ đọc ebook theo từng người dùng.
- `Wishlist`: danh sách sách yêu thích của người dùng.
- `Coupon`: mã giảm giá, điều kiện áp dụng và giới hạn lượt dùng.
- `Order`: đơn hàng, trạng thái đơn hàng và phương thức thanh toán.
- `OrderItem`: từng sách trong đơn hàng, có đánh dấu mua bản digital hay không.
- `Rating`: đánh giá và bình luận của người dùng.
- `AdminAuditLog`: nhật ký thao tác của staff/admin.

## 3. Chức Năng Hiện Có

### Chức Năng Cho Người Dùng

- Trang chủ với các khu vực sách nổi bật, phổ biến và gợi ý.
- Danh sách sách có tìm kiếm, lọc theo thể loại và sắp xếp.
- Trang chi tiết sách: mô tả, tồn kho, giá, đánh giá, sách liên quan, thêm giỏ hàng/yêu thích.
- Danh sách thể loại và trang chi tiết thể loại.
- Đăng ký, đăng nhập, đăng xuất.
- Giỏ hàng: thêm, cập nhật số lượng, xóa sản phẩm.
- Checkout với địa chỉ giao hàng, ghi chú, mã giảm giá và phương thức thanh toán.
- Danh sách đơn hàng và chi tiết đơn hàng.
- Hủy đơn khi đơn còn ở trạng thái chờ/xác nhận.
- Tải hóa đơn PDF cho đơn hàng thuộc tài khoản đang đăng nhập.
- Wishlist và thao tác thêm/xóa yêu thích bằng AJAX.
- Hồ sơ người dùng và chỉnh sửa thông tin cá nhân.
- Reading DNA: thống kê thói quen đọc, biểu đồ, thành tựu và gợi ý.
- Trình đọc ebook: preview/full access và lưu tiến độ đọc.
- Trang giới thiệu và liên hệ.

### Chức Năng Thương Mại Và Quản Trị

- API kiểm tra mã giảm giá.
- Mock payment confirmation.
- Đường dẫn callback/return cho VNPay và module helper VNPay.
- Dashboard admin tổng quan: doanh thu, đơn hàng, người dùng, sách, biểu đồ/danh sách.
- Trang dashboard cho staff: quản lý người dùng, sách, coupon, đơn hàng, audit log.
- Xuất CSV sách và đơn hàng.
- API cập nhật trạng thái đơn hàng cho staff có quyền.
- Seed command tạo nhóm quyền RBAC mặc định.

### Chức Năng AI/Chatbot

Chatbot được định hướng là tính năng hỗ trợ vừa đủ, không phải lõi chính của project.

- Endpoint chatbot dùng Ollama.
- Endpoint chatbot streaming.
- Tìm sách trong database trước khi gọi model để giảm việc bịa nội dung.
- Hỗ trợ một số tác vụ như tra cứu đơn hàng/gợi ý sách.
- Rate limit cho cả chatbot thường và chatbot streaming.
- Có fallback khi model lỗi hoặc không kết nối được.

## 4. Cách Cài Đặt Và Chạy Project

Từ thư mục gốc repository:

```powershell
cd Project
copy .env.example .env
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_books --limit 50
python manage.py seed_demo_user
python manage.py seed_rbac
python manage.py runserver
```

Tài khoản demo hữu ích:

- Username: `demo`
- Password: `demo123`

Seed thêm sách digital nếu cần test reader:

```powershell
python manage.py seed_reader_content
```

Nếu muốn chạy lệnh từ root repo:

```powershell
python Project\manage.py check
python Project\manage.py test books
python Project\manage.py runserver
```

## 5. Trạng Thái Test Tự Động

Lệnh test chính:

```powershell
python Project\manage.py test books
```

Baseline hiện tại: `15 tests OK`.

Lệnh coverage:

```powershell
coverage run Project\manage.py test books
coverage report --fail-under=35
```

Coverage gần nhất: khoảng `48%`, vượt ngưỡng CI hiện tại là `35%`.

Các phần đã có test tự động:

- Trang chủ load thành công.
- Trang chi tiết sách load thành công.
- Reader mở được với sách digital miễn phí.
- API lưu tiến độ đọc lưu đúng trang và trạng thái hoàn thành.
- Sách không phải digital bị redirect khỏi reader.
- Sách digital trả phí hiển thị preview trước khi mua và full access sau khi mua digital.
- Checkout digital đánh dấu `OrderItem.is_digital_purchase` và không trừ tồn kho.
- Checkout sách giấy trừ tồn kho đúng theo số lượng.
- Coupon hợp lệ giảm tổng tiền và tăng số lượt dùng.
- Coupon không hợp lệ không chặn checkout và không giảm tiền.
- Các route dashboard reverse được.
- Reading DNA cấp đủ dữ liệu biểu đồ và insight.
- Trang chi tiết đơn hàng có link tải hóa đơn PDF.
- Tải hóa đơn PDF yêu cầu đúng chủ đơn hàng và trả response PDF hợp lệ.
- Chatbot thường bị rate limit khi gửi quá nhanh.
- Chatbot streaming dùng chung rate limit.

Các phần chưa được test tự động đầy đủ:

- Render UI trên browser thật và responsive/mobile layout.
- DOM update của AJAX wishlist/cart.
- Coupon hết hạn, coupon vượt max uses, coupon dưới min order.
- Ma trận quyền staff/admin cho mọi thao tác dashboard.
- Luồng VNPay checksum thành công/thất bại.
- Tích hợp Ollama thật.
- Chất lượng trình bày trực quan của file PDF.

## 6. Checklist Test Thủ Công Trên Web

Dùng checklist này sau khi chạy server tại `http://127.0.0.1:8000/`.

### Kiểm Tra Điều Hướng Cơ Bản

- Mở `/`.
- Kiểm tra header/nav hiển thị không vỡ layout.
- Click `Books`, `Categories`, `About`, `Contact`.
- Tìm kiếm từ header và xác nhận có gợi ý/kết quả.
- Thu nhỏ trình duyệt về kích thước mobile và kiểm tra nav/chatbot không che nội dung chính.

### Catalog Và Chi Tiết Sách

- Mở `/books/`.
- Tìm kiếm theo tên sách và tác giả.
- Lọc theo thể loại.
- Thử các tùy chọn sắp xếp.
- Mở một trang chi tiết sách.
- Kiểm tra ảnh bìa/placeholder, giá, tồn kho, khu vực đánh giá, sách liên quan và các nút CTA.
- Nếu có sách hết hàng, thử thêm vào giỏ và xác nhận bị chặn hoặc nút bị disable.

### Giỏ Hàng Và Checkout

- Thêm sách giấy vào giỏ.
- Cập nhật số lượng tại `/cart/`.
- Xóa sản phẩm khỏi giỏ.
- Thêm sách digital vào giỏ và xác nhận số lượng luôn là `1`.
- Checkout khi đã đăng nhập.
- Nhập địa chỉ giao hàng và chọn COD.
- Xác nhận đơn hàng được tạo và giỏ hàng được xóa.
- Xác nhận checkout sách giấy làm giảm tồn kho.
- Xác nhận checkout sách digital không làm giảm tồn kho.

### Coupon

- Tạo coupon trong dashboard/admin hoặc Django admin.
- Áp dụng coupon hợp lệ khi checkout.
- Nhập coupon sai và xác nhận thông báo thân thiện.
- Thử coupon chưa đủ giá trị đơn tối thiểu nếu có cấu hình.
- Xác nhận tổng tiền đơn hàng phản ánh đúng giảm giá.

### Đơn Hàng Và Hóa Đơn

- Mở `/orders/`.
- Mở một trang chi tiết đơn hàng.
- Kiểm tra timeline trạng thái, danh sách sản phẩm, địa chỉ và tổng tiền.
- Tải hóa đơn PDF.
- Xác nhận browser tải/mở được file PDF.
- Thử truy cập URL hóa đơn của user khác và xác nhận bị từ chối.
- Hủy đơn đang chờ/xác nhận và xác nhận tồn kho sách giấy được hoàn lại.

### Thanh Toán

- Checkout với Momo mock.
- Kiểm tra trang payment hiển thị QR/hướng dẫn mock.
- Click xác nhận thanh toán và kiểm tra trạng thái đơn thành confirmed.
- Checkout với VNPay sandbox chỉ khi đã cấu hình env vars.
- Test callback VNPay thành công/thất bại riêng khi có credential sandbox hợp lệ.

### Wishlist

- Thêm sách vào wishlist từ trang list/detail nếu có nút.
- Xác nhận badge/count wishlist thay đổi.
- Mở `/wishlist/`.
- Xóa sách khỏi wishlist và xác nhận item biến mất.
- Thử thao tác wishlist khi chưa đăng nhập và xác nhận yêu cầu đăng nhập/redirect phù hợp.

### Rating Và Sentiment

- Mở sách có thể đánh giá.
- Gửi rating 1-5 sao và bình luận.
- Xác nhận rating hiển thị ở trang chi tiết sách.
- Xác nhận khu vực sentiment summary không làm vỡ layout.

### Profile Và Reading DNA

- Mở `/profile/`.
- Chỉnh sửa họ, tên, email.
- Mở `/profile/reading-dna/`.
- Xác nhận các stat card hiển thị.
- Xác nhận radar chart và trend chart hiển thị.
- Xác nhận milestones/recommendations hiển thị khi user có đủ dữ liệu.
- Với user mới chưa có đơn/đánh giá, xác nhận empty-state hiển thị đúng.

### Digital Reader

- Mở chi tiết một sách digital.
- Click nút đọc sách.
- Với sách digital miễn phí, xác nhận mở được full content.
- Với sách digital trả phí chưa mua, xác nhận chỉ xem preview.
- Mua bản digital và xác nhận mở được full reader.
- Dùng nút next/previous page.
- Refresh reader và xác nhận tiến độ đọc được khôi phục.
- Kiểm tra slider cỡ chữ và nút theme.
- Kiểm tra nút "Ask AI" không làm vỡ reader.

### Chatbot

- Mở chatbot bubble.
- Hỏi gợi ý chung, ví dụ: `goi y sach lap trinh`.
- Xác nhận câu trả lời thân thiện và không bịa quá đà.
- Hỏi trạng thái đơn hàng khi chưa đăng nhập và khi đã đăng nhập.
- Tắt Ollama hoặc để Ollama unavailable và xác nhận có fallback message.
- Gửi nhiều request nhanh và xác nhận rate limit xuất hiện.
- Kiểm tra chatbot không che các nút quan trọng trên mobile.

### Admin Dashboard

- Tạo staff/admin hoặc gán nhóm quyền bằng `seed_rbac`.
- Mở `/dashboard/`.
- Xác nhận chỉ staff mới truy cập được.
- Kiểm tra số liệu và biểu đồ dashboard.
- Mở các trang users, books, coupons, orders, audit.
- Test thêm/sửa/xóa sách với quyền phù hợp.
- Test thêm/sửa/xóa coupon với quyền phù hợp.
- Test cập nhật trạng thái đơn hàng.
- Export orders CSV.
- Export books CSV.
- Xác nhận audit log được ghi khi thao tác admin.

## 7. Nhận Xét UX/UI

Điểm mạnh hiện tại:

- Có nhận diện visual rõ với phong cách Midnight Cosmic.
- Flow chính khá dễ hiểu: catalog, detail, cart, checkout, orders.
- Dashboard đã bao phủ các nghiệp vụ quản trị chính.
- Reader mode đã có và có test bảo vệ.
- Chatbot có mặt như trợ lý phụ, không lấn át web bán sách.

Điểm cần cải thiện:

- Nhiều template còn dùng inline style, khó duy trì đồng bộ UI.
- Một số text tiếng Việt ở dashboard/admin chưa có dấu đầy đủ.
- Frontend chatbot có render một ít HTML từ text, cần harden để tránh pattern không an toàn.
- Một số flow AJAX cần test ở browser thật, không chỉ test Django.
- Thanh toán sandbox cần test với credential thật trước khi demo.
- Hóa đơn PDF đã dùng được nhưng còn đơn giản về mặt trình bày.

## 8. Nhận Xét Code Quality

Điểm tốt hiện tại:

- `.env` đã được ignore; `.env.example` đã commit.
- Cây Django trùng ở root đã được xóa; `Project/` là source of truth.
- Test database tự dùng SQLite khi chạy test.
- `python Project\manage.py check` pass.
- Đã có GitHub Actions chạy check/test/coverage.
- Các thay đổi gần đây đều đi theo branch riêng, có test rồi mới merge.

Sạn/rủi ro còn lại:

- `Project/books/views.py` đang rất lớn, về lâu dài nên tách theo domain.
- Hàm legacy `api_chatbot_sync_unused` vẫn còn và nên xóa trong cleanup commit.
- Một số endpoint đang dùng `csrf_exempt`; cần review xem có thể bỏ không.
- Nhiều `except Exception` còn bắt rộng, nên thu hẹp dần.
- Test permission dashboard cần mở rộng.

## 9. Việc Nên Làm Tiếp

Chưa nên thêm feature lớn nếu các phần dưới đây chưa ổn hơn:

1. Mở rộng test cho permission dashboard và admin actions.
2. Xóa dead code chatbot fallback.
3. Harden frontend chatbot rendering.
4. Review và bỏ `csrf_exempt` không cần thiết.
5. Polish các template quan trọng cho mobile layout và text tiếng Việt.
6. Chạy manual browser pass theo checklist ở trên.
7. Nếu có thời gian, thêm browser/e2e test cho cart, checkout, wishlist.

