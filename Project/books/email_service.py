"""
Bookie Email Service
====================
Async email utilities for the Bookie bookstore application.
Uses Django's built-in email framework with threading for non-blocking sends.
"""

import logging
import threading
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)
User = get_user_model()


def _send_in_thread(email_message):
    """Send an EmailMessage in a background thread."""
    try:
        email_message.send(fail_silently=False)
        logger.info("Email sent to %s: %s", email_message.to, email_message.subject)
    except Exception:
        logger.exception("Failed to send email to %s: %s", email_message.to, email_message.subject)


def send_html_email(subject, template_name, context, recipient_list, attachments=None):
    """
    Render an HTML email template and send it asynchronously.

    Args:
        subject: Email subject line.
        template_name: Path to the HTML template (e.g. 'email/welcome.html').
        context: Template context dictionary.
        recipient_list: List of recipient email addresses.
        attachments: Optional list of (filename, content_bytes, mime_type) tuples.
    """
    # Filter out empty/None email addresses
    recipient_list = [email for email in recipient_list if email]
    if not recipient_list:
        logger.debug("No valid recipients for email '%s', skipping.", subject)
        return

    html_content = render_to_string(template_name, context)
    text_content = strip_tags(html_content)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    msg.attach_alternative(html_content, "text/html")

    if attachments:
        for filename, content, mime_type in attachments:
            msg.attach(filename, content, mime_type)

    # Send synchronously in tests to avoid race conditions and connection isolation issues
    if getattr(settings, "EMAIL_BACKEND", "") == "django.core.mail.backends.locmem.EmailBackend":
        _send_in_thread(msg)
    else:
        thread = threading.Thread(target=_send_in_thread, args=(msg,), daemon=True)
        thread.start()


# ─────────────────────────────────────────────────────────────────
# Business Email Functions
# ─────────────────────────────────────────────────────────────────


def send_welcome_email(user):
    """Send a welcome email after user registration."""
    if not user.email:
        return
    send_html_email(
        subject="Chào mừng bạn đến với Bookie! 📚",
        template_name="email/welcome.html",
        context={"user": user},
        recipient_list=[user.email],
    )


def send_order_confirmation_email(order):
    """Send order confirmation email with optional PDF invoice attachment."""
    user = order.user
    if not user.email:
        return

    items = list(order.items.select_related("book"))
    context = {
        "order": order,
        "items": items,
        "user": user,
    }

    # Generate PDF invoice as attachment
    attachments = []
    try:
        pdf_bytes = _generate_invoice_pdf(order, items)
        attachments.append((f"hoa-don-{order.pk}.pdf", pdf_bytes, "application/pdf"))
    except Exception:
        logger.exception("Failed to generate PDF invoice for order #%s", order.pk)

    send_html_email(
        subject=f"Xác nhận đơn hàng #{order.pk} — Bookie",
        template_name="email/order_confirmation.html",
        context=context,
        recipient_list=[user.email],
        attachments=attachments if attachments else None,
    )


def send_order_status_update_email(order, old_status):
    """Send email notifying the customer about an order status change."""
    user = order.user
    if not user.email:
        return

    status_labels = dict(order.STATUS_CHOICES)
    context = {
        "order": order,
        "user": user,
        "old_status": status_labels.get(old_status, old_status),
        "new_status": order.status_display_vi,
    }

    send_html_email(
        subject=f"Đơn hàng #{order.pk} — {order.status_display_vi}",
        template_name="email/order_status_update.html",
        context=context,
        recipient_list=[user.email],
    )


def send_low_stock_alert_email(books):
    """Send low stock alert to all staff/admin users."""
    if not books:
        return

    admin_emails = list(
        User.objects.filter(is_staff=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not admin_emails:
        return

    context = {"books": books, "threshold": settings.LOW_STOCK_THRESHOLD}

    send_html_email(
        subject=f"⚠️ Cảnh báo tồn kho thấp — {len(books)} sản phẩm",
        template_name="email/low_stock_alert.html",
        context=context,
        recipient_list=admin_emails,
    )


def _generate_invoice_pdf(order, items):
    """Generate a PDF invoice and return its bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Invoice #{order.pk}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("BOOKIE INVOICE", styles["Title"]),
        Paragraph(f"Invoice for order #{order.pk}", styles["Heading2"]),
        Spacer(1, 12),
        Paragraph(f"Customer: {order.user.username}", styles["Normal"]),
        Paragraph(f"Order date: {order.created_at.strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
        Paragraph(f"Status: {order.status_display_vi}", styles["Normal"]),
        Paragraph(f"Shipping address: {order.shipping_address or 'N/A'}", styles["Normal"]),
        Spacer(1, 16),
    ]

    rows = [["Book", "Qty", "Unit price", "Subtotal"]]
    for item in items:
        rows.append([
            item.book.title,
            str(item.quantity),
            f"{item.price:,.0f} VND",
            f"{item.subtotal:,.0f} VND",
        ])
    rows.extend([
        ["", "", "Subtotal", f"{order.subtotal:,.0f} VND"],
        ["", "", "Discount", f"-{order.discount_amount:,.0f} VND"],
        ["", "", "Total", f"{order.total:,.0f} VND"],
    ])

    table = Table(rows, colWidths=[230, 50, 100, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()
