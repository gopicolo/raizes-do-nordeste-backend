from tests.conftest import login


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def pedido_valido(canal="APP", produto=1, quantidade=1):
    return {"unidadeId": 1, "canalPedido": canal, "itens": [{"produtoId": produto, "quantidade": quantidade}], "formaPagamento": "MOCK"}


def test_t01_login_valido(client):
    r = client.post("/auth/login", json={"email": "cliente@teste.local", "senha": "Cliente@123"})
    assert r.status_code == 200
    assert r.json()["accessToken"]
    assert r.json()["user"]["perfil"] == "CLIENTE"


def test_t02_acesso_sem_token(client):
    r = client.get("/pedidos")
    assert r.status_code == 401
    assert r.json()["error"] == "NAO_AUTENTICADO"


def test_t03_perfil_sem_permissao(client, token_cozinha):
    r = client.post("/estoque/movimentacoes", headers=auth(token_cozinha), json={"unidadeId":1,"produtoId":1,"quantidade":5,"motivo":"reposição"})
    assert r.status_code == 403
    assert r.json()["error"] == "SEM_PERMISSAO"


def test_t04_canal_obrigatorio(client, token_cliente):
    body = pedido_valido(); body.pop("canalPedido")
    r = client.post("/pedidos", headers=auth(token_cliente), json=body)
    assert r.status_code == 422
    assert r.json()["error"] == "VALIDACAO_INVALIDA"


def test_t05_quantidade_invalida(client, token_cliente):
    r = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido(quantidade=0))
    assert r.status_code == 422


def test_t06_pedido_com_itens_validos(client, token_cliente):
    r = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido("TOTEM"))
    assert r.status_code == 201
    assert r.json()["status"] == "AGUARDANDO_PAGAMENTO"
    assert r.json()["canalPedido"] == "TOTEM"
    assert r.json()["total"] == 20.0


def test_t07_produto_inexistente(client, token_cliente):
    r = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido(produto=999))
    assert r.status_code == 404
    assert r.json()["error"] == "PRODUTO_NAO_ENCONTRADO"


def test_t08_estoque_insuficiente(client, token_cliente):
    r = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido(produto=2, quantidade=2))
    assert r.status_code == 409
    assert r.json()["error"] == "ESTOQUE_INSUFICIENTE"


def test_t09_pagamento_aprovado(client, token_cliente):
    pedido = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido()).json()
    r = client.post(f"/pagamentos/{pedido['id']}/processar", headers=auth(token_cliente), json={"resultado":"APROVADO"})
    assert r.status_code == 200
    assert r.json()["statusPagamento"] == "APROVADO"
    assert r.json()["statusPedido"] == "PAGO"
    saldo = client.get("/fidelidade/saldo", headers=auth(token_cliente)).json()
    assert saldo["saldoPontos"] >= 2


def test_t10_pagamento_recusado_devolve_estoque(client, token_cliente):
    antes = client.get("/estoque/unidades/1", headers=auth(token_cliente)).json()[0]["quantidade"]
    pedido = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido()).json()
    durante = client.get("/estoque/unidades/1", headers=auth(token_cliente)).json()[0]["quantidade"]
    assert durante == antes - 1
    r = client.post(f"/pagamentos/{pedido['id']}/processar", headers=auth(token_cliente), json={"resultado":"RECUSADO"})
    assert r.status_code == 200
    assert r.json()["statusPedido"] == "PAGAMENTO_RECUSADO"
    depois = client.get("/estoque/unidades/1", headers=auth(token_cliente)).json()[0]["quantidade"]
    assert depois == antes


def test_t11_auditoria_registra_acao_sensivel(client, token_cliente, token_admin):
    pedido = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido()).json()
    client.post(f"/pagamentos/{pedido['id']}/processar", headers=auth(token_cliente), json={"resultado":"APROVADO"})
    r = client.get("/auditoria", headers=auth(token_admin))
    assert r.status_code == 200
    acoes = {x["acao"] for x in r.json()}
    assert "CRIAR_PEDIDO" in acoes
    assert "PROCESSAR_PAGAMENTO" in acoes


def test_t12_filtro_por_canal(client, token_cliente):
    client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido("APP"))
    client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido("WEB"))
    r = client.get("/pedidos?canalPedido=WEB", headers=auth(token_cliente))
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["canalPedido"] == "WEB"


def test_t13_fluxo_cozinha_status(client, token_cliente, token_cozinha):
    pedido = client.post("/pedidos", headers=auth(token_cliente), json=pedido_valido()).json()
    client.post(f"/pagamentos/{pedido['id']}/processar", headers=auth(token_cliente), json={"resultado":"APROVADO"})
    r1 = client.patch(f"/pedidos/{pedido['id']}/status", headers=auth(token_cozinha), json={"status":"EM_PREPARO"})
    assert r1.status_code == 200
    r2 = client.patch(f"/pedidos/{pedido['id']}/status", headers=auth(token_cozinha), json={"status":"PRONTO"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "PRONTO"


def test_t14_itens_repetidos_nao_ultrapassam_estoque(client, token_cliente):
    antes = client.get('/estoque/unidades/1', headers=auth(token_cliente)).json()
    body = pedido_valido(produto=2)
    body['itens'].append({'produtoId': 2, 'quantidade': 1})
    resposta = client.post('/pedidos', headers=auth(token_cliente), json=body)
    assert resposta.status_code == 409
    depois = client.get('/estoque/unidades/1', headers=auth(token_cliente)).json()
    assert antes == depois
    assert client.get('/pedidos', headers=auth(token_cliente)).json()['items'] == []
