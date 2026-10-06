"""Executa Pytest e carga HTTP contra um banco temporário, sem alterar raizes.db."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postman', action='store_true', help='Executa também Newman instalado via npm install.')
    args = parser.parse_args()
    os.chdir(ROOT)
    evidencias = ROOT / 'evidencias'
    evidencias.mkdir(exist_ok=True)
    with (evidencias / 'testes_pytest.txt').open('w', encoding='utf-8') as f:
        subprocess.run([sys.executable, '-m', 'pytest', '-v', '--tb=short'], stdout=f, stderr=subprocess.STDOUT, check=True)
    with tempfile.TemporaryDirectory(prefix='raizes-validacao-') as temp:
        env = dict(os.environ, DATABASE_URL='sqlite:///' + str(Path(temp) / 'validacao.db'))
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env, check=True)
        subprocess.run([sys.executable, '-m', 'scripts.seed'], env=env, check=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        with (evidencias / 'uvicorn_carga.log').open('w', encoding='utf-8') as log:
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', str(port)], env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try:
                        if httpx.get(base + '/health', trust_env=False).status_code == 200:
                            break
                    except httpx.HTTPError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('A API não iniciou em 10 segundos.')
                if args.postman:
                    cli = ROOT / 'node_modules/newman/bin/newman.js'
                    if not cli.is_file():
                        raise RuntimeError('Execute npm install antes de usar --postman.')
                    with (evidencias / 'postman_execucao.txt').open('w', encoding='utf-8') as f:
                        subprocess.run(['node', str(cli), 'run', 'postman_collection.json', '-e', 'postman_environment.json', '--env-var', 'baseUrl=' + base, '--reporters', 'cli,htmlextra', '--reporter-htmlextra-export', 'evidencias/postman_relatorio.html', '--reporter-htmlextra-skipSensitiveData', '--color', 'off'], stdout=f, stderr=subprocess.STDOUT, check=True)
                with (evidencias / 'carga_execucao.txt').open('w', encoding='utf-8') as f:
                    subprocess.run([sys.executable, 'scripts/teste_carga.py', '--base-url', base], stdout=f, stderr=subprocess.STDOUT, check=True)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    print('Validação concluída. Resultados em evidencias/. O banco temporário foi removido.')


if __name__ == '__main__':
    main()
