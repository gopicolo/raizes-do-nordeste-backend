from sqlalchemy import select
from app.domain.enums import Perfil
from app.infrastructure.database import Base, SessionLocal, engine
from app.infrastructure.models import Estoque, Fidelidade, Produto, Promocao, Unidade, Usuario
from app.infrastructure.security import hash_senha

Base.metadata.create_all(bind=engine)

def run():
    db = SessionLocal()
    try:
        if db.scalar(select(Usuario).limit(1)):
            if not db.scalar(select(Usuario).where(Usuario.email == "atendente@raizes.local")):
                db.add(Usuario(nome="Atendente Demonstração", email="atendente@raizes.local",
                               senha_hash=hash_senha("Atendente@123"),
                               perfil=Perfil.ATENDENTE.value, consentimento_fidelidade=False))
                db.commit()
                print("Conta de demonstração ATENDENTE adicionada.")
            else:
                print("Seed já aplicado; nenhum dado alterado.")
            return
        usuarios = [
            Usuario(nome="Cliente Demonstração", email="cliente@raizes.local", senha_hash=hash_senha("Cliente@123"), perfil=Perfil.CLIENTE.value, consentimento_fidelidade=True),
            Usuario(nome="Gerente Demonstração", email="gerente@raizes.local", senha_hash=hash_senha("Gerente@123"), perfil=Perfil.GERENTE.value, consentimento_fidelidade=False),
            Usuario(nome="Cozinha Demonstração", email="cozinha@raizes.local", senha_hash=hash_senha("Cozinha@123"), perfil=Perfil.COZINHA.value, consentimento_fidelidade=False),
            Usuario(nome="Admin Demonstração", email="admin@raizes.local", senha_hash=hash_senha("Admin@123"), perfil=Perfil.ADMIN.value, consentimento_fidelidade=False),
        ]
        usuarios.append(Usuario(nome="Atendente Demonstração", email="atendente@raizes.local",
                                senha_hash=hash_senha("Atendente@123"),
                                perfil=Perfil.ATENDENTE.value, consentimento_fidelidade=False))
        db.add_all(usuarios)
        db.flush()
        db.add(Fidelidade(usuario_id=usuarios[0].id, pontos=20))
        unidades = [
            Unidade(nome="Raízes do Nordeste - Recife Centro", cidade="Recife", uf="PE", cozinha_completa=True),
            Unidade(nome="Raízes do Nordeste - João Pessoa", cidade="João Pessoa", uf="PB", cozinha_completa=False),
        ]
        produtos = [
            Produto(nome="Cuscuz com Carne de Sol", descricao="Cuscuz de milho, carne de sol e queijo coalho.", preco=24.90),
            Produto(nome="Tapioca de Queijo Coalho", descricao="Tapioca recheada com queijo coalho.", preco=16.50),
            Produto(nome="Bolo de Macaxeira", descricao="Fatia de bolo de macaxeira tradicional.", preco=9.90),
            Produto(nome="Suco de Cajá", descricao="Suco regional de cajá, 400 ml.", preco=8.50),
        ]
        db.add_all(unidades + produtos)
        db.flush()
        saldos = {
            (unidades[0].id, produtos[0].id): 30,
            (unidades[0].id, produtos[1].id): 20,
            (unidades[0].id, produtos[2].id): 15,
            (unidades[0].id, produtos[3].id): 40,
            (unidades[1].id, produtos[0].id): 5,
            (unidades[1].id, produtos[1].id): 8,
            (unidades[1].id, produtos[2].id): 0,
            (unidades[1].id, produtos[3].id): 12,
        }
        db.add_all([Estoque(unidade_id=u, produto_id=p, quantidade=q) for (u,p),q in saldos.items()])
        db.add(Promocao(nome="Semana Nordestina", descricao="10% de desconto documentado para campanhas elegíveis; aplicação futura no motor de promoções.", percentual_desconto=10, ativa=True))
        db.commit()
        print("Seed aplicado com sucesso.")
        print("cliente@raizes.local / Cliente@123")
        print("gerente@raizes.local / Gerente@123")
        print("cozinha@raizes.local / Cozinha@123")
        print("admin@raizes.local / Admin@123")
        print("atendente@raizes.local / Atendente@123")
    finally:
        db.close()

if __name__ == "__main__":
    run()
