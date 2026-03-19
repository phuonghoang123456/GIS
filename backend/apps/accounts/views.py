from django.db import IntegrityError
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.activity.models import ActivityLog
from apps.common.auth import generate_token
from apps.common.responses import fail, ok

from .models import User
from .serializers import LoginSerializer, RegisterSerializer


def _user_payload(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "fullName": user.full_name,
        "role": user.role,
    }


class RegisterView(APIView):
    permission_classes = []
    authentication_classes: list[type[BaseAuthentication]] = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return fail("Missing or invalid required fields", 400, "validation_error", serializer.errors)

        payload = serializer.validated_data
        if User.objects.filter(username=payload["username"]).exists():
            return fail("Username already exists", 409, "username_exists")

        if User.objects.filter(email=payload["email"]).exists():
            return fail("Email already exists", 409, "email_exists")

        user = User(
            username=payload["username"],
            email=payload["email"],
            full_name=payload.get("fullName") or None,
            role="user",
            is_active=True,
            created_at=timezone.now(),
        )
        user.set_password(payload["password"])
        try:
            user.save()
        except IntegrityError:
            return fail("Username or email already exists", 409, "conflict")

        token = generate_token(user)
        try:
            ActivityLog.create(
                user_id=user.id,
                activity_type="register",
                page="auth",
                details={"username": user.username},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception:
            # Do not block auth flow if logging fails.
            pass

        return ok({"message": "User registered successfully", "token": token, "user": _user_payload(user)}, 201)


class LoginView(APIView):
    permission_classes = []
    authentication_classes: list[type[BaseAuthentication]] = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return fail("Username and password required", 400, "validation_error", serializer.errors)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        user = User.objects.filter(username=username, is_active=True).first()
        if not user or not user.check_password(password):
            return fail("Invalid credentials", 401, "invalid_credentials")

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        token = generate_token(user)

        try:
            ActivityLog.create(
                user_id=user.id,
                activity_type="login",
                page="auth",
                details={"username": user.username},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception:
            pass

        return ok({"message": "Login successful", "token": token, "user": _user_payload(user)})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            ActivityLog.create(
                user_id=request.user.id,
                activity_type="logout",
                page="auth",
                details={"username": request.user.username},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception:
            pass
        return ok({"message": "Logout successful"})


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return ok(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "fullName": user.full_name,
                    "role": user.role,
                    "createdAt": user.created_at,
                    "lastLogin": user.last_login,
                }
            }
        )
