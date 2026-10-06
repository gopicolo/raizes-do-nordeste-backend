from datetime import datetime, timezone
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routers import auth, catalogo, estoque, fidelidade, pagamentos, pedidos

app = FastAPI(
    title="Raízes do Nordeste API",
    version="1.0.0",
    description="API acadêmica para a rede Raízes do Nordeste, com multicanalidade, estoque por unidade, pedido, pagamento mock, fidelização, segurança e auditoria.",
    contact={"name": "Projeto Multidisciplinar - Trilha Back-End"},
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def erro_payload(request: Request, error: str, message: str, details=None):
    return {
        "error": error,
        "message": message,
        "details": details or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "requestId": getattr(request.state, "request_id", None),
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=erro_payload(request, exc.detail.get("error", "ERRO_HTTP"), exc.detail.get("message", "Falha na requisição."), exc.detail.get("details", [])))
    return JSONResponse(status_code=exc.status_code, content=erro_payload(request, "ERRO_HTTP", str(exc.detail)))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", []) if x != "body"]
        details.append({"field": ".".join(loc), "issue": e.get("msg", "valor inválido")})
    return JSONResponse(status_code=422, content=erro_payload(request, "VALIDACAO_INVALIDA", "Um ou mais campos são inválidos.", details))


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(catalogo.router)
app.include_router(pedidos.router)
app.include_router(pagamentos.router)
app.include_router(estoque.router)
app.include_router(fidelidade.router)
