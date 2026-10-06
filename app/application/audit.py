import json
from sqlalchemy.orm import Session
from app.infrastructure.models import Auditoria


def registrar_auditoria(db: Session, usuario_id: int | None, acao: str, recurso: str, recurso_id: str | None = None, detalhes: dict | None = None):
    registro = Auditoria(
        usuario_id=usuario_id,
        acao=acao,
        recurso=recurso,
        recurso_id=recurso_id,
        detalhes=json.dumps(detalhes, ensure_ascii=False) if detalhes else None,
    )
    db.add(registro)
