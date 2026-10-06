import os
os.environ["DATABASE_URL"] = "sqlite:///./test_raizes.db"
os.environ["JWT_SECRET"] = "segredo-de-teste"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.database import Base, SessionLocal, engine
from app.infrastructure.models import Estoque, Fidelidade, Produto, Promocao, Unidade, Usuario
from app.infrastructure.security import hash_senha
from app.domain.enums import Perfil


@pytest.fixture(autouse=True)
def banco_limpo():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        cliente = Usuario(nome="Cliente Teste", email="cliente@teste.local", senha_hash=hash_senha("Cliente@123"), perfil=Perfil.CLIENTE.value, consentimento_fidelidade=True)
        gerente = Usuario(nome="Gerente Teste", email="gerente@teste.local", senha_hash=hash_senha("Gerente@123"), perfil=Perfil.GERENTE.value)
        cozinha = Usuario(nome="Cozinha Teste", email="cozinha@teste.local", senha_hash=hash_senha("Cozinha@123"), perfil=Perfil.COZINHA.value)
        admin = Usuario(nome="Admin Teste", email="admin@teste.local", senha_hash=hash_senha("Admin@123"), perfil=Perfil.ADMIN.value)
        db.add_all([cliente, gerente, cozinha, admin]); db.flush()
        db.add(Fidelidade(usuario_id=cliente.id, pontos=0))
        unidade = Unidade(nome="Recife Centro", cidade="Recife", uf="PE", cozinha_completa=True, ativa=True)
        produto1 = Produto(nome="Cuscuz", descricao="Cuscuz regional", preco=20.00, ativo=True)
        produto2 = Produto(nome="Tapioca", descricao="Tapioca regional", preco=15.00, ativo=True)
        db.add_all([unidade, produto1, produto2]); db.flush()
        db.add_all([
            Estoque(unidade_id=unidade.id, produto_id=produto1.id, quantidade=10),
            Estoque(unidade_id=unidade.id, produto_id=produto2.id, quantidade=1),
            Promocao(nome="Teste", descricao="Promoção de teste", percentual_desconto=5, ativa=True),
        ])
        db.commit()
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def login(client, email="cliente@teste.local", senha="Cliente@123"):
    r = client.post("/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    return r.json()["accessToken"]


@pytest.fixture
def token_cliente(client):
    return login(client)


@pytest.fixture
def token_gerente(client):
    return login(client, "gerente@teste.local", "Gerente@123")


@pytest.fixture
def token_cozinha(client):
    return login(client, "cozinha@teste.local", "Cozinha@123")


@pytest.fixture
def token_admin(client):
    return login(client, "admin@teste.local", "Admin@123")
