"""estrutura inicial
Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("email", sa.String(180), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("perfil", sa.String(20), nullable=False),
        sa.Column("consentimento_fidelidade", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"])
    op.create_table("unidades",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("cidade", sa.String(100), nullable=False), sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("cozinha_completa", sa.Boolean(), nullable=False), sa.Column("ativa", sa.Boolean(), nullable=False))
    op.create_table("produtos",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=False), sa.Column("preco", sa.Numeric(10,2), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False))
    op.create_table("promocoes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=False), sa.Column("percentual_desconto", sa.Integer(), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False))
    op.create_table("estoques",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("unidade_id", sa.Integer(), sa.ForeignKey("unidades.id"), nullable=False),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False), sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("unidade_id","produto_id", name="uq_estoque_unidade_produto"))
    op.create_index("ix_estoques_unidade_id", "estoques", ["unidade_id"])
    op.create_index("ix_estoques_produto_id", "estoques", ["produto_id"])
    op.create_table("fidelidade",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False, unique=True),
        sa.Column("pontos", sa.Integer(), nullable=False), sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False))
    op.create_table("pedidos",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("unidade_id", sa.Integer(), sa.ForeignKey("unidades.id"), nullable=False), sa.Column("canal_pedido", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("total", sa.Numeric(10,2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_pedidos_cliente_id", "pedidos", ["cliente_id"])
    op.create_index("ix_pedidos_unidade_id", "pedidos", ["unidade_id"])
    op.create_index("ix_pedidos_canal_pedido", "pedidos", ["canal_pedido"])
    op.create_index("ix_pedidos_status", "pedidos", ["status"])
    op.create_table("itens_pedido",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("pedido_id", sa.Integer(), sa.ForeignKey("pedidos.id"), nullable=False),
        sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False), sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("preco_unitario", sa.Numeric(10,2), nullable=False))
    op.create_index("ix_itens_pedido_pedido_id", "itens_pedido", ["pedido_id"])
    op.create_table("pagamentos",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("pedido_id", sa.Integer(), sa.ForeignKey("pedidos.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("provedor", sa.String(30), nullable=False),
        sa.Column("referencia_externa", sa.String(80)), sa.Column("payload_retorno", sa.Text()), sa.Column("processado_em", sa.DateTime(timezone=True)))
    op.create_table("auditoria",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("acao", sa.String(80), nullable=False), sa.Column("recurso", sa.String(80), nullable=False),
        sa.Column("recurso_id", sa.String(60)), sa.Column("detalhes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for table in ["auditoria","pagamentos","itens_pedido","pedidos","fidelidade","estoques","promocoes","produtos","unidades","usuarios"]:
        op.drop_table(table)
