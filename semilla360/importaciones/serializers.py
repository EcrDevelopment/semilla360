from rest_framework import serializers
from .models import Producto

class productoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = '__all__'


class FileSerializer(serializers.Serializer):
    file = serializers.FileField()