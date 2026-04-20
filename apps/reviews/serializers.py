"""Serializers de avaliacoes."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.reviews.models import Review


def mask_client_name(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "Cliente"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


class ReviewByTokenReadSerializer(serializers.ModelSerializer[Review]):
    provider_name = serializers.CharField(source="provider.business_name", read_only=True)
    service_name = serializers.CharField(source="appointment.service.name", read_only=True)
    start_datetime = serializers.DateTimeField(source="appointment.start_datetime", read_only=True)

    class Meta:
        model = Review
        fields = ["provider_name", "service_name", "start_datetime", "client_name"]


class ReviewByTokenSubmitSerializer(serializers.Serializer[dict[str, object]]):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")


class ProviderReviewSerializer(serializers.ModelSerializer[Review]):
    class Meta:
        model = Review
        fields = [
            "id",
            "rating",
            "comment",
            "client_name",
            "created_at",
            "is_public",
            "provider_reply",
            "replied_at",
        ]


class ProviderReviewReplySerializer(serializers.Serializer[dict[str, object]]):
    reply = serializers.CharField(max_length=2000)


class PublicReviewSerializer(serializers.ModelSerializer[Review]):
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "rating", "comment", "client_name", "created_at", "provider_reply", "replied_at"]

    def get_client_name(self, obj: Review) -> str:
        return mask_client_name(obj.client_name)


class MyAppointmentReviewStatusSerializer(serializers.ModelSerializer[Review]):
    review_status = serializers.SerializerMethodField()
    review_token = serializers.SerializerMethodField()
    review_rating = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["review_status", "review_token", "review_rating"]

    def get_review_status(self, obj: Review) -> str | None:
        if obj.rating is not None:
            return "completed"
        if obj.token_expires_at >= timezone.now():
            return "pending"
        return None

    def get_review_token(self, obj: Review) -> str | None:
        if obj.rating is None and obj.token_expires_at >= timezone.now():
            return obj.review_token
        return None

    def get_review_rating(self, obj: Review) -> int | None:
        return obj.rating
