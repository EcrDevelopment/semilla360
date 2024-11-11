from rest_framework import serializers
from .models import Product

class ExampleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'


class FileSerializer(serializers.Serializer):
    file = serializers.FileField()