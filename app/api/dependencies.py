from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.infrastructure.database import get_db
from app.infrastructure.models import Usuario
from app.infrastructure.security import decodificar_token

bearer = HTTPBearer(auto_error=False)


def usuario_atual(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if cred is None:
        raise HTTPException(status_code=401, detail={"error": "NAO_AUTENTICADO", "message": "Token Bearer obrigatório.", "details": []})
    try:
        payload = decodificar_token(cred.credentials)
        usuario = db.get(Usuario, int(payload["sub"]))
    except Exception:
        usuario = None
    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=401, detail={"error": "TOKEN_INVALIDO", "message": "Token inválido ou expirado.", "details": []})
    request.state.usuario_id = usuario.id
    return usuario


def exigir_perfis(*perfis: str):
    def dependency(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if usuario.perfil not in perfis:
            raise HTTPException(status_code=403, detail={"error": "SEM_PERMISSAO", "message": "Seu perfil não possui permissão para esta operação.", "details": []})
        return usuario
    return dependency
