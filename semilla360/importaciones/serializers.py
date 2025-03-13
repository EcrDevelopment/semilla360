from rest_framework import serializers
from .models import Producto, Despacho, DetalleDespacho, ConfiguracionDespacho, GastosExtra, OrdenCompraDespacho, \
    Empresa, OrdenCompra, ProveedorTransporte, Transportista


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = '__all__'

class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = '__all__'

class OrdenCompraSerializer(serializers.ModelSerializer):
    empresa = EmpresaSerializer(read_only=True)
    producto = ProductoSerializer(read_only=True)

    class Meta:
        model = OrdenCompra
        fields = '__all__'

class ProveedorTransporteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProveedorTransporte
        fields = '__all__'

class TransportistaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transportista
        fields = '__all__'

class OrdenCompraDespachoSerializer(serializers.ModelSerializer):
    orden_compra = OrdenCompraSerializer(read_only=True)

    class Meta:
        model = OrdenCompraDespacho
        fields = '__all__'


class ConfiguracionDespachoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionDespacho
        fields = '__all__'


class DetalleDespachoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetalleDespacho
        fields = '__all__'


class GastosExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = GastosExtra
        fields = '__all__'



class DespachoSerializer(serializers.ModelSerializer):
    proveedor = ProveedorTransporteSerializer(read_only=True)
    transportista = TransportistaSerializer(read_only=True)
    ordenes_compra = OrdenCompraSerializer(many=True, read_only=True)
    ordenes_despacho = OrdenCompraDespachoSerializer(many=True, read_only=True)
    configuracion_despacho = ConfiguracionDespachoSerializer(source='configuraciondespacho_set', many=True,read_only=True)
    detalle_despacho = DetalleDespachoSerializer(source='detalledespacho_set', many=True, read_only=True)
    gastos_extra = GastosExtraSerializer(source='gastosextra_set', many=True, read_only=True)

    class Meta:
        model = Despacho
        fields = '__all__'
