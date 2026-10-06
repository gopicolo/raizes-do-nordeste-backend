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
    novo_status = (StatusPedido.PAGO if resultado == StatusPagamento.APROVADO
                   else StatusPedido.PAGAMENTO_RECUSADO)
    # Disputa a mesma transição que o cancelamento, antes de qualquer efeito.
    transicao = db.execute(
        update(Pedido)
        .where(Pedido.id == pedido.id,
               Pedido.status == StatusPedido.AGUARDANDO_PAGAMENTO.value)
        .values(status=novo_status.value, updated_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    if transicao.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "error": "PEDIDO_NAO_AGUARDA_PAGAMENTO",
            "message": "O pedido foi cancelado ou seu pagamento já foi processado.",
            "details": [],
        })
    pagamento = pedido.pagamento
    if pagamento is None:
        pagamento = Pagamento(pedido_id=pedido.id, provedor="MOCK")
        db.add(pagamento)
    pagamento.status = resultado.value
    pagamento.referencia_externa = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
    pagamento.payload_retorno = json.dumps({"resultado": resultado.value, "provedor": "MOCK"})
    pagamento.processado_em = datetime.now(timezone.utc)
    if resultado == StatusPagamento.APROVADO:
        cliente = db.get(Usuario, pedido.cliente_id)
        if cliente and cliente.consentimento_fidelidade:
            conta = db.scalar(select(Fidelidade).where(Fidelidade.usuario_id == cliente.id))
            if not conta:
                conta = Fidelidade(usuario_id=cliente.id, pontos=0)
                db.add(conta)
                db.flush()
            db.execute(
                update(Fidelidade).where(Fidelidade.id == conta.id)
                .values(pontos=Fidelidade.pontos + int(Decimal(pedido.total) // Decimal("10")),
                        atualizado_em=datetime.now(timezone.utc))
                .execution_options(synchronize_session=False)
            )
    else:
        devolver_estoque(db, pedido)
    pedido.updated_at = datetime.now(timezone.utc)
    registrar_auditoria(db, usuario_id, "PROCESSAR_PAGAMENTO", "pedido", str(pedido.id), {"resultado": resultado.value})
    db.commit()
    db.refresh(pagamento)
    return pagamento


def devolver_estoque(db: Session, pedido: Pedido) -> None:
    for item in pedido.itens:
        devolucao = db.execute(
            update(Estoque)
            .where(Estoque.unidade_id == pedido.unidade_id,
                   Estoque.produto_id == item.produto_id)
            .values(quantidade=Estoque.quantidade + item.quantidade,
                    atualizado_em=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
        if devolucao.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail={
                "error": "ESTOQUE_NAO_ENCONTRADO",
                "message": "Não foi possível devolver a reserva de estoque.",
                "details": [],
            })


def alterar_status_pedido(db: Session, pedido: Pedido, status: StatusPedido,
                         usuario_id: int) -> Pedido:
    permitidos = {
        StatusPedido.AGUARDANDO_PAGAMENTO.value: {StatusPedido.CANCELADO},
        StatusPedido.PAGO.value: {StatusPedido.EM_PREPARO, StatusPedido.CANCELADO},
        StatusPedido.EM_PREPARO.value: {StatusPedido.PRONTO, StatusPedido.CANCELADO},
        StatusPedido.PRONTO.value: {StatusPedido.ENTREGUE},
    }
    anterior = pedido.status
    if status not in permitidos.get(anterior, set()):
        raise HTTPException(status_code=409, detail={
            "error": "TRANSICAO_STATUS_INVALIDA",
            "message": f"Não é permitido mudar de {anterior} para {status.value}.",
            "details": [],
        })
    alteracao = db.execute(
        update(Pedido).where(Pedido.id == pedido.id, Pedido.status == anterior)
        .values(status=status.value, updated_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    if alteracao.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "error": "PEDIDO_ALTERADO",
            "message": "O pedido foi alterado por outra operação. Consulte-o novamente.",
            "details": [],
        })
    if status == StatusPedido.CANCELADO:
        devolver_estoque(db, pedido)
    registrar_auditoria(db, usuario_id, "ALTERAR_STATUS", "pedido", str(pedido.id),
                       {"statusAnterior": anterior, "novoStatus": status.value})
    db.commit()
    return carregar_pedido(db, pedido.id)


def resgatar_pontos(db: Session, usuario: Usuario, pontos: int) -> dict:
    if not usuario.consentimento_fidelidade:
        raise HTTPException(status_code=403, detail={
            "error": "FIDELIDADE_SEM_CONSENTIMENTO",
            "message": "É necessário aderir ao programa de fidelidade.",
            "details": [],
        })
    debito = db.execute(
        update(Fidelidade)
        .where(Fidelidade.usuario_id == usuario.id, Fidelidade.pontos >= pontos)
        .values(pontos=Fidelidade.pontos - pontos, atualizado_em=datetime.now(timezone.utc))
        .returning(Fidelidade.pontos)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if debito is None:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "error": "PONTOS_INSUFICIENTES",
            "message": "Saldo de pontos insuficiente para o resgate.",
            "details": [],
        })
    registrar_auditoria(db, usuario.id, "RESGATAR_PONTOS", "fidelidade", str(usuario.id),
                       {"pontosResgatados": pontos, "saldoPontos": debito})
    db.commit()
    return {"pontosResgatados": pontos, "saldoPontos": debito}
