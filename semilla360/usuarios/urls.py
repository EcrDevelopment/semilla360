from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView
from .views import PasswordResetRequestView, PasswordResetConfirmView,CustomTokenObtainPairView,CustomTokenRefreshView
from . import views

urlpatterns = [
    path('auth/login/',CustomTokenObtainPairView.as_view(), name='login'),
    path('get-csrf-token/', views.get_csrf_token, name='get_csrf_token'),
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),  # Solicitar restablecimiento
    path('auth/password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),  # Confirmar restablecimiento
]
