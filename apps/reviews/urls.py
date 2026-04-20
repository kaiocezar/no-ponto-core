from django.urls import path

from apps.reviews.views import ReviewByTokenView

urlpatterns = [
    path("by-token/<str:token>/", ReviewByTokenView.as_view(), name="review-by-token"),
]
