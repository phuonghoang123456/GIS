from rest_framework.response import Response


def ok(data, status_code=200):
    return Response({"success": True, "data": data}, status=status_code)


def fail(message: str, status_code=400, code: str | None = None, details=None):
    return Response(
        {
            "success": False,
            "error": {
                "code": code or "bad_request",
                "message": message,
                "details": details or {},
            },
        },
        status=status_code,
    )
