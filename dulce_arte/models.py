from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import transaction


class Cliente(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    notas = models.TextField(blank=True, help_text="Preferencias u observaciones del cliente")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    UNIDADES_MEDIDA = [
        ('KG', 'Kilo(s)'),
        ('G', 'Gramo(s)'),
        ('L', 'Litro(s)'),
        ('ML', 'Mililitro(s)'),
        ('UNID', 'Unidad(es)'),
    ]

    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(
        max_length=10, 
        choices=UNIDADES_MEDIDA, 
        default='KG'
    )
    stock_actual = models.FloatField(default=0.0)
    stock_minimo = models.FloatField(default=0.0)
    costo_unitario = models.DecimalField(max_length=10, decimal_places=2, max_digits=10, default=0.00)

    def __str__(self):
        return f"{self.nombre} ({self.get_unidad_medida_display()})"

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

    class Meta:
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.stock_actual} {self.unidad_medida})"

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo


class Producto(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    precio_base = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = "Producto base"
        verbose_name_plural = "Productos base"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} - ${self.precio_base}"


class RecetaBOM(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='materiales_bom')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_requerida = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Cantidad necesaria por unidad de producto",
        validators=[MinValueValidator(0.01)]
    )

    class Meta:
        verbose_name = "Material de receta (BOM)"
        verbose_name_plural = "Listas de materiales (BOM)"
        unique_together = ('producto', 'insumo')

    def __str__(self):
        return f"{self.producto.nombre} → {self.cantidad_requerida} {self.insumo.unidad_medida} de {self.insumo.nombre}"


class Pedido(models.Model):
    ESTADOS_KANBAN = [
        ('RECIBIDO', 'Recibido'),
        ('EN_PREPARACION', 'En preparación'),
        ('HORNEADO_DECORADO', 'Horneado / Decorado'),
        ('CONTROL_CALIDAD', 'Control de calidad'),
        ('LISTO', 'Listo'),
        ('CANCELADO', 'Cancelado'),
    ]

    ESTADOS_PAGO = [
        ('PENDIENTE', 'Pendiente'),
        ('ABONADO', 'Abonado (50%)'),
        ('PAGADO', 'Pagado Total'),
    ]

    ORDEN_ESTADOS = ['RECIBIDO', 'EN_PREPARACION', 'HORNEADO_DECORADO', 'CONTROL_CALIDAD', 'LISTO']

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='pedidos')
    producto_base = models.ForeignKey(
        Producto, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Producto principal (o dejar vacío si el pedido es 100% personalizado)"
    )
    cantidad = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text="Cantidad de unidades del producto o lote"
    )
    especificaciones_diseno = models.TextField(
        help_text="Detalles del diseño, tamaño, relleno, decoración e ingredientes especiales"
    )
    fecha_entrega = models.DateTimeField()
    estado_kanban = models.CharField(max_length=30, choices=ESTADOS_KANBAN, default='RECIBIDO')
    estado_pago = models.CharField(max_length=20, choices=ESTADOS_PAGO, default='PENDIENTE')
    
    total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0)]
    )
    monto_abonado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        validators=[MinValueValidator(0)]
    )
    bom_descontado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Pedido #{self.id} – {self.cliente.nombre}"

    def save(self, *args, **kwargs):
        if self.total > 0 and self.monto_abonado >= self.total:
            self.estado_pago = 'PAGADO'
        elif self.monto_abonado > 0:
            self.estado_pago = 'ABONADO'
        else:
            self.estado_pago = 'PENDIENTE'
        super().save(*args, **kwargs)

    @property
    def saldo_pendiente(self):
        return max(0, self.total - self.monto_abonado)

    def get_siguiente_estado(self):
        try:
            idx = self.ORDEN_ESTADOS.index(self.estado_kanban)
            if idx + 1 < len(self.ORDEN_ESTADOS):
                return self.ORDEN_ESTADOS[idx + 1]
        except ValueError:
            pass
        return None

    def avanzar_estado(self):
        siguiente = self.get_siguiente_estado()
        if not siguiente:
            raise ValidationError("El pedido ya está en el último estado o fue cancelado.")
        self.estado_kanban = siguiente
        self.save(update_fields=['estado_kanban'])

    @transaction.atomic
    def descontar_stock_bom(self):
        if self.bom_descontado:
            raise ValidationError("El stock de este pedido ya fue descontado.")

        detalles = self.detalles.all()
        items_a_descontar = []

        if detalles.exists():
            for d in detalles:
                if d.producto:
                    for rec in d.producto.materiales_bom.select_related('insumo'):
                        items_a_descontar.append({
                            'insumo': rec.insumo,
                            'cantidad': float(rec.cantidad_requerida) * d.cantidad
                        })
        elif self.producto_base:
            for rec in self.producto_base.materiales_bom.select_related('insumo'):
                items_a_descontar.append({
                    'insumo': rec.insumo,
                    'cantidad': float(rec.cantidad_requerida) * self.cantidad
                })
        else:
            prod_comodin = Producto.objects.filter(nombre__icontains="personalizado").first()
            if prod_comodin:
                for rec in prod_comodin.materiales_bom.select_related('insumo'):
                    items_a_descontar.append({
                        'insumo': rec.insumo,
                        'cantidad': float(rec.cantidad_requerida) * self.cantidad
                    })

        if not items_a_descontar:
            self.bom_descontado = True
            self.save(update_fields=['bom_descontado'])
            return

        insumos_ids = [item['insumo'].id for item in items_a_descontar]
        insumos_db = {
            i.id: i for i in Insumo.objects.filter(id__in=insumos_ids).select_for_update()
        }

        for item in items_a_descontar:
            insumo_obj = insumos_db[item['insumo'].id]
            if insumo_obj.stock_actual < item['cantidad']:
                raise ValidationError(
                    f"Stock insuficiente de {insumo_obj.nombre}. "
                    f"Necesario: {item['cantidad']} {insumo_obj.unidad_medida}, "
                    f"disponible: {insumo_obj.stock_actual}."
                )

        for item in items_a_descontar:
            insumo_obj = insumos_db[item['insumo'].id]
            insumo_obj.stock_actual -= item['cantidad']
            insumo_obj.save(update_fields=['stock_actual'])

        self.bom_descontado = True
        self.save(update_fields=['bom_descontado'])

    @transaction.atomic
    def devolver_stock_bom(self):
        if not self.bom_descontado:
            return

        detalles = self.detalles.all()
        items_a_devolver = []

        if detalles.exists():
            for d in detalles:
                if d.producto:
                    for rec in d.producto.materiales_bom.select_related('insumo'):
                        items_a_devolver.append({
                            'insumo': rec.insumo,
                            'cantidad': float(rec.cantidad_requerida) * d.cantidad
                        })
        elif self.producto_base:
            for rec in self.producto_base.materiales_bom.select_related('insumo'):
                items_a_devolver.append({
                    'insumo': rec.insumo,
                    'cantidad': float(rec.cantidad_requerida) * self.cantidad
                })

        insumos_ids = [item['insumo'].id for item in items_a_devolver]
        insumos_db = {
            i.id: i for i in Insumo.objects.filter(id__in=insumos_ids).select_for_update()
        }

        for item in items_a_devolver:
            insumo_obj = insumos_db[item['insumo'].id]
            insumo_obj.stock_actual += item['cantidad']
            insumo_obj.save(update_fields=['stock_actual'])

        self.bom_descontado = False
        self.save(update_fields=['bom_descontado'])


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion_custom = models.CharField(
        max_length=255, blank=True,
        help_text="Descripción si es un ítem personalizado adicional"
    )
    cantidad = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = "Detalle del pedido"
        verbose_name_plural = "Detalles del pedido"

    def __str__(self):
        prod_nombre = self.producto.nombre if self.producto else self.descripcion_custom
        return f"{self.cantidad}x {prod_nombre} (${self.subtotal})"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class RutaDespacho(models.Model):
    TIPOS_ENTREGA = [
        ('RETIRO_LOCAL', 'Retiro en Local'),
        ('DOMICILIO', 'Despacho a Domicilio'),
    ]

    ESTADOS_DESPACHO = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_CAMINO', 'En camino'),
        ('ENTREGADO', 'Entregado'),
        ('FALLIDO', 'Fallido'),
    ]

    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name='despacho')
    tipo_entrega = models.CharField(max_length=20, choices=TIPOS_ENTREGA, default='RETIRO_LOCAL')
    repartidor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='despachos_asignados',
        help_text="Asignar repartidor solo si el envío es a domicilio"
    )
    direccion_entrega = models.CharField(max_length=255, default="Retiro en local")
    estado = models.CharField(max_length=20, choices=ESTADOS_DESPACHO, default='PENDIENTE')
    comprobante_firma = models.ImageField(
        upload_to='comprobantes/', blank=True, null=True,
        help_text="Firma digital o comprobante de entrega"
    )
    fecha_despacho = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Ruta de despacho"
        verbose_name_plural = "Rutas de despacho"

    def __str__(self):
        return f"Despacho Pedido #{self.pedido.id} ({self.get_tipo_entrega_display()}) – {self.get_estado_display()}"

    def clean(self):
        super().clean()
        if self.tipo_entrega == 'DOMICILIO':
            if not self.repartidor:
                raise ValidationError({'repartidor': 'Debe seleccionar un repartidor para entregas a domicilio.'})
            if not self.direccion_entrega or self.direccion_entrega == "Retiro en local":
                raise ValidationError({'direccion_entrega': 'Debe ingresar una dirección válida de despacho.'})
        elif self.tipo_entrega == 'RETIRO_LOCAL':
            self.repartidor = None
            self.direccion_entrega = "Retiro en local"