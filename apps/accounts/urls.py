"""URLs de autenticação e cadastro."""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.views import (
    AcceptInviteView,
    ClientMeView,
    CompleteProfileView,
    RegisterProviderView,
    RequestOTPView,
    ValidateInviteView,
    VerifyOTPView,
)

urlpatterns = [
    path("register/", RegisterProviderView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("request-otp/", RequestOTPView.as_view(), name="request-otp"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
    path("me/", ClientMeView.as_view(), name="accounts-me"),
    path("accept-invite/", ValidateInviteView.as_view(), name="validate-invite"),
    path("accept-invite/accept/", AcceptInviteView.as_view(), name="accept-invite"),
]
