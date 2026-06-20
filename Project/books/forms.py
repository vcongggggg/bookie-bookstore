from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Book, Coupon, Rating

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}))

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Tên đăng nhập"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Mật khẩu"})
        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Xác nhận mật khẩu"})


class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ("score", "comment")
        widgets = {
            "score": forms.HiddenInput(attrs={"id": "rating-score-input"}),
            "comment": forms.Textarea(attrs={"rows": 3, "placeholder": "Chia sẻ cảm nhận của bạn về cuốn sách...", "class": "form-control"}),
        }


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Tên"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Họ"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}),
        }


class CheckoutForm(forms.Form):
    idempotency_key = forms.CharField(widget=forms.HiddenInput(), required=False)
    shipping_address = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Nhập địa chỉ giao hàng..."}),
        label="Địa chỉ giao hàng",
        required=True,
    )
    note = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Ghi chú cho đơn hàng (tùy chọn)..."}),
        label="Ghi chú",
        required=False,
    )
    coupon_code = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nhập mã giảm giá (nếu có)"}),
        label="Mã giảm giá",
        required=False,
    )
    PAYMENT_CHOICES = [
        ("cod", "Thanh toán khi nhận hàng (COD)"),
        ("vnpay", "Ví điện tử VNPay"),
        ("momo", "Ví điện tử Momo"),
    ]
    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Phương thức thanh toán",
        initial="cod"
    )


class BookAdminForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = (
            "title",
            "author",
            "description",
            "price",
            "category",
            "published_year",
            "num_pages",
            "cover_image",
            "stock",
            "is_digital",
            "content_text",
            "content_html",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "author": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "price": forms.NumberInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "published_year": forms.NumberInput(attrs={"class": "form-control"}),
            "num_pages": forms.NumberInput(attrs={"class": "form-control"}),
            "cover_image": forms.URLInput(attrs={"class": "form-control"}),
            "stock": forms.NumberInput(attrs={"class": "form-control"}),
            "is_digital": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "content_text": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "content_html": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }


class CouponAdminForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = (
            "code",
            "discount_type",
            "discount_value",
            "min_order_amount",
            "max_uses",
            "used_count",
            "active",
            "valid_from",
            "valid_to",
        )
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "discount_type": forms.Select(attrs={"class": "form-select"}),
            "discount_value": forms.NumberInput(attrs={"class": "form-control"}),
            "min_order_amount": forms.NumberInput(attrs={"class": "form-control"}),
            "max_uses": forms.NumberInput(attrs={"class": "form-control"}),
            "used_count": forms.NumberInput(attrs={"class": "form-control"}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "valid_from": forms.DateTimeInput(attrs={"class": "form-control"}),
            "valid_to": forms.DateTimeInput(attrs={"class": "form-control"}),
        }
