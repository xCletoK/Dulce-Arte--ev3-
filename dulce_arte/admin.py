from django.contrib import admin
from django.contrib import messages
from .models import Cliente, Insumo, Producto, RecetaBOM, Pedido, RutaDespacho, DetallePedido


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'telefono', 'email', 'fecha_creacion')
    search_fields = ('nombre', 'telefono', 'email')
    list_filter = ('fecha_creacion',)


class RecetaBOMInline(admin.TabularInline):
    model = RecetaBOM
    extra = 1


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'precio_base')
    search_fields = ('nombre',)
    inlines = [RecetaBOMInline]


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'stock_actual', 'stock_minimo', 'unidad_medida', 'costo_unitario')
    list_filter = ('unidad_medida',)
    search_fields = ('nombre',)


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 1


@admin.action(description="Descontar Stock de Bodega según BOM")
def aplicar_descuento_bom(modeladmin, request, queryset):
    for pedido in queryset:
        try:
            pedido.descontar_stock_bom()
            messages.success(request, f"Stock descontado para el Pedido #{pedido.id}.")
        except Exception as e:
            messages.error(request, f"Error en Pedido #{pedido.id}: {str(e)}")


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'cliente', 'producto_base', 'estado_kanban', 'estado_pago',
        'fecha_entrega', 'bom_descontado', 'total', 'monto_abonado'
    )
    list_filter = ('estado_kanban', 'estado_pago', 'bom_descontado', 'fecha_entrega')
    search_fields = ('cliente__nombre', 'especificaciones_diseno')
    actions = [aplicar_descuento_bom]
    autocomplete_fields = ['cliente', 'producto_base']
    inlines = [DetallePedidoInline]
    fieldsets = (
        ('Cliente y Cotización', {
            'fields': ('cliente', 'producto_base', 'especificaciones_diseno', 'total', 'monto_abonado', 'estado_pago')
        }),
        ('Seguimiento', {
            'fields': ('estado_kanban', 'fecha_entrega', 'bom_descontado')
        }),
    )


@admin.register(RutaDespacho)
class RutaDespachoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'tipo_entrega', 'repartidor', 'direccion_entrega', 'estado', 'fecha_despacho')
    list_filter = ('tipo_entrega', 'estado')
    search_fields = ('direccion_entrega', 'pedido__cliente__nombre')