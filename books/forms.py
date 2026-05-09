from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Rating

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
