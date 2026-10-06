from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import exigir_perfis, usuario_atual
from app.application.audit import registrar_auditoria
from app.domain.enums import Perfil
from app.domain.schemas import MovimentoEstoqueEntrada
from app.infrastructure.database import get_db
from app.infrastructure.models import Estoque, Produto, Unidade, Usuario

router = APIRouter(prefix="/estoque", tags=["Estoque"])


@router.get("/unidades/{unidade_id}")
def saldo(unidade_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    if not db.get(Unidade, unidade_id):
        raise HTTPException(status_code=404, detail={"error": "UNIDADE_NAO_ENCONTRADA", "message": "Unidade não encontrada.", "details": []})
    rows = db.execute(select(Estoque, Produto).join(Produto, Produto.id == Estoque.produto_id).where(Estoque.unidade_id == unidade_id).order_by(Produto.id)).all()
    return [{"produtoId": p.id, "produto": p.nome, "quantidade": e.quantidade} for e, p in rows]


@router.post("/movimentacoes", status_code=201)
def movimentar(entrada: MovimentoEstoqueEntrada, usuario: Usuario = Depends(exigir_perfis(Perfil.GERENTE.value, Perfil.ADMIN.value)), db: Session = Depends(get_db)):
    if not db.get(Unidade, entrada.unidadeId) or not db.get(Produto, entrada.produtoId):
        raise HTTPException(status_code=404, detail={"error": "RECURSO_NAO_ENCONTRADO", "message": "Unidade ou produto não encontrado.", "details": []})
    estoque = db.scalar(select(Estoque).where(Estoque.unidade_id == entrada.unidadeId, Estoque.produto_id == entrada.produtoId))
    if not estoque:
        estoque = Estoque(unidade_id=entrada.unidadeId, produto_id=entrada.produtoId, quantidade=0)
        db.add(estoque)
        db.flush()
    novo = estoque.quantidade + entrada.quantidade
    if novo < 0:
        raise HTTPException(status_code=409, detail={"error": "SALDO_NEGATIVO", "message": "Movimentação deixaria o estoque negativo.", "details": []})
    estoque.quantidade = novo
    estoque.atualizado_em = datetime.now(timezone.utc)
    registrar_auditoria(db, usuario.id, "MOVIMENTAR_ESTOQUE", "estoque", str(estoque.id), {"quantidade": entrada.quantidade, "motivo": entrada.motivo})
    db.commit()
    return {"unidadeId": entrada.unidadeId, "produtoId": entrada.produtoId, "saldoAtual": estoque.quantidade}
