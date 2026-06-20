from .catalog import (
    home, book_list, ebook_list, book_detail, category_list, category_detail, 
    about, contact, robots_txt, rate_book, api_search
)
from .auth import register, BookieLoginView
from .cart import cart_view, add_to_cart, update_cart, remove_from_cart, api_apply_coupon
from .orders import (
    checkout, payment_gateway, vnpay_return, payment_confirm, order_list, 
    order_detail, order_invoice_pdf, cancel_order
)
from .wishlist import wishlist_view, wishlist_add, wishlist_remove
from .profile import profile, profile_edit, profile_change_password, reading_dna, reading_history
from .dashboard import (
    dashboard, dashboard_users, dashboard_user_detail, dashboard_user_set_role,
    dashboard_user_toggle_staff, dashboard_user_toggle_active, dashboard_books,
    dashboard_book_create, dashboard_book_edit, dashboard_book_delete,
    dashboard_coupons, dashboard_coupon_create, dashboard_coupon_edit,
    dashboard_coupon_delete, dashboard_orders, export_orders_csv,
    export_books_csv, api_update_order_status, dashboard_audit_logs
)
from .reader import (
    read_book, api_save_reading_progress, _sanitize_reader_html, _split_reader_pages,
    service_worker, manifest_json
)
from .chatbot import api_chatbot, api_chatbot_stream, _build_chatbot
from .api import api_books, api_book_detail, api_stats
