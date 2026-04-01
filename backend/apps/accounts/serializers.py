from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=50)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6, max_length=128)
    fullName = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=50)
    password = serializers.CharField(max_length=128)
