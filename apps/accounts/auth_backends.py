from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Authenticate by email instead of username.

    Signup stores ``username == email`` so the default ModelBackend works for
    those accounts. Superusers created via ``manage.py createsuperuser`` keep
    a separate username (e.g. ``admin``), which would otherwise be unable to
    log in via the email-based login form.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        UserModel = get_user_model()
        users = list(UserModel.objects.filter(email__iexact=username.strip()))
        if len(users) != 1:
            UserModel().set_password(password)  # equalize timing on miss/dupe
            return None
        user = users[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
