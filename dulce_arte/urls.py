from django.urls import path, include
from rest_framework.routers import DefaultRouter

from dulce_arte.views import (
    landing, login_view, register_view, logout_view, custom_404,
    dashboard, gestion_pedidos_view, editar_pedido_view, kanban_cocina_view, cambiar_estado_kanban,
    inventario_bom_view, descontar_bom_pedido,
    rutas_despacho_view, editar_despacho_view,
    crear_insumo_view, editar_insumo_view, crear_bom_view, editar_bom_view, crear_producto_view, crear_cliente_view, cancelar_pedido_view,
    InsumoViewSet, ProductoViewSet, PedidoViewSet, RutaDespachoViewSet, ClienteViewSet,
)

router = DefaultRouter()
router.register(r'insumos', InsumoViewSet)
router.register(r'productos', ProductoViewSet)
router.register(r'pedidos', PedidoViewSet)
router.register(r'despachos', RutaDespachoViewSet)
router.register(r'clientes', ClienteViewSet)

urlpatterns = [
    path('api/', include(router.urls)),

    path('', landing, name='landing'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),

    path('panel/', dashboard, name='dashboard'),
    path('pedidos/', gestion_pedidos_view, name='gestion_pedidos_html'),
    path('pedidos/editar/<int:pk>/', editar_pedido_view, name='editar_pedido_html'),
    path('pedidos/cancelar/<int:pk>/', cancelar_pedido_view, name='cancelar_pedido_html'),
    path('clientes/crear/', crear_cliente_view, name='crear_cliente'),
    path('kanban/', kanban_cocina_view, name='kanban_cocina_html'),
    path('kanban/avanzar/<int:pk>/', cambiar_estado_kanban, name='cambiar_estado_kanban'),
    path('inventario/', inventario_bom_view, name='inventario_bom_html'),
    path('pedidos/descontar-bom/<int:pk>/', descontar_bom_pedido, name='descontar_bom_pedido'),
    path('despachos/', rutas_despacho_view, name='rutas_despacho_html'),
    path('despachos/editar/<int:pk>/', editar_despacho_view, name='editar_despacho_html'),
    path('insumos/crear/', crear_insumo_view, name='crear_insumo'),
    path('insumos/editar/<int:pk>/', editar_insumo_view, name='editar_insumo'),
    path('productos/crear/', crear_producto_view, name='crear_producto'),
    path('bom/crear/', crear_bom_view, name='crear_bom'),
    path('bom/editar/<int:pk>/', editar_bom_view, name='editar_bom'),
]