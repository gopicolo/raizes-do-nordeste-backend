from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import exigir_perfis, usuario_atual
from app.application.services import alterar_status_pedido, carregar_pedido, criar_pedido
from app.domain.enums import CanalPedido, Perfil, StatusPedido
from app.domain.schemas import PedidoCriacao, StatusPedidoEntrada
from app.infrastructure.database import get_db
from app.infrastructure.models import Pedido, Usuario

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def serializar(pedido: Pedido):
    return {
        "id": pedido.id,
        "clienteId": pedido.cliente_id,
        "unidadeId": pedido.unidade_id,
        "canalPedido": pedido.canal_pedido,
        "status": pedido.status,
        "total": float(pedido.total),
        "itens": [{"produtoId": i.produto_id, "nome": i.produto.nome, "quantidade": i.quantidade, "precoUnitario": float(i.preco_unitario)} for i in pedido.itens],
        "createdAt": pedido.created_at,
    }


@router.post("", status_code=201)
def novo_pedido(entrada: PedidoCriacao, usuario: Usuario = Depends(exigir_perfis(Perfil.CLIENTE.value, Perfil.ATENDENTE.value)), db: Session = Depends(get_db)):
    return serializar(criar_pedido(db, usuario, entrada))


@router.get("")
def listar_pedidos(
    canalPedido: CanalPedido | None = Query(None),
    status: StatusPedido | None = Query(None),
    page: int = 1,
    limit: int = 20,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    stmt = select(Pedido).order_by(Pedido.id.desc())
    if usuario.perfil == Perfil.CLIENTE.value:
        stmt = stmt.where(Pedido.cliente_id == usuario.id)
    if canalPedido:
        stmt = stmt.where(Pedido.canal_pedido == canalPedido.value)
    if status:
        stmt = stmt.where(Pedido.status == status.value)
    ids = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
    return {"page": page, "limit": limit, "items": [serializar(carregar_pedido(db, p.id)) for p in ids]}


@router.get("/{pedido_id}")
def obter_pedido(pedido_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    pedido = carregar_pedido(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail={"error": "PEDIDO_NAO_ENCONTRADO", "message": "Pedido não encontrado.", "details": []})
    if usuario.perfil == Perfil.CLIENTE.value and pedido.cliente_id != usuario.id:
        raise HTTPException(status_code=403, detail={"error": "SEM_PERMISSAO", "message": "Você não pode acessar pedidos de outro cliente.", "details": []})
    return serializar(pedido)


@router.patch("/{pedido_id}/status")
def atualizar_status(pedido_id: int, entrada: StatusPedidoEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    pedido = carregar_pedido(db, pedido_id)
    if not pedido:
        raise HTTPException(status_code=404, detail={"error": "PEDIDO_NAO_ENCONTRADO", "message": "Pedido não encontrado.", "details": []})
    equipe = {Perfil.COZINHA.value, Perfil.GERENTE.value, Perfil.ADMIN.value}
    cancelar_proprio = (
        usuario.perfil in {Perfil.CLIENTE.value, Perfil.ATENDENTE.value}
        and pedido.cliente_id == usuario.id
        and pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO.value
        and entrada.status == StatusPedido.CANCELADO
    )
    if usuario.perfil not in equipe and not cancelar_proprio:
        raise HTTPException(status_code=403, detail={
            "error": "SEM_PERMISSAO",
            "message": "Você só pode cancelar seu próprio pedido enquanto aguarda pagamento.",
            "details": [],
        })
    return serializar(alterar_status_pedido(db, pedido, entrada.status, usuario.id))
