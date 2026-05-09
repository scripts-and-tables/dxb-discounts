from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from apps.discounts.models import Discount

from .emails import EmailDeliveryFailed, send_code_email
from .forms import CodeForm, LoginForm, PasswordResetForm, SignupForm
from .models import CodeRateLimitExceeded, EmailCode, EmailCodePurpose, Favorite


EMAIL_FAILURE_MESSAGE = (
    "We couldn't send the email right now. Please try again in a moment."
)
RATE_LIMIT_MESSAGE = "Too many code requests. Try again in an hour."


User = get_user_model()

PENDING_KEY = "accounts:pending"
MAX_CODE_ATTEMPTS = 5


# ------------- Signup -------------

@never_cache
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            password=form.cleaned_data["password"],
            is_active=False,
        )
        try:
            code = EmailCode.issue(user, EmailCodePurpose.SIGNUP)
            send_code_email(to_email=email, code=code.code, purpose="signup")
        except CodeRateLimitExceeded:
            user.delete()
            messages.error(request, RATE_LIMIT_MESSAGE)
            return render(request, "accounts/signup.html", {"form": form})
        except EmailDeliveryFailed:
            user.delete()
            messages.error(request, EMAIL_FAILURE_MESSAGE)
            return render(request, "accounts/signup.html", {"form": form})
        request.session[PENDING_KEY] = {"user_id": user.pk, "purpose": EmailCodePurpose.SIGNUP}
        return redirect("accounts:signup_verify")
    return render(request, "accounts/signup.html", {"form": form})


@never_cache
@require_http_methods(["GET", "POST"])
def signup_verify(request):
    pending = request.session.get(PENDING_KEY)
    if not pending or pending.get("purpose") != EmailCodePurpose.SIGNUP:
        return redirect("accounts:signup")
    user = User.objects.filter(pk=pending["user_id"], is_active=False).first()
    if not user:
        request.session.pop(PENDING_KEY, None)
        return redirect("accounts:signup")

    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ok, msg = _consume_code(user, EmailCodePurpose.SIGNUP, form.cleaned_data["code"])
        if ok:
            user.is_active = True
            user.save(update_fields=["is_active"])
            request.session.pop(PENDING_KEY, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Email verified. Welcome!")
            return redirect("accounts:profile")
        form.add_error("code", msg)

    return render(request, "accounts/verify.html", {
        "form": form,
        "email": user.email,
        "purpose": "signup",
        "resend_url": reverse("accounts:signup_resend"),
    })


@require_POST
@ratelimit(key="user_or_ip", rate="3/h", block=True)
def signup_resend(request):
    pending = request.session.get(PENDING_KEY)
    if not pending or pending.get("purpose") != EmailCodePurpose.SIGNUP:
        return redirect("accounts:signup")
    user = User.objects.filter(pk=pending["user_id"], is_active=False).first()
    if user:
        status = "ok"
        try:
            code = EmailCode.issue(user, EmailCodePurpose.SIGNUP)
            send_code_email(to_email=user.email, code=code.code, purpose="signup")
        except CodeRateLimitExceeded:
            status = "rate_limited"
        except EmailDeliveryFailed:
            status = "delivery_failed"
        if status == "ok":
            messages.success(request, "We sent a new code.")
        elif status == "rate_limited":
            messages.error(request, RATE_LIMIT_MESSAGE)
        else:
            messages.error(request, EMAIL_FAILURE_MESSAGE)
    return redirect("accounts:signup_verify")


# ------------- Login -------------

@never_cache
@require_http_methods(["GET", "POST"])
@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.cleaned_data["user"]
        try:
            code = EmailCode.issue(user, EmailCodePurpose.LOGIN)
            send_code_email(to_email=user.email, code=code.code, purpose="login")
        except CodeRateLimitExceeded:
            messages.error(request, RATE_LIMIT_MESSAGE)
            return render(request, "accounts/login.html", {
                "form": form,
                "next": request.GET.get("next", ""),
            })
        except EmailDeliveryFailed:
            messages.error(request, EMAIL_FAILURE_MESSAGE)
            return render(request, "accounts/login.html", {
                "form": form,
                "next": request.GET.get("next", ""),
            })
        request.session[PENDING_KEY] = {
            "user_id": user.pk,
            "purpose": EmailCodePurpose.LOGIN,
            "next": request.GET.get("next") or request.POST.get("next") or "",
        }
        return redirect("accounts:login_verify")
    return render(request, "accounts/login.html", {
        "form": form,
        "next": request.GET.get("next", ""),
    })


@never_cache
@require_http_methods(["GET", "POST"])
def login_verify(request):
    pending = request.session.get(PENDING_KEY)
    if not pending or pending.get("purpose") != EmailCodePurpose.LOGIN:
        return redirect("accounts:login")
    user = User.objects.filter(pk=pending["user_id"], is_active=True).first()
    if not user:
        request.session.pop(PENDING_KEY, None)
        return redirect("accounts:login")

    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ok, msg = _consume_code(user, EmailCodePurpose.LOGIN, form.cleaned_data["code"])
        if ok:
            next_url = pending.get("next") or reverse("accounts:profile")
            request.session.pop(PENDING_KEY, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return HttpResponseRedirect(next_url)
        form.add_error("code", msg)

    return render(request, "accounts/verify.html", {
        "form": form,
        "email": user.email,
        "purpose": "login",
        "resend_url": reverse("accounts:login_resend"),
    })


@require_POST
@ratelimit(key="user_or_ip", rate="3/h", block=True)
def login_resend(request):
    pending = request.session.get(PENDING_KEY)
    if not pending or pending.get("purpose") != EmailCodePurpose.LOGIN:
        return redirect("accounts:login")
    user = User.objects.filter(pk=pending["user_id"], is_active=True).first()
    if user:
        status = "ok"
        try:
            code = EmailCode.issue(user, EmailCodePurpose.LOGIN)
            send_code_email(to_email=user.email, code=code.code, purpose="login")
        except CodeRateLimitExceeded:
            status = "rate_limited"
        except EmailDeliveryFailed:
            status = "delivery_failed"
        if status == "ok":
            messages.success(request, "We sent a new code.")
        elif status == "rate_limited":
            messages.error(request, RATE_LIMIT_MESSAGE)
        else:
            messages.error(request, EMAIL_FAILURE_MESSAGE)
    return redirect("accounts:login_verify")


# ------------- Logout -------------

@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Signed out.")
    return redirect("pages:home")


# ------------- Profile -------------

@login_required
@require_GET
def profile(request):
    favorites = list(
        Favorite.objects
        .filter(user=request.user)
        .select_related("discount__place")
        .order_by("-created_at")
    )
    # Mark each favorited discount so the heart renders as filled in the card.
    for f in favorites:
        f.discount.is_favorited = True
    return render(request, "accounts/profile.html", {
        "favorites": favorites,
    })


# ------------- Favorite toggle -------------

@require_POST
def favorite_toggle(request, slug: str):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.META.get('HTTP_REFERER', '/')}")

    discount = get_object_or_404(Discount, slug=slug, is_active=True, place__is_published=True)
    fav, created = Favorite.objects.get_or_create(user=request.user, discount=discount)
    if not created:
        fav.delete()
        favorited = False
    else:
        favorited = True

    if request.headers.get("HX-Request"):
        return render(request, "accounts/_favorite_button.html", {
            "discount": discount,
            "favorited": favorited,
        })
    return redirect(discount.get_absolute_url())


# ------------- Gem toggle (admin-only) -------------

@require_POST
def gem_toggle(request, slug: str):
    if not request.user.is_staff:
        return HttpResponseForbidden()

    discount = get_object_or_404(Discount, slug=slug, is_active=True, place__is_published=True)
    discount.is_gem = not discount.is_gem
    discount.save(update_fields=["is_gem", "updated_at"])

    if request.headers.get("HX-Request"):
        return render(request, "accounts/_gem_button.html", {"discount": discount})
    return redirect(discount.get_absolute_url())


# ------------- Password reset (rate-limited) -------------

@method_decorator(
    ratelimit(key="ip", rate="5/h", method="POST", block=True),
    name="post",
)
class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    form_class = PasswordResetForm

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except EmailDeliveryFailed:
            messages.error(self.request, EMAIL_FAILURE_MESSAGE)
            return self.form_invalid(form)


# ------------- Helpers -------------

def _consume_code(user, purpose: str, raw_code: str) -> tuple[bool, str]:
    code_obj = EmailCode.objects.valid().filter(user=user, purpose=purpose).order_by("-created_at").first()
    if not code_obj:
        return False, "That code has expired. Request a new one."
    if code_obj.attempts >= MAX_CODE_ATTEMPTS:
        return False, "Too many attempts. Request a new code."
    code_obj.attempts += 1
    code_obj.save(update_fields=["attempts"])
    if code_obj.code != raw_code:
        return False, "Incorrect code."
    code_obj.mark_used()
    return True, ""
