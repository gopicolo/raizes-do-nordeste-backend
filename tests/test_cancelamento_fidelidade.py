from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def criar(client, token, quantidade=1, repetido=False):
    itens = [{"produtoId": 1, "quantidade": quantidade}]
    if repetido:
        itens.append({"produtoId": 1, "quantidade": 1})
    r = client.post('/pedidos', headers=auth(token), json={
        'unidadeId': 1, 'canalPedido': 'APP', 'itens': itens,
    })
    assert r.status_code == 201, r.text
    return r.json()['id']


def estoque(client, token):
    return client.get('/estoque/unidades/1', headers=auth(token)).json()[0]['quantidade']


def pagar(client, token, pedido):
    return client.post(f'/pagamentos/{pedido}/processar', headers=auth(token),
                       json={'resultado': 'APROVADO'})


def cancelar(client, token, pedido):
    return client.patch(f'/pedidos/{pedido}/status', headers=auth(token),
                        json={'status': 'CANCELADO'})


@pytest.mark.parametrize('estado', ['AGUARDANDO_PAGAMENTO', 'PAGO', 'EM_PREPARO'])
def test_cancelar_devolve_todos_itens_uma_vez(client, token_cliente, token_gerente, estado):
    antes = estoque(client, token_cliente)
    pedido = criar(client, token_cliente, repetido=True)
    if estado != 'AGUARDANDO_PAGAMENTO':
        assert pagar(client, token_cliente, pedido).status_code == 200
    if estado == 'EM_PREPARO':
        r = client.patch(f'/pedidos/{pedido}/status', headers=auth(token_gerente),
                         json={'status': estado})
        assert r.status_code == 200
    assert estoque(client, token_cliente) == antes - 2
    assert cancelar(client, token_gerente, pedido).status_code == 200
    assert estoque(client, token_cliente) == antes
    assert cancelar(client, token_gerente, pedido).status_code == 409
    assert pagar(client, token_cliente, pedido).status_code == 409
    assert estoque(client, token_cliente) == antes


def test_cliente_cancela_proprio_pendente_com_auditoria(client, token_cliente, token_admin):
    pedido = criar(client, token_cliente)
    assert cancelar(client, token_cliente, pedido).status_code == 200
    assert pagar(client, token_cliente, pedido).status_code == 409
    registros = client.get('/auditoria', headers=auth(token_admin)).json()
    assert any(r['acao'] == 'ALTERAR_STATUS' and r['recursoId'] == str(pedido)
               and 'CANCELADO' in r['detalhes'] for r in registros)


def test_cliente_nao_cancela_pedido_de_outro_nem_pago(client, token_cliente):
    pedido = criar(client, token_cliente)
    r = client.post('/auth/cadastro', json={
        'nome': 'Outro Cliente', 'email': 'outro@teste.local', 'senha': 'Outra@123',
    })
    assert r.status_code == 201
    outro = client.post('/auth/login', json={
        'email': 'outro@teste.local', 'senha': 'Outra@123',
    }).json()['accessToken']
    assert cancelar(client, outro, pedido).status_code == 403
    assert pagar(client, token_cliente, pedido).status_code == 200
    assert cancelar(client, token_cliente, pedido).status_code == 403
    assert estoque(client, token_cliente) == 9


def test_pedido_pronto_nao_pode_ser_cancelado(client, token_cliente, token_gerente):
    pedido = criar(client, token_cliente)
    assert pagar(client, token_cliente, pedido).status_code == 200
    for estado in ['EM_PREPARO', 'PRONTO']:
        assert client.patch(f'/pedidos/{pedido}/status', headers=auth(token_gerente),
                            json={'status': estado}).status_code == 200
    assert cancelar(client, token_gerente, pedido).status_code == 409
    assert estoque(client, token_cliente) == 9


def test_cancelamentos_concorrentes_nao_duplicam_estoque(client, token_cliente, token_gerente):
    pedido = criar(client, token_cliente)
    barreira = Barrier(2)
    def executar(_):
        barreira.wait()
        return cancelar(client, token_gerente, pedido).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(executar, range(2)))
    assert sorted(resultados) == [200, 409]
    assert estoque(client, token_cliente) == 10


def test_pagamento_e_cancelamento_nao_aplicam_efeitos_em_duplicidade(client, token_cliente):
    pedido = criar(client, token_cliente)
    barreira = Barrier(2)
    def executar(pagamento):
        barreira.wait()
        return (pagar if pagamento else cancelar)(client, token_cliente, pedido).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(executar, [True, False]))
    estado = client.get(f'/pedidos/{pedido}', headers=auth(token_cliente)).json()['status']
    saldo = client.get('/fidelidade/saldo', headers=auth(token_cliente)).json()['saldoPontos']
    assert resultados.count(200) == 1
    assert all(c in (200, 403, 409) for c in resultados)
    if estado == 'CANCELADO':
        assert estoque(client, token_cliente) == 10 and saldo == 0
    else:
        assert estado == 'PAGO'
        assert estoque(client, token_cliente) == 9 and saldo == 2


def test_resgate_debita_somente_saldo_proprio_e_registra_auditoria(client, token_cliente, token_admin):
    pedido = criar(client, token_cliente)
    assert pagar(client, token_cliente, pedido).status_code == 200
    r = client.post('/fidelidade/resgatar', headers=auth(token_cliente), json={'pontos': 1})
    assert r.status_code == 200
    assert r.json() == {'pontosResgatados': 1, 'saldoPontos': 1}
    assert client.get('/fidelidade/saldo', headers=auth(token_cliente)).json()['saldoPontos'] == 1
    r = client.post('/fidelidade/resgatar', headers=auth(token_cliente), json={'pontos': 2})
    assert r.status_code == 409 and r.json()['error'] == 'PONTOS_INSUFICIENTES'
    registros = client.get('/auditoria', headers=auth(token_admin)).json()
    assert len([r for r in registros if r['acao'] == 'RESGATAR_PONTOS']) == 1


@pytest.mark.parametrize('pontos', [0, -1, 1.5, True, '2'])
def test_resgate_rejeita_quantidade_invalida(client, token_cliente, pontos):
    r = client.post('/fidelidade/resgatar', headers=auth(token_cliente), json={'pontos': pontos})
    assert r.status_code == 422


def test_resgate_exige_login_consentimento_e_saldo(client, token_cliente, token_gerente):
    assert client.post('/fidelidade/resgatar', json={'pontos': 1}).status_code == 401
    assert client.post('/fidelidade/resgatar', headers=auth(token_gerente),
                       json={'pontos': 1}).status_code == 403
    assert client.post('/fidelidade/resgatar', headers=auth(token_cliente),
                       json={'pontos': 1}).status_code == 409


def test_resgates_concorrentes_nao_deixam_saldo_negativo(client, token_cliente):
    pedido = criar(client, token_cliente)
    assert pagar(client, token_cliente, pedido).status_code == 200
    barreira = Barrier(2)
    def executar(_):
        barreira.wait()
        return client.post('/fidelidade/resgatar', headers=auth(token_cliente),
                           json={'pontos': 2}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(executar, range(2)))
    assert sorted(resultados) == [200, 409]
    assert client.get('/fidelidade/saldo', headers=auth(token_cliente)).json()['saldoPontos'] == 0
