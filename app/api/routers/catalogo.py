from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.infrastructure.database import get_db
from app.infrastructure.models import Estoque, Produto, Promocao, Unidade

router = APIRouter(tags=["Catálogo"])


@router.get("/unidades")
def listar_unidades(db: Session = Depends(get_db)):
    dados = db.scalars(select(Unidade).where(Unidade.ativa.is_(True)).order_by(Unidade.id)).all()
    return [{"id": u.id, "nome": u.nome, "cidade": u.cidade, "uf": u.uf, "cozinhaCompleta": u.cozinha_completa} for u in dados]


@router.get("/produtos")
def listar_produtos(unidadeId: int = Query(..., description="Unidade cujo cardápio/estoque será consultado"), page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    unidade = db.get(Unidade, unidadeId)
    if not unidade or not unidade.ativa:
        raise HTTPException(status_code=404, detail={"error": "UNIDADE_NAO_ENCONTRADA", "message": "Unidade inexistente ou inativa.", "details": []})
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    stmt = (
        select(Produto, Estoque)
        .join(Estoque, (Estoque.produto_id == Produto.id) & (Estoque.unidade_id == unidadeId), isouter=True)
        .where(Produto.ativo.is_(True))
        .order_by(Produto.id)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return {
        "page": page,
        "limit": limit,
        "items": [
            {"id": p.id, "nome": p.nome, "descricao": p.descricao, "preco": float(p.preco), "disponivel": bool(e and e.quantidade > 0), "quantidadeEstoque": e.quantidade if e else 0}
            for p, e in rows
        ],
    }


@router.get("/promocoes")
def listar_promocoes(db: Session = Depends(get_db)):
    promos = db.scalars(select(Promocao).where(Promocao.ativa.is_(True)).order_by(Promocao.id)).all()
    return [{"id": p.id, "nome": p.nome, "descricao": p.descricao, "percentualDesconto": p.percentual_desconto} for p in promos]
