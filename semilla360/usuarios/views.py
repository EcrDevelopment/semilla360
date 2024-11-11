
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import PasswordResetSerializer, PasswordResetConfirmSerializer# views.py
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from .models import PasswordResetToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer




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