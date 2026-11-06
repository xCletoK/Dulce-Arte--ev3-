import base64
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import F

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Pedido, Insumo, Producto, RutaDespacho, Cliente, RecetaBOM
from .forms import PedidoForm, RutaDespachoForm, InsumoForm, RecetaBOMForm, ClienteForm, ProductoForm
from .serializers import (
    InsumoSerializer, ProductoSerializer,
    PedidoSerializer, RutaDespachoSerializer, ClienteSerializer
)


def es_staff(user):
    return user.is_authenticated and user.is_staff


# ==================== PÚBLICO ====================

def landing(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard')
    return render(request, 'dulce_arte/landing.html')


def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                return redirect('dashboard')
            messages.warning(request, 'Tu cuenta no tiene permisos de acceso al sistema de gestión.')
            logout(request)
            return redirect('login')
        messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = AuthenticationForm()

    return render(request, 'dulce_arte/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('landing')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cuenta creada correctamente. Un administrador debe autorizar tu acceso.')
            return redirect('login')
        messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = UserCreationForm()

    return render(request, 'dulce_arte/register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('landing')


def custom_404(request, exception=None):
    return render(request, 'dulce_arte/404.html', status=404)


# ==================== PANEL (SOLO STAFF) ====================

@login_required
@user_passes_test(es_staff, login_url='login')
def dashboard(request):
    context = {
        'total_pedidos': Pedido.objects.count(),
        'pendientes_bom': Pedido.objects.filter(bom_descontado=False).exclude(estado_kanban='CANCELADO').count(),
        'en_cocina': Pedido.objects.exclude(estado_kanban__in=['RECIBIDO', 'LISTO', 'CANCELADO']).count(),
        'listos': Pedido.objects.filter(estado_kanban='LISTO').count(),
        'insumos_bajo': Insumo.objects.filter(stock_actual__lte=F('stock_minimo')),
    }
    return render(request, 'dulce_arte/dashboard.html', context)


@login_required
@user_passes_test(es_staff, login_url='login')
def gestion_pedidos_view(request):
    if request.method == 'POST':
        form = PedidoForm(request.POST)
        if form.is_valid():
            pedido = form.save()
            tipo = form.cleaned_data.get('tipo_entrega', 'RETIRO_LOCAL')
            direccion = form.cleaned_data.get('direccion_entrega') or 'Retiro en local'
            if tipo == 'RETIRO_LOCAL':
                direccion = 'Retiro en local'

            RutaDespacho.objects.create(
                pedido=pedido,
                tipo_entrega=tipo,
                direccion_entrega=direccion
            )
            messages.success(request, f'Pedido #{pedido.id} registrado correctamente.')
            return redirect('gestion_pedidos_html')
    else:
        form = PedidoForm()

    pedidos = Pedido.objects.select_related('cliente', 'producto_base').order_by('-fecha_creacion')
    productos = Producto.objects.all()
    return render(request, 'dulce_arte/pedidos.html', {
        'form': form,
        'pedidos': pedidos,
        'productos': productos,
    })


@login_required
@user_passes_test(es_staff, login_url='login')
def editar_pedido_view(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    despacho = getattr(pedido, 'despacho', None)

    if request.method == 'POST':
        form = PedidoForm(request.POST, instance=pedido)
        if form.is_valid():
            pedido_obj = form.save()
            tipo = form.cleaned_data.get('tipo_entrega', 'RETIRO_LOCAL')
            direccion = form.cleaned_data.get('direccion_entrega') or 'Retiro en local'
            if tipo == 'RETIRO_LOCAL':
                direccion = 'Retiro en local'

            if despacho:
                despacho.tipo_entrega = tipo
                despacho.direccion_entrega = direccion
                despacho.save()
            else:
                RutaDespacho.objects.create(
                    pedido=pedido_obj,
                    tipo_entrega=tipo,
                    direccion_entrega=direccion
                )
            messages.success(request, f'Pedido #{pedido.id} actualizado correctamente.')
            return redirect('gestion_pedidos_html')
    else:
        initial = {}
        if despacho:
            initial['tipo_entrega'] = despacho.tipo_entrega
            initial['direccion_entrega'] = despacho.direccion_entrega
        form = PedidoForm(instance=pedido, initial=initial)

    productos = Producto.objects.all()
    return render(request, 'dulce_arte/editar_pedido.html', {
        'form': form, 
        'pedido': pedido,
        'productos': productos,
    })


@login_required
@user_passes_test(es_staff, login_url='login')
def crear_cliente_view(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f'Cliente "{cliente.nombre}" registrado correctamente.')
            return redirect('gestion_pedidos_html')
    else:
        form = ClienteForm()
    return render(request, 'dulce_arte/crear_cliente.html', {'form': form})


@login_required
@user_passes_test(es_staff, login_url='login')
def cancelar_pedido_view(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.bom_descontado:
        pedido.devolver_stock_bom()
        messages.info(request, f'Stock devuelto a la bodega al cancelar el pedido #{pedido.id}.')

    pedido.estado_kanban = 'CANCELADO'
    pedido.save(update_fields=['estado_kanban'])
    messages.success(request, f'Pedido #{pedido.id} marcado como cancelado.')
    return redirect('gestion_pedidos_html')


@login_required
@user_passes_test(es_staff, login_url='login')
def kanban_cocina_view(request):
    context = {
        'recibidos': Pedido.objects.filter(estado_kanban='RECIBIDO').select_related('producto_base', 'cliente'),
        'preparacion': Pedido.objects.filter(estado_kanban='EN_PREPARACION').select_related('producto_base', 'cliente'),
        'horneados': Pedido.objects.filter(estado_kanban='HORNEADO_DECORADO').select_related('producto_base', 'cliente'),
        'calidad': Pedido.objects.filter(estado_kanban='CONTROL_CALIDAD').select_related('producto_base', 'cliente'),
        'listos': Pedido.objects.filter(estado_kanban='LISTO').select_related('producto_base', 'cliente'),
    }
    return render(request, 'dulce_arte/kanban.html', context)


@login_required
@user_passes_test(es_staff, login_url='login')
def cambiar_estado_kanban(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.estado_kanban == 'RECIBIDO' and not pedido.bom_descontado:
        messages.error(request, f'No se puede iniciar la preparación del pedido #{pedido.id}. Primero debe descontar el stock (BOM).')
        return redirect('kanban_cocina_html')

    try:
        pedido.avanzar_estado()
        messages.success(request, f'Pedido #{pedido.id} movido a: {pedido.get_estado_kanban_display()}')
    except ValidationError as e:
        messages.error(request, str(e))

    return redirect('kanban_cocina_html')


@login_required
@user_passes_test(es_staff, login_url='login')
def inventario_bom_view(request):
    insumos = Insumo.objects.all()
    productos = Producto.objects.prefetch_related('materiales_bom__insumo').all()
    return render(request, 'dulce_arte/inventario_bom.html', {'insumos': insumos, 'productos': productos})


@login_required
@user_passes_test(es_staff, login_url='login')
def descontar_bom_pedido(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    try:
        pedido.descontar_stock_bom()
        messages.success(request, f'Stock descontado correctamente para el pedido #{pedido.id}.')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error inesperado: {str(e)}')
    return redirect('gestion_pedidos_html')


@login_required
@user_passes_test(es_staff, login_url='login')
def rutas_despacho_view(request):
    despachos = RutaDespacho.objects.select_related('pedido', 'repartidor', 'pedido__producto_base').all()
    return render(request, 'dulce_arte/despachos.html', {'despachos': despachos})


@login_required
@user_passes_test(es_staff, login_url='login')
def editar_despacho_view(request, pk):
    despacho = get_object_or_404(RutaDespacho, pk=pk)
    if request.method == 'POST':
        form = RutaDespachoForm(request.POST, instance=despacho)
        if form.is_valid():
            despacho_obj = form.save(commit=False)
            firma_data = request.POST.get('firma_base64')
            if firma_data and 'data:image' in firma_data:
                format_type, imgstr = firma_data.split(';base64,')
                ext = format_type.split('/')[-1]
                despacho_obj.comprobante_firma.save(
                    f'firma_pedido_{despacho.pedido.id}.{ext}',
                    ContentFile(base64.b64decode(imgstr)),
                    save=False
                )
            despacho_obj.save()
            messages.success(request, f'Despacho del pedido #{despacho.pedido.id} actualizado.')
            return redirect('rutas_despacho_html')
    else:
        form = RutaDespachoForm(instance=despacho)

    return render(request, 'dulce_arte/editar_despacho.html', {'form': form, 'despacho': despacho})


@login_required
@user_passes_test(es_staff, login_url='login')
def crear_insumo_view(request):
    if request.method == 'POST':
        form = InsumoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Insumo creado correctamente.')
            return redirect('inventario_bom_html')
    else:
        form = InsumoForm()
    return render(request, 'dulce_arte/crear_insumo.html', {'form': form})


@login_required
@user_passes_test(es_staff, login_url='login')
def editar_insumo_view(request, pk):
    insumo = get_object_or_404(Insumo, pk=pk)
    if request.method == 'POST':
        form = InsumoForm(request.POST, instance=insumo)
        if form.is_valid():
            form.save()
            messages.success(request, f'Stock de {insumo.nombre} actualizado.')
            return redirect('inventario_bom_html')
    else:
        form = InsumoForm(instance=insumo)
    return render(request, 'dulce_arte/editar_insumo.html', {'form': form, 'insumo': insumo})


@login_required
@user_passes_test(es_staff, login_url='login')
def crear_producto_view(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto base creado correctamente.')
            return redirect('inventario_bom_html')
    else:
        form = ProductoForm()
    return render(request, 'dulce_arte/crear_producto.html', {'form': form})


@login_required
@user_passes_test(es_staff, login_url='login')
def crear_bom_view(request):
    productos = Producto.objects.all().order_by('nombre')
    insumos = Insumo.objects.all().order_by('nombre')

    if request.method == 'POST':
        producto_id = request.POST.get('producto')
        insumo_ids = request.POST.getlist('insumos[]')
        cantidades = request.POST.getlist('cantidades[]')

        if not producto_id:
            messages.error(request, 'Debe seleccionar un producto.')
        elif not insumo_ids or not cantidades:
            messages.error(request, 'Debe agregar al menos un insumo con su cantidad.')
        else:
            producto = get_object_or_404(Producto, pk=producto_id)
            creados = 0
            actualizados = 0

            for insumo_id, cantidad in zip(insumo_ids, cantidades):
                if insumo_id and cantidad:
                    try:
                        cant_val = float(cantidad)
                        if cant_val > 0:
                            insumo_obj = Insumo.objects.get(pk=insumo_id)
                            receta, created = RecetaBOM.objects.update_or_create(
                                producto=producto,
                                insumo=insumo_obj,
                                defaults={'cantidad_requerida': cant_val}
                            )
                            if created:
                                creados += 1
                            else:
                                actualizados += 1
                    except (ValueError, Insumo.DoesNotExist):
                        continue

            if creados > 0 or actualizados > 0:
                messages.success(request, f'Receta BOM guardada para "{producto.nombre}": {creados} insumo(s) nuevo(s), {actualizados} actualizado(s).')
                return redirect('inventario_bom_html')
            else:
                messages.error(request, 'No se pudo guardar ningún insumo válido.')

    return render(request, 'dulce_arte/crear_bom.html', {
        'productos': productos,
        'insumos': insumos,
    })


@login_required
@user_passes_test(es_staff, login_url='login')
def editar_bom_view(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    insumos = Insumo.objects.all().order_by('nombre')
    materiales_actuales = producto.materiales_bom.select_related('insumo').all()

    if request.method == 'POST':
        # 1. Actualizar datos básicos del Producto
        nombre_prod = request.POST.get('nombre_producto', '').strip()
        desc_prod = request.POST.get('descripcion_producto', '').strip()
        precio_prod = request.POST.get('precio_base', 0)

        if nombre_prod:
            producto.nombre = nombre_prod
            producto.descripcion = desc_prod
            try:
                producto.precio_base = float(precio_prod)
            except ValueError:
                pass
            producto.save()

        # 2. Actualizar lista de insumos (BOM)
        insumo_ids = request.POST.getlist('insumos[]')
        cantidades = request.POST.getlist('cantidades[]')

        RecetaBOM.objects.filter(producto=producto).delete()

        creados = 0
        for insumo_id, cantidad in zip(insumo_ids, cantidades):
            if insumo_id and cantidad:
                try:
                    cant_val = float(cantidad)
                    if cant_val > 0:
                        insumo_obj = Insumo.objects.get(pk=insumo_id)
                        RecetaBOM.objects.create(
                            producto=producto,
                            insumo=insumo_obj,
                            cantidad_requerida=cant_val
                        )
                        creados += 1
                except (ValueError, Insumo.DoesNotExist):
                    continue

        messages.success(request, f'Producto "{producto.nombre}" y su receta BOM actualizados correctamente.')
        return redirect('inventario_bom_html')

    return render(request, 'dulce_arte/editar_bom.html', {
        'producto': producto,
        'insumos': insumos,
        'materiales_actuales': materiales_actuales,
    })


# ==================== API DRF ====================

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all().order_by('nombre')
    serializer_class = ClienteSerializer
    permission_classes = [permissions.IsAdminUser]


class InsumoViewSet(viewsets.ModelViewSet):
    queryset = Insumo.objects.all().order_by('nombre')
    serializer_class = InsumoSerializer
    permission_classes = [permissions.IsAdminUser]


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.prefetch_related('materiales_bom__insumo').all()
    serializer_class = ProductoSerializer
    permission_classes = [permissions.IsAdminUser]


class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.select_related('cliente', 'producto_base').all()
    serializer_class = PedidoSerializer
    permission_classes = [permissions.IsAdminUser]

    def update(self, request, *args, **kwargs):
        return Response({'detail': 'Los pedidos no se pueden editar una vez registrados.'}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        return Response({'detail': 'Los pedidos no se pueden editar una vez registrados.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def descontar_bom(self, request, pk=None):
        pedido = self.get_object()
        try:
            pedido.descontar_stock_bom()
            return Response({'detail': f'Stock descontado para el pedido #{pedido.id}.'})
        except ValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def avanzar_estado(self, request, pk=None):
        pedido = self.get_object()
        if pedido.estado_kanban == 'RECIBIDO' and not pedido.bom_descontado:
            return Response({'detail': 'Debe descontar el BOM antes de iniciar la preparación.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pedido.avanzar_estado()
            return Response({'detail': f'Pedido movido a {pedido.get_estado_kanban_display()}', 'estado': pedido.estado_kanban})
        except ValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RutaDespachoViewSet(viewsets.ModelViewSet):
    queryset = RutaDespacho.objects.select_related('pedido', 'repartidor').all()
    serializer_class = RutaDespachoSerializer
    permission_classes = [permissions.IsAdminUser]