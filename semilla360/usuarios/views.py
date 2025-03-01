
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import PasswordResetSerializer, PasswordResetConfirmSerializer,CustomTokenObtainPairSerializer
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from .models import PasswordResetToken
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView
from django.http import JsonResponse
from django.conf import settings
from rest_framework.utils import json
from django.middleware.csrf import get_token

def get_csrf_token(request):
    csrf_token = get_token(request)
    return JsonResponse({'csrf_Token': csrf_token})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Correo enviado con éxito"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if serializer.is_valid():
            # Obtener los datos validados
            user_id = serializer.validated_data['user_id']
            new_password = serializer.validated_data['new_password']
            token = serializer.validated_data['token']

            # Cambiar la contraseña
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()

            # Eliminar el token después de usarlo
            PasswordResetToken.objects.filter(token=token, user_id=user_id).delete()

            return Response({"message": "Contraseña restablecida con éxito."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_data = serializer.validated_data
        secure = settings.DEBUG is False  # Secure solo cuando está en producción

        # Crear la respuesta
        response = Response(response_data)

        return response

# Vista para refresh de token
class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # Obtener el refresh_token de las cookies
        refresh_token = request.COOKIES.get('refresh_token')

        # Si no está en las cookies, intentar obtenerlo de los parámetros de la solicitud
        if not refresh_token:
            print('no se encontro token en las cookies')
            refresh_token = request.data.get('refresh')

        # Validar que se haya encontrado el token
        if not refresh_token:
            print('no se encontro token en la request')
            return JsonResponse({'error': 'Refresh token not found'}, status=400)

        data = request.data.copy()

        data['refresh'] = refresh_token

        # Reemplazar los datos de la solicitud original con la copia mutable
        request._body = json.dumps(data)
        # Llamar al metodo original de TokenRefreshView
        return super().post(request, *args, **kwargs)