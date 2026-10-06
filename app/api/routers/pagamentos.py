from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import exigir_perfis
from app.application.services import carregar_pedido, processar_pagamento
from app.domain.enums import Perfil, StatusPagamento
from app.domain.schemas import PagamentoEntrada
from app.infrastructure.database import get_db
from app.infrastructure.models import Usuario

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


@router.post("/{pedido_id}/processar")
def processar(pedido_id: int, entrada: PagamentoEntrada, usuario: Usuario = Depends(exigir_perfis(Perfil.CLIENTE.value, Perfil.ATENDENTE.value, Perfil.GERENTE.value, Perfil.ADMIN.value)), db: Session = Depends(get_db)):
    pedido = carregar_pedido(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail={"error": "PEDIDO_NAO_ENCONTRADO", "message": "Pedido não encontrado.", "details": []})
    if usuario.perfil == Perfil.CLIENTE.value and pedido.cliente_id != usuario.id:
        raise HTTPException(status_code=403, detail={"error": "SEM_PERMISSAO", "message": "Você não pode processar pagamento de outro cliente.", "details": []})
    if pedido.pagamento and pedido.pagamento.status != StatusPagamento.PENDENTE.value:
        raise HTTPException(status_code=409, detail={"error": "PAGAMENTO_JA_PROCESSADO", "message": "O pagamento deste pedido já foi processado.", "details": []})
    pagamento = processar_pagamento(db, pedido, entrada.resultado, usuario.id)
    pedido = carregar_pedido(db, pedido_id)
    return {"pedidoId": pedido.id, "statusPagamento": pagamento.status, "statusPedido": pedido.status, "referenciaExterna": pagamento.referencia_externa}
