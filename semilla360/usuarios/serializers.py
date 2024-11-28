from rest_framework import serializers
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken,AccessToken
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import PasswordResetToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import re

#este serializer define la estructura de la respuesta que se enviara al momento de hacer login
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        # Agregar información del usuario
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'nombre': self.user.first_name,
            'apellido': self.user.last_name,
            # Aquí puedes agregar más campos si es necesario
        }
        #print(data)

        return data

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, write_only=True)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No existe un usuario con este correo.")
        return value

    def save(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email)

        # Generar el token de acceso JWT
        token = RefreshToken.for_user(user).access_token

        # Guardar el token y usuario en la base de datos
        PasswordResetToken.objects.create(user=user, token=token)

        # Crear el enlace de restablecimiento
        reset_link = f"{settings.FRONTEND_URL}/reset-password/confirm?token={token}&user={user.id}"
        site_name = "Semilla-360°"

        # Cargar y renderizar la plantilla HTML
        html_content = render_to_string("emails/password_reset.html", {
            'reset_link': reset_link,
            'site_name': site_name,
        })
        text_content = strip_tags(html_content)  # Genera una versión de texto plano sin HTML

        # Configurar el correo
        subject = "Restablecimiento de contraseña"
        from_email = settings.DEFAULT_FROM_EMAIL
        email_message = EmailMultiAlternatives(subject, text_content, from_email, [email])
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

# serializers.py
class SetNewPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        user = self.context['user']
        user.set_password(data['password'])
        user.save()
        return data



class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    user_id = serializers.IntegerField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        token = attrs.get('token')
        user_id = attrs.get('user_id')
        new_password = attrs.get('new_password')

        # Verifica la existencia del token
        try:
            token_instance = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("El token es inválido.")

        # Verifica si el token ha expirado
        if token_instance.is_expired():
            raise serializers.ValidationError("El token ha expirado, realiza una nueva solicitud.")

        # Verifica si el user_id coincide con el del token
        if token_instance.user.id != user_id:
            raise serializers.ValidationError("El usuario no coincide con el token proporcionado.")

        # Asegura que el usuario existe
        if not User.objects.filter(id=user_id).exists():
            raise serializers.ValidationError("El usuario no existe.")

        # Validación de la nueva contraseña
        if len(new_password) < 8:
            raise serializers.ValidationError("La contraseña debe tener al menos 8 caracteres.")
        if not re.search(r"[A-Z]", new_password):
            raise serializers.ValidationError("La contraseña debe contener al menos una letra mayúscula.")
        if not re.search(r"[a-z]", new_password):
            raise serializers.ValidationError("La contraseña debe contener al menos una letra minúscula.")
        if not re.search(r"[0-9]", new_password):
            raise serializers.ValidationError("La contraseña debe contener al menos un número.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
            raise serializers.ValidationError("La contraseña debe contener al menos un carácter especial.")

        # Si todo es válido, devuelve los atributos validados
        return attrs



