from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain.enums import Perfil
from app.domain.schemas import LoginEntrada, TokenSaida, UsuarioCadastro
from app.infrastructure.database import get_db
from app.infrastructure.models import Fidelidade, Usuario
from app.infrastructure.security import criar_token, hash_senha, verificar_senha
from app.application.audit import registrar_auditoria

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/cadastro", status_code=201)
def cadastro(entrada: UsuarioCadastro, db: Session = Depends(get_db)):
    if db.scalar(select(Usuario).where(Usuario.email == entrada.email)):
        raise HTTPException(status_code=409, detail={"error": "EMAIL_JA_CADASTRADO", "message": "Já existe usuário com este e-mail.", "details": []})
    usuario = Usuario(
        nome=entrada.nome,
        email=entrada.email,
        senha_hash=hash_senha(entrada.senha),
        perfil=Perfil.CLIENTE.value,
        consentimento_fidelidade=entrada.consentimentoFidelidade,
    )
    db.add(usuario)
    db.flush()
    if entrada.consentimentoFidelidade:
        db.add(Fidelidade(usuario_id=usuario.id, pontos=0))
    registrar_auditoria(db, usuario.id, "CADASTRAR_USUARIO", "usuario", str(usuario.id))
    db.commit()
    return {"id": usuario.id, "nome": usuario.nome, "email": usuario.email, "perfil": usuario.perfil, "consentimentoFidelidade": usuario.consentimento_fidelidade}


@router.post("/login", response_model=TokenSaida)
def login(entrada: LoginEntrada, db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.email == entrada.email.strip().lower()))
    if not usuario or not verificar_senha(entrada.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "CREDENCIAIS_INVALIDAS", "message": "E-mail ou senha inválidos.", "details": []})
    token, exp = criar_token({"sub": str(usuario.id), "perfil": usuario.perfil})
    registrar_auditoria(db, usuario.id, "LOGIN", "auth")
    db.commit()
    return {"accessToken": token, "tokenType": "Bearer", "expiresIn": exp, "user": {"id": usuario.id, "nome": usuario.nome, "perfil": usuario.perfil}}
