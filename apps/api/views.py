from django.http import HttpRequest, JsonResponse


def health(request: HttpRequest) -> JsonResponse:
    """Basic health check endpoint returning {"status": "ok"}."""
    return JsonResponse({"status": "ok"})
