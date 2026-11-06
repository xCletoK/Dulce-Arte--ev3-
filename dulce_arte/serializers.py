from rest_framework import serializers
from .models import Cliente, Insumo, Producto, RecetaBOM, Pedido, RutaDespacho, DetallePedido

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'

class InsumoSerializer(serializers.ModelSerializer):
    stock_bajo = serializers.BooleanField(read_only=True)
    class Meta:
        model = Insumo
        fields = '__all__'

class RecetaBOMSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    class Meta:
        model = RecetaBOM
        fields = '__all__'

class ProductoSerializer(serializers.ModelSerializer):
    materiales_bom = RecetaBOMSerializer(many=True, read_only=True)
    costo_bom_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'descripcion', 'precio_base', 'costo_bom_total', 'materiales_bom']

class PedidoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_kanban_display', read_only=True)
    class Meta:
        model = Pedido
        fields = '__all__'
        read_only_fields = ['bom_descontado', 'fecha_creacion']

class RutaDespachoSerializer(serializers.ModelSerializer):
    pedido_info = serializers.StringRelatedField(source='pedido', read_only=True)
    class Meta:
        model = RutaDespacho
        fields = '__all__'