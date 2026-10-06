from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import exigir_perfis, usuario_atual
from app.application.services import resgatar_pontos
from app.domain.enums import Perfil
from app.domain.schemas import ResgateFidelidadeEntrada
from app.infrastructure.database import get_db
from app.infrastructure.models import Auditoria, Fidelidade, Usuario

router = APIRouter(tags=["Fidelidade e Auditoria"])


@router.get("/fidelidade/saldo")
def saldo_fidelidade(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    if not usuario.consentimento_fidelidade:
        return {"saldoPontos": 0, "consentimento": False, "message": "Usuário não aderiu ao programa de fidelização."}
    conta = db.scalar(select(Fidelidade).where(Fidelidade.usuario_id == usuario.id))
    return {"saldoPontos": conta.pontos if conta else 0, "consentimento": True}


@router.post("/fidelidade/resgatar")
def resgate_fidelidade(entrada: ResgateFidelidadeEntrada, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return resgatar_pontos(db, usuario, entrada.pontos)


@router.get("/auditoria")
def auditoria(usuario: Usuario = Depends(exigir_perfis(Perfil.ADMIN.value, Perfil.GERENTE.value)), db: Session = Depends(get_db)):
    registros = db.scalars(select(Auditoria).order_by(Auditoria.id.desc()).limit(100)).all()
    return [{"id": r.id, "usuarioId": r.usuario_id, "acao": r.acao, "recurso": r.recurso, "recursoId": r.recurso_id, "detalhes": r.detalhes, "createdAt": r.created_at} for r in registros]
