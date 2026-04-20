"""Views de avaliacoes."""

from __future__ import annotations

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.providers.models import ProviderProfile
from apps.reviews.models import Review
from apps.reviews.serializers import (
    ProviderReviewReplySerializer,
    ProviderReviewSerializer,
    PublicReviewSerializer,
    ReviewByTokenReadSerializer,
    ReviewByTokenSubmitSerializer,
)


class ReviewByTokenView(APIView):
    permission_classes = [AllowAny]

    def _get_review(self, token: str) -> Review:
        review = (
            Review.objects.select_related("provider", "appointment__service")
            .filter(review_token=token)
            .first()
        )
        if review is None or review.token_expires_at < timezone.now():
            raise NotFound()
        return review

    def get(self, request: Request, token: str, *args: object, **kwargs: object) -> Response:
        return Response(ReviewByTokenReadSerializer(self._get_review(token)).data)

    def post(self, request: Request, token: str, *args: object, **kwargs: object) -> Response:
        review = self._get_review(token)
        if review.rating is not None:
            return Response(
                {"detail": "Avaliacao ja enviada."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = ReviewByTokenSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review.rating = serializer.validated_data["rating"]
        review.comment = (serializer.validated_data.get("comment") or "").strip() or None
        review.save(update_fields=["rating", "comment"])
        return Response(ProviderReviewSerializer(review).data)


class ProviderReviewListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProviderReviewSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = Review.objects.filter(
            provider=self.request.user.provider_profile,
            rating__isnull=False,
        ).order_by("-created_at")
        rating = self.request.query_params.get("rating")
        if rating:
            qs = qs.filter(rating=rating)
        return qs


class ReviewReplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        review = get_object_or_404(Review, pk=pk, provider=request.user.provider_profile)
        if review.provider_reply:
            return Response({"detail": "Resposta ja cadastrada."}, status=status.HTTP_409_CONFLICT)
        serializer = ProviderReviewReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review.provider_reply = serializer.validated_data["reply"].strip()
        review.replied_at = timezone.now()
        review.save(update_fields=["provider_reply", "replied_at"])
        return Response(ProviderReviewSerializer(review).data)


class ReviewToggleVisibilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        review = get_object_or_404(Review, pk=pk, provider=request.user.provider_profile)
        review.is_public = not review.is_public
        review.save(update_fields=["is_public"])
        return Response({"is_public": review.is_public})


class PublicReviewListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicReviewSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        provider = get_object_or_404(ProviderProfile, slug=self.kwargs["slug"], is_published=True)
        return Review.objects.filter(
            provider=provider,
            is_public=True,
            rating__isnull=False,
        ).order_by("-created_at")


class PublicReviewSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, slug: str, *args: object, **kwargs: object) -> Response:
        provider = get_object_or_404(ProviderProfile, slug=slug, is_published=True)
        qs = Review.objects.filter(provider=provider, is_public=True, rating__isnull=False)
        distribution = {str(star): 0 for star in range(1, 6)}
        for item in qs.values("rating").annotate(total=Count("id")):
            distribution[str(item["rating"])] = item["total"]
        return Response(
            {
                "average_rating": provider.average_rating,
                "total_reviews": provider.total_reviews,
                "rating_distribution": distribution,
            }
        )
