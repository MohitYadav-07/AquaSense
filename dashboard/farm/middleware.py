from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect

EXEMPT = ("/login/", "/admin/", "/static/", "/manifest.json", "/sw.js", "/offline/", "/lang/")


class LoginRequiredMiddleware:
    """Everything except the login page, PWA files and static assets needs a signed-in user."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not request.path.startswith(EXEMPT):
            return redirect("%s?next=%s" % (settings.LOGIN_URL, quote(request.get_full_path())))
        return self.get_response(request)
