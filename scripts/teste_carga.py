"""Carga local reproduzível; somente execute contra um banco descartável de teste."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import time

import httpx


async def etapa(client, nome, quantidade, concorrencia, method, path, **kwargs):
    sem = asyncio.Semaphore(concorrencia)
    resultados = []
    async def requisicao(i):
        async with sem:
            inicio = time.perf_counter()
            try:
                rota = path[i % len(path)] if isinstance(path, list) else path
                r = await client.request(method, rota, **kwargs)
                codigo = r.status_code
            except httpx.HTTPError:
                codigo = 'erro_rede'
            resultados.append((codigo, (time.perf_counter() - inicio) * 1000))
    inicio = time.perf_counter()
    await asyncio.gather(*(requisicao(i) for i in range(quantidade)))
    duracao = time.perf_counter() - inicio
    tempos = sorted(t for _, t in resultados)
    return dict(nome=nome, requisicoes=quantidade, concorrencia=concorrencia,
                segundos=round(duracao, 3), req_s=round(quantidade / duracao, 2),
                media_ms=round(statistics.mean(tempos), 2),
                p95_ms=round(tempos[int((len(tempos)-1)*.95)], 2),
                max_ms=round(max(tempos), 2), status=dict(Counter(str(c) for c, _ in resultados)))


async def main(args):
    inicio = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30, trust_env=False) as c:
        r = await c.get('/health'); r.raise_for_status()
        rotas = ['/unidades', '/produtos?unidadeId=1', '/promocoes']
        etapas = []
        for nome, qtd, simultaneos in [('base',100,1), ('moderada',300,5), ('pico',1000,20)]:
            etapas.append(await etapa(c,nome,qtd,simultaneos,'GET',rotas))
        login = await c.post('/auth/login',json={'email':'cliente@raizes.local','senha':'Cliente@123'})
        login.raise_for_status()
        headers={'Authorization':'Bearer '+login.json()['accessToken']}
        estoque = await c.get('/estoque/unidades/1',headers=headers); estoque.raise_for_status()
        saldo = next(x['quantidade'] for x in estoque.json() if x['produtoId']==4)
        concorrencia = await etapa(c,'disputa_estoque',saldo+20,10,'POST','/pedidos',headers=headers,
            json={'unidadeId':1,'canalPedido':'APP','itens':[{'produtoId':4,'quantidade':1}],'formaPagamento':'MOCK'})
        estoque_final=await c.get('/estoque/unidades/1',headers=headers); estoque_final.raise_for_status()
        final=next(x['quantidade'] for x in estoque_final.json() if x['produtoId']==4)
        criados=int(concorrencia['status'].get('201',0))
        concorrencia.update(estoque_inicial=saldo,estoque_final=final,pedidos_criados=criados,
                            estoque_consistente=(saldo-criados==final and final>=0))
        etapas.append(concorrencia)
        for erro in ('401','403','422'):
            if erro=='401': resp=await c.get('/pedidos')
            elif erro=='403':resp=await c.post('/estoque/movimentacoes',headers=headers,json={'unidadeId':1,'produtoId':1,'quantidade':1,'motivo':'teste'})
            else:resp=await c.post('/pedidos',headers=headers,json={})
            assert resp.status_code==int(erro),(erro,resp.status_code)
    resultado={'inicio_utc':inicio,'fim_utc':datetime.now(timezone.utc).isoformat(),
        'ambiente':f'{platform.system()} {platform.machine()}, Python {platform.python_version()}, SQLite, Uvicorn 1 worker, localhost',
        'base_url':args.base_url,'metodo':'Carga fechada, sem tempo de espera; 1400 consultas e disputa concorrente por estoque.',
        'limites':'Ensaio sintético local. Não demonstra capacidade de produção, rede externa, múltiplos workers ou gateway real. Pagamentos simultâneos não avaliados.',
        'etapas':etapas,'controles_acesso':{'401':True,'403':True,'422':True}}
    Path(args.output).write_text(json.dumps(resultado,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(resultado,ensure_ascii=False,indent=2))
    ok=all(e['status'].get('200',0)==e['requisicoes'] for e in etapas[:3]) and concorrencia['estoque_consistente']
    ok=ok and set(concorrencia['status']) <= {'201','409'}
    return 0 if ok else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output',default='evidencias/carga_resultado.json')
    args=parser.parse_args()
    raise SystemExit(asyncio.run(main(args)))
