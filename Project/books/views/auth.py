from .helpers import *
from .helpers import _client_actor, _rate_limit_response

def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        limited = _rate_limit_response(
            request,
            "register",
            settings.REGISTER_RATE_LIMIT_REQUESTS,
            settings.REGISTER_RATE_LIMIT_WINDOW,
            "Bạn đăng ký quá nhanh. Vui lòng chờ một lúc rồi thử lại.",
        )
        if limited:
            return limited

        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            try:
                from ..tasks import send_welcome_email_task
                send_welcome_email_task(user.pk)
            except Exception:
                pass  # We don't block the user signup flow if email fails to trigger
            messages.success(request, "Đăng ký thành công! Chào mừng bạn đến Smart Bookstore.")
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


class BookieLoginView(LoginView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        
        # Check lockout based on IP
        ip_actor = _client_actor(request)
        ip_lockout_key = f"login_lockout:{ip_actor}"
        if cache.get(ip_lockout_key):
            from django.contrib.auth.forms import AuthenticationForm
            form = AuthenticationForm(request)
            form.cleaned_data = {}
            form.add_error(None, "Tài khoản hoặc thiết bị của bạn tạm thời bị khóa do đăng nhập sai nhiều lần. Vui lòng thử lại sau 15 phút.")
            return render(request, self.template_name or "registration/login.html", {"form": form})
            
        # Check lockout based on username
        if request.method == "POST":
            username = request.POST.get("username", "").strip()
            if username:
                user_lockout_key = f"login_lockout:username:{username.lower()}"
                if cache.get(user_lockout_key):
                    from django.contrib.auth.forms import AuthenticationForm
                    form = AuthenticationForm(request, data=request.POST)
                    form.cleaned_data = {}
                    form.add_error(None, "Tài khoản hoặc thiết bị của bạn tạm thời bị khóa do đăng nhập sai nhiều lần. Vui lòng thử lại sau 15 phút.")
                    return render(request, self.template_name or "registration/login.html", {"form": form})

        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        request = self.request
        ip_actor = _client_actor(request)
        username = request.POST.get("username", "").strip()

        # Increment IP failures
        ip_fail_key = f"login_failed_count:{ip_actor}"
        try:
            ip_fails = int(cache.get(ip_fail_key, 0))
        except (ValueError, TypeError):
            ip_fails = 0
        ip_fails += 1
        cache.set(ip_fail_key, ip_fails, timeout=settings.LOGIN_RATE_LIMIT_LOCKOUT_WINDOW)
        if ip_fails >= settings.LOGIN_RATE_LIMIT_FAILED_ATTEMPTS:
            cache.set(f"login_lockout:{ip_actor}", True, timeout=settings.LOGIN_RATE_LIMIT_LOCKOUT_WINDOW)

        # Increment Username failures
        if username:
            user_fail_key = f"login_failed_count:username:{username.lower()}"
            try:
                user_fails = int(cache.get(user_fail_key, 0))
            except (ValueError, TypeError):
                user_fails = 0
            user_fails += 1
            cache.set(user_fail_key, user_fails, timeout=settings.LOGIN_RATE_LIMIT_LOCKOUT_WINDOW)
            if user_fails >= settings.LOGIN_RATE_LIMIT_FAILED_ATTEMPTS:
                cache.set(f"login_lockout:username:{username.lower()}", True, timeout=settings.LOGIN_RATE_LIMIT_LOCKOUT_WINDOW)

        return super().form_invalid(form)

    def form_valid(self, form):
        # Clear failures on successful login
        request = self.request
        ip_actor = _client_actor(request)
        username = request.POST.get("username", "").strip()

        cache.delete(f"login_failed_count:{ip_actor}")
        cache.delete(f"login_lockout:{ip_actor}")
        if username:
            cache.delete(f"login_failed_count:username:{username.lower()}")
            cache.delete(f"login_lockout:username:{username.lower()}")

        return super().form_valid(form)



