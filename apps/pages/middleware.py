from django.http import HttpResponse


class HealthCheckMiddleware:
    """Short-circuit /healthz/ before any host validation.

    Railway's internal healthcheck uses an undocumented Host header that
    isn't easily added to ALLOWED_HOSTS, so returning the response from
    middleware (before request.get_host() is ever called) lets deploys
    pass healthcheck without weakening ALLOWED_HOSTS to '*'.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ("/healthz", "/healthz/"):
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)
