import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

JWT_SECRET = os.getenv("JWT_SECRET", "troque-esta-chave-em-producao")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))


def hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verificar_senha(senha: str, armazenada: str) -> bool:
    try:
        algoritmo, rounds, salt_b64, digest_b64 = armazenada.split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        esperado = base64.b64decode(digest_b64)
        atual = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, int(rounds))
        return hmac.compare_digest(atual, esperado)
    except Exception:
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def criar_token(payload: dict[str, Any]) -> tuple[str, int]:
    expires_in = JWT_EXPIRE_MINUTES * 60
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + expires_in}
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(body, separators=(',', ':')).encode())}"
    assinatura = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(assinatura)}", expires_in


def decodificar_token(token: str) -> dict[str, Any]:
    try:
        h, p, s = token.split(".")
        signing_input = f"{h}.{p}"
        assinatura = _b64url_decode(s)
        esperada = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(assinatura, esperada):
            raise ValueError("assinatura inválida")
        payload = json.loads(_b64url_decode(p))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expirado")
        return payload
    except Exception as exc:
        raise ValueError("token inválido") from exc
