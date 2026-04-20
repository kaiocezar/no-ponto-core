"""Models de avaliacoes pos-consulta."""

from __future__ import annotations

import uuid

from django.db import models


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="review",
    )
    provider = models.ForeignKey(
        "providers.ProviderProfile",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    client = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    client_name = models.CharField(max_length=200)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    is_public = models.BooleanField(default=True)
    provider_reply = models.TextField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    review_token = models.CharField(max_length=128, unique=True, db_index=True)
    token_expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews_review"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(rating__gte=1, rating__lte=5) | models.Q(rating__isnull=True),
                name="review_rating_range_1_5_or_null",
            )
        ]
        indexes = [
            models.Index(fields=["provider", "created_at"]),
            models.Index(fields=["provider", "is_public", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Review {self.id} ({self.provider_id})"
