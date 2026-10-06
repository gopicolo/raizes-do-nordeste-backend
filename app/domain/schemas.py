from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .enums import CanalPedido, Perfil, StatusPedido, StatusPagamento


class UsuarioCadastro(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    senha: str = Field(min_length=8, max_length=72)
    consentimentoFidelidade: bool = False

    @field_validator("email")
    @classmethod
    def valida_email(cls, v: str):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("e-mail inválido")
        return v


class UsuarioSaida(BaseModel):
    id: int
    nome: str
    email: str
    perfil: Perfil
    consentimentoFidelidade: bool


class LoginEntrada(BaseModel):
    email: str
    senha: str


class TokenSaida(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    expiresIn: int
    user: dict


class UnidadeSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    cidade: str
    uf: str
    cozinha_completa: bool


class ProdutoSaida(BaseModel):
    id: int
    nome: str
    descricao: str
    preco: Decimal
    disponivel: bool
    quantidadeEstoque: int


class ItemPedidoEntrada(BaseModel):
    produtoId: int
    quantidade: int = Field(gt=0, le=50)


class PedidoCriacao(BaseModel):
    unidadeId: int
    canalPedido: CanalPedido
    itens: list[ItemPedidoEntrada] = Field(min_length=1)
    formaPagamento: str = Field(default="MOCK")

    @field_validator("formaPagamento")
    @classmethod
    def apenas_mock(cls, v: str):
        if v.upper() != "MOCK":
            raise ValueError("somente MOCK é aceito nesta atividade")
        return "MOCK"


class ItemPedidoSaida(BaseModel):
    produtoId: int
    nome: str
    quantidade: int
    precoUnitario: Decimal


class PedidoSaida(BaseModel):
    id: int
    clienteId: int
    unidadeId: int
    canalPedido: CanalPedido
    status: StatusPedido
    total: Decimal
    itens: list[ItemPedidoSaida]
    createdAt: datetime


class PagamentoEntrada(BaseModel):
    resultado: StatusPagamento

    @field_validator("resultado")
    @classmethod
    def valida_resultado(cls, v: StatusPagamento):
        if v == StatusPagamento.PENDENTE:
            raise ValueError("use APROVADO ou RECUSADO")
        return v


class PagamentoSaida(BaseModel):
    pedidoId: int
    statusPagamento: StatusPagamento
    statusPedido: StatusPedido
    referenciaExterna: str


class StatusPedidoEntrada(BaseModel):
    status: StatusPedido


class MovimentoEstoqueEntrada(BaseModel):
    unidadeId: int
    produtoId: int
    quantidade: int
    motivo: str = Field(min_length=3, max_length=120)


class FidelidadeSaida(BaseModel):
    saldoPontos: int
    consentimento: bool


class ResgateFidelidadeEntrada(BaseModel):
    pontos: int = Field(gt=0, le=2147483647, strict=True)
