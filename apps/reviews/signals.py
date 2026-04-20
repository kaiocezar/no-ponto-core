"""Signals para manter media de avaliacoes no provider."""

from __future__ import annotations

from django.db.models import Avg, Count
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.providers.models import ProviderProfile
from apps.reviews.models import Review


@receiver(post_save, sender=Review)
def recalculate_provider_review_metrics(
    sender: type[Review],
    instance: Review,
    **kwargs: object,
) -> None:
    stats = Review.objects.filter(
        provider=instance.provider,
        is_public=True,
        rating__isnull=False,
    ).aggregate(avg=Avg("rating"), total=Count("id"))
    ProviderProfile.objects.filter(pk=instance.provider_id).update(
        average_rating=stats["avg"],
        total_reviews=stats["total"] or 0,
    )
