from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(String(20), nullable=False, default="CLIENTE")
    consentimento_fidelidade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Unidade(Base):
    __tablename__ = "unidades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    cidade: Mapped[str] = mapped_column(String(100), nullable=False)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)
    cozinha_completa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Produto(Base):
    __tablename__ = "produtos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    preco: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Estoque(Base):
    __tablename__ = "estoques"
    __table_args__ = (UniqueConstraint("unidade_id", "produto_id", name="uq_estoque_unidade_produto"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"), nullable=False, index=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False, index=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    unidade: Mapped[Unidade] = relationship()
    produto: Mapped[Produto] = relationship()


class Pedido(Base):
    __tablename__ = "pedidos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"), nullable=False, index=True)
    canal_pedido: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="AGUARDANDO_PAGAMENTO", index=True)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    cliente: Mapped[Usuario] = relationship()
    unidade: Mapped[Unidade] = relationship()
    itens: Mapped[list["ItemPedido"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")
    pagamento: Mapped["Pagamento | None"] = relationship(back_populates="pedido", uselist=False, cascade="all, delete-orphan")


class ItemPedido(Base):
    __tablename__ = "itens_pedido"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), nullable=False, index=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    preco_unitario: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    pedido: Mapped[Pedido] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship()


class Pagamento(Base):
    __tablename__ = "pagamentos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDENTE")
    provedor: Mapped[str] = mapped_column(String(30), nullable=False, default="MOCK")
    referencia_externa: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload_retorno: Mapped[str | None] = mapped_column(Text, nullable=True)
    processado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pedido: Mapped[Pedido] = relationship(back_populates="pagamento")


class Fidelidade(Base):
    __tablename__ = "fidelidade"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, unique=True)
    pontos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    usuario: Mapped[Usuario] = relationship()


class Promocao(Base):
    __tablename__ = "promocoes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    percentual_desconto: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    acao: Mapped[str] = mapped_column(String(80), nullable=False)
    recurso: Mapped[str] = mapped_column(String(80), nullable=False)
    recurso_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    detalhes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
