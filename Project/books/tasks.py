import logging
from huey.contrib.djhuey import db_task

logger = logging.getLogger(__name__)

@db_task()
def send_welcome_email_task(user_id):
    from django.contrib.auth import get_user_model
    from books.email_service import send_welcome_email
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        send_welcome_email(user)
    except User.DoesNotExist:
        logger.error("User with ID %s does not exist", user_id)

@db_task()
def send_order_confirmation_email_task(order_id):
    from books.models import Order
    from books.email_service import send_order_confirmation_email
    try:
        order = Order.objects.select_related("user").get(pk=order_id)
        send_order_confirmation_email(order)
    except Order.DoesNotExist:
        logger.error("Order with ID %s does not exist", order_id)

@db_task()
def send_order_status_update_email_task(order_id, old_status):
    from books.models import Order
    from books.email_service import send_order_status_update_email
    try:
        order = Order.objects.select_related("user").get(pk=order_id)
        send_order_status_update_email(order, old_status)
    except Order.DoesNotExist:
        logger.error("Order with ID %s does not exist", order_id)

@db_task()
def send_low_stock_alert_email_task(book_ids):
    from books.models import Book
    from books.email_service import send_low_stock_alert_email
    books = list(Book.objects.filter(pk__in=book_ids))
    send_low_stock_alert_email(books)
