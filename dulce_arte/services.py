from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Insumo

class InventarioService:
    @staticmethod
    @transaction.atomic
    def descontar_bom_pedido(pedido):
        if pedido.bom_descontado: raise ValidationError("Stock ya fue descontado previamente.")
        items_requeridos = []

        for detalle in pedido.detalles.select_related('producto').all():
            if detalle.producto:
                for rec in detalle.producto.materiales_bom.select_related('insumo').all():
                    items_requeridos.append({'insumo': rec.insumo, 'cantidad': rec.cantidad_requerida * detalle.cantidad})

        if pedido.producto_base:
            for rec in pedido.producto_base.materiales_bom.select_related('insumo').all():
                items_requeridos.append({'insumo': rec.insumo, 'cantidad': rec.cantidad_requerida})

        for custom in pedido.insumos_personalizados.select_related('insumo').all():
            items_requeridos.append({'insumo': custom.insumo, 'cantidad': custom.cantidad})

        if not items_requeridos:
            pedido.bom_descontado = True
            pedido.save(update_fields=['bom_descontado'])
            return

        resumen = {}
        for item in items_requeridos:
            i_id = item['insumo'].id
            resumen[i_id] = resumen.get(i_id, Decimal('0.00')) + item['cantidad']

        insumos_db = {i.id: i for i in Insumo.objects.filter(id__in=resumen.keys()).select_for_update()}
        for i_id, cant in resumen.items():
            insumo_obj = insumos_db[i_id]
            if insumo_obj.stock_actual < cant: raise ValidationError(f"Stock insuficiente de {insumo_obj.nombre}.")
            insumo_obj.stock_actual -= cant
            insumo_obj.save(update_fields=['stock_actual'])

        pedido.bom_descontado = True
        pedido.save(update_fields=['bom_descontado'])

    @staticmethod
    @transaction.atomic
    def devolver_bom_pedido(pedido):
        if not pedido.bom_descontado: return
        items_a_devolver = []

        for detalle in pedido.detalles.select_related('producto').all():
            if detalle.producto:
                for rec in detalle.producto.materiales_bom.select_related('insumo').all():
                    items_a_devolver.append({'insumo': rec.insumo, 'cantidad': rec.cantidad_requerida * detalle.cantidad})
        if pedido.producto_base:
            for rec in pedido.producto_base.materiales_bom.select_related('insumo').all():
                items_a_devolver.append({'insumo': rec.insumo, 'cantidad': rec.cantidad_requerida})
        for custom in pedido.insumos_personalizados.select_related('insumo').all():
            items_a_devolver.append({'insumo': custom.insumo, 'cantidad': custom.cantidad})

        resumen = {}
        for item in items_a_devolver:
            i_id = item['insumo'].id
            resumen[i_id] = resumen.get(i_id, Decimal('0.00')) + item['cantidad']

        insumos_db = {i.id: i for i in Insumo.objects.filter(id__in=resumen.keys()).select_for_update()}
        for i_id, cant in resumen.items():
            insumo_obj = insumos_db[i_id]
            insumo_obj.stock_actual += cant
            insumo_obj.save(update_fields=['stock_actual'])

        pedido.bom_descontado = False
        pedido.save(update_fields=['bom_descontado'])

class KanbanFSMService:
    ORDEN = ['RECIBIDO', 'EN_PREPARACION', 'HORNEADO_DECORADO', 'CONTROL_CALIDAD', 'LISTO']

    @staticmethod
    def avanzar(pedido):
        if pedido.estado_kanban == 'RECIBIDO':
            if not pedido.abono_suficiente: raise ValidationError("Requiere 50% de abono previo.")
            if not pedido.bom_descontado: InventarioService.descontar_bom_pedido(pedido)
        try:
            idx = KanbanFSMService.ORDEN.index(pedido.estado_kanban)
            if idx + 1 < len(KanbanFSMService.ORDEN):
                pedido.estado_kanban = KanbanFSMService.ORDEN[idx + 1]
                pedido.save(update_fields=['estado_kanban'])
            else: raise ValidationError("Pedido ya terminado.")
        except ValueError: raise ValidationError("Estado inválido.")

    @staticmethod
    def retroceder(pedido):
        try:
            idx = KanbanFSMService.ORDEN.index(pedido.estado_kanban)
            if idx > 0:
                pedido.estado_kanban = KanbanFSMService.ORDEN[idx - 1]
                pedido.save(update_fields=['estado_kanban'])
            else: raise ValidationError("Fase inicial.")
        except ValueError: raise ValidationError("Estado inválido.")