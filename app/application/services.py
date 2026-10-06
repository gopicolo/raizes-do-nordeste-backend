from datetime import datetime, timezone
from decimal import Decimal
import json
import uuid
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.domain.enums import StatusPagamento, StatusPedido
from app.domain.schemas import PedidoCriacao
from app.infrastructure.models import Estoque, Fidelidade, ItemPedido, Pagamento, Pedido, Produto, Unidade, Usuario
from .audit import registrar_auditoria


def criar_pedido(db: Session, cliente: Usuario, entrada: PedidoCriacao) -> Pedido:
    unidade = db.get(Unidade, entrada.unidadeId)
    if not unidade or not unidade.ativa:
        raise HTTPException(status_code=404, detail={"error": "UNIDADE_NAO_ENCONTRADA", "message": "Unidade inexistente ou inativa.", "details": []})

    itens_preparados: list[tuple[Produto, Estoque, int]] = []
    total = Decimal("0.00")
    for idx, item in enumerate(entrada.itens):
        produto = db.get(Produto, item.produtoId)
        if not produto or not produto.ativo:
            raise HTTPException(status_code=404, detail={"error": "PRODUTO_NAO_ENCONTRADO", "message": f"Produto {item.produtoId} inexistente ou inativo.", "details": [{"field": f"itens[{idx}].produtoId", "issue": "produto não encontrado"}]})
        estoque = db.scalar(select(Estoque).where(Estoque.unidade_id == unidade.id, Estoque.produto_id == produto.id))
        disponivel = estoque.quantidade if estoque else 0
        if disponivel < item.quantidade:
            raise HTTPException(status_code=409, detail={"error": "ESTOQUE_INSUFICIENTE", "message": "Não há quantidade suficiente para um ou mais itens.", "details": [{"field": f"itens[{idx}].quantidade", "issue": f"Disponível: {disponivel}"}]})
        itens_preparados.append((produto, estoque, item.quantidade))
        total += Decimal(produto.preco) * item.quantidade

    pedido = Pedido(
        cliente_id=cliente.id,
        unidade_id=unidade.id,
        canal_pedido=entrada.canalPedido.value,
        status=StatusPedido.AGUARDANDO_PAGAMENTO.value,
        total=total,
    )
    db.add(pedido)
    db.flush()

    for produto, estoque, quantidade in itens_preparados:
        # A condição e o decremento pertencem à mesma instrução SQL.
        # Uma leitura anterior do saldo não protege contra pedidos concorrentes.
        reserva = db.execute(
            update(Estoque)
            .where(Estoque.id == estoque.id, Estoque.quantidade >= quantidade)
            .values(quantidade=Estoque.quantidade - quantidade,
                    atualizado_em=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
        if reserva.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail={
                "error": "ESTOQUE_INSUFICIENTE",
                "message": "O estoque disponível foi reservado por outro pedido.",
                "details": [{"field": "itens", "issue": "Saldo insuficiente na reserva."}],
            })
        db.add(ItemPedido(pedido_id=pedido.id, produto_id=produto.id, quantidade=quantidade, preco_unitario=produto.preco))

    pagamento = Pagamento(pedido_id=pedido.id, status=StatusPagamento.PENDENTE.value, provedor="MOCK")
    db.add(pagamento)
    registrar_auditoria(db, cliente.id, "CRIAR_PEDIDO", "pedido", str(pedido.id), {"canalPedido": entrada.canalPedido.value, "total": str(total)})
    db.commit()
    return carregar_pedido(db, pedido.id)


def carregar_pedido(db: Session, pedido_id: int) -> Pedido | None:
    stmt = (
        select(Pedido)
        .options(joinedload(Pedido.itens).joinedload(ItemPedido.produto), joinedload(Pedido.pagamento))
        .where(Pedido.id == pedido_id)
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def processar_pagamento(db: Session, pedido: Pedido, resultado: StatusPagamento, usuario_id: int) -> Pagamento:
    pagamento = pedido.pagamento
    if pagamento is None:
        pagamento = Pagamento(pedido_id=pedido.id, provedor="MOCK")
        db.add(pagamento)
    pagamento.status = resultado.value
    pagamento.referencia_externa = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
    pagamento.payload_retorno = json.dumps({"resultado": resultado.value, "provedor": "MOCK"})
    pagamento.processado_em = datetime.now(timezone.utc)
    if resultado == StatusPagamento.APROVADO:
        pedido.status = StatusPedido.PAGO.value
        cliente = db.get(Usuario, pedido.cliente_id)
        if cliente and cliente.consentimento_fidelidade:
            conta = db.scalar(select(Fidelidade).where(Fidelidade.usuario_id == cliente.id))
            if not conta:
                conta = Fidelidade(usuario_id=cliente.id, pontos=0)
                db.add(conta)
            conta.pontos += int(Decimal(pedido.total) // Decimal("10"))
            conta.atualizado_em = datetime.now(timezone.utc)
    else:
        pedido.status = StatusPedido.PAGAMENTO_RECUSADO.value
        for item in pedido.itens:
            estoque = db.scalar(select(Estoque).where(Estoque.unidade_id == pedido.unidade_id, Estoque.produto_id == item.produto_id))
            if estoque:
                estoque.quantidade += item.quantidade
                estoque.atualizado_em = datetime.now(timezone.utc)
    pedido.updated_at = datetime.now(timezone.utc)
    registrar_auditoria(db, usuario_id, "PROCESSAR_PAGAMENTO", "pedido", str(pedido.id), {"resultado": resultado.value})
    db.commit()
    db.refresh(pagamento)
    return pagamento
