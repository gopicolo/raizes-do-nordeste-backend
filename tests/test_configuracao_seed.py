import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from app.infrastructure.database import SessionLocal
from app.infrastructure.models import Usuario, Estoque
from scripts.seed import run
from sqlalchemy import select


@pytest.mark.parametrize('externo', [False, True])
def test_dotenv_configura_banco_e_jwt_sem_sobrescrever_ambiente(tmp_path, externo):
    raiz = Path(__file__).resolve().parents[1]
    shutil.copytree(raiz / 'app', tmp_path / 'app', ignore=shutil.ignore_patterns('__pycache__'))
    (tmp_path / '.env').write_text('DATABASE_URL=sqlite:///arquivo-env.db\nJWT_SECRET=chave-local-de-teste\nJWT_EXPIRE_MINUTES=15\n')
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    for chave in ('DATABASE_URL', 'JWT_SECRET', 'JWT_EXPIRE_MINUTES', 'PYTHON_DOTENV_DISABLED'):
        env.pop(chave, None)
    if externo:
        env.update(DATABASE_URL='sqlite:///externo.db', JWT_SECRET='chave-do-ambiente', JWT_EXPIRE_MINUTES='30')
    codigo = ('from app.infrastructure.database import DATABASE_URL; '
              'from app.infrastructure.security import JWT_SECRET, JWT_EXPIRE_MINUTES; '
              'import json; print(json.dumps([DATABASE_URL, JWT_SECRET, JWT_EXPIRE_MINUTES]))')
    r = subprocess.run([sys.executable, '-c', codigo], cwd=tmp_path, env=env,
                       capture_output=True, text=True, check=True)
    esperado = ['sqlite:///externo.db', 'chave-do-ambiente', 30] if externo else [
        'sqlite:///arquivo-env.db', 'chave-local-de-teste', 15]
    assert json.loads(r.stdout) == esperado


def test_seed_adiciona_atendente_sem_reiniciar_banco_existente(client):
    with SessionLocal() as db:
        antes = [(e.id, e.quantidade) for e in db.scalars(select(Estoque)).all()]
    run()
    run()
    with SessionLocal() as db:
        contas = db.scalars(select(Usuario).where(Usuario.email == 'atendente@raizes.local')).all()
        assert len(contas) == 1 and contas[0].perfil == 'ATENDENTE'
        assert [(e.id, e.quantidade) for e in db.scalars(select(Estoque)).all()] == antes
    login = client.post('/auth/login', json={'email': 'atendente@raizes.local', 'senha': 'Atendente@123'})
    assert login.status_code == 200
    r = client.post('/pedidos', headers={'Authorization': 'Bearer ' + login.json()['accessToken']},
                    json={'unidadeId': 1, 'canalPedido': 'BALCAO', 'itens': [{'produtoId': 1, 'quantidade': 1}]})
    assert r.status_code == 201


def test_seed_inicial_completo_e_repetivel(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    banco = tmp_path / 'seed.db'
    env = dict(os.environ, DATABASE_URL='sqlite:///' + str(banco))
    for _ in range(2):
        subprocess.run([sys.executable, '-m', 'scripts.seed'], cwd=raiz, env=env,
                       check=True, capture_output=True, text=True)
    import sqlite3
    with sqlite3.connect(banco) as db:
        assert db.execute('select count(*) from usuarios').fetchone()[0] == 5
        assert db.execute("select perfil from usuarios where email='atendente@raizes.local'").fetchone()[0] == 'ATENDENTE'
        assert db.execute('select count(*) from unidades').fetchone()[0] == 2
        assert db.execute('select count(*) from produtos').fetchone()[0] == 4
        assert db.execute('select count(*) from estoques').fetchone()[0] == 8
