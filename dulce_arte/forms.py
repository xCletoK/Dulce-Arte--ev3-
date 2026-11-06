from django import forms
from .models import Pedido, RutaDespacho, Cliente, Insumo, Producto, RecetaBOM, DetallePedido


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'email', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'descripcion', 'precio_base']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'precio_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '500', 'min': '0'}),
        }


class PedidoForm(forms.ModelForm):
    tipo_entrega = forms.ChoiceField(
        choices=RutaDespacho.TIPOS_ENTREGA,
        initial='RETIRO_LOCAL',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo_entrega_pedido'})
    )
    direccion_entrega = forms.CharField(
        required=False,
        initial='Retiro en local',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_direccion_pedido', 'placeholder': 'Ej: Av. Principal 123'})
    )

    class Meta:
        model = Pedido
        fields = [
            'cliente', 'producto_base', 'cantidad', 'especificaciones_diseno',
            'fecha_entrega', 'total', 'monto_abonado'
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'producto_base': forms.Select(attrs={'class': 'form-control', 'id': 'id_producto_base'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'id': 'id_cantidad'}),
            'especificaciones_diseno': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ej: Torta 2 pisos, bizcocho vainilla, relleno manjar...'
            }),
            'fecha_entrega': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'total': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'id_total',
                'readonly': 'readonly',
                'tabindex': '-1',
                'style': 'background-color: var(--surface-muted, #f1f5f9); cursor: not-allowed; font-weight: 700;'
            }),
            'monto_abonado': forms.HiddenInput(attrs={'id': 'id_monto_abonado'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto_base'].required = False
        self.fields['producto_base'].empty_label = "---------"


class RutaDespachoForm(forms.ModelForm):
    class Meta:
        model = RutaDespacho
        fields = ['tipo_entrega', 'repartidor', 'direccion_entrega', 'estado', 'fecha_despacho']
        widgets = {
            'tipo_entrega': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo_entrega'}),
            'repartidor': forms.Select(attrs={'class': 'form-control', 'id': 'id_repartidor'}),
            'direccion_entrega': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_direccion_entrega'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'fecha_despacho': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['repartidor'].required = False
        self.fields['repartidor'].empty_label = "— Seleccionar repartidor —"


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ['nombre', 'unidad_medida', 'stock_actual', 'stock_minimo', 'costo_unitario']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-control'}),
            'stock_actual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'costo_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


class RecetaBOMForm(forms.ModelForm):
    class Meta:
        model = RecetaBOM
        fields = ['producto', 'insumo', 'cantidad_requerida']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control'}),
            'insumo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_requerida': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }