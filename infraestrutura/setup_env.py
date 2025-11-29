#!/usr/bin/env python3
"""setup_influx.py
Instala e configura InfluxDB e dependências adicionais
"""
import os, sys, subprocess, shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
REQS_ADDITIONAL = ['influxdb-client']

def run(cmd, check=True):
    print('>>>', ' '.join(cmd))
    subprocess.run(cmd, check=check)

def install_influxdb_docker():
    print('\n[STEP] Verificando Docker...')
    try:
        run(['docker', '--version'])
    except:
        print('Docker não encontrado. Instalando...')
        run(['curl', '-fsSL', 'https://get.docker.com', '-o', 'get-docker.sh'])
        run(['sh', 'get-docker.sh'])
        run(['sudo', 'usermod', '-aG', 'docker', 'pi'])
    
    print('\n[STEP] Iniciando InfluxDB com Docker Compose...')
    run(['docker', 'compose', 'up', '-d'])

def install_python_dependencies():
    print('\n[STEP] Instalando dependências Python adicionais...')
    pip = str(BASE / 'venv' / 'bin' / 'pip')
    run([pip, 'install'] + REQS_ADDITIONAL)

def main():
    print("Configurando InfluxDB e dependências...")
    
    # Verifica se o venv existe
    if not (BASE / 'venv').exists():
        print("Erro: Ambiente virtual não encontrado. Execute setup_env.py primeiro.")
        return
    
    install_influxdb_docker()
    install_python_dependencies()
    
    print('\n[OK] Configuração do InfluxDB concluída!')
    print('InfluxDB está rodando em: http://localhost:8086')
    print('Token: estufa_token')
    print('Org: estufa_org')
    print('Bucket: estufa_bucket')
    print('\nPara iniciar o simulador: python3 estufa_opcua_simulate.py')
    print('Para iniciar o writer do InfluxDB: python3 influxdb_writer.py')

if __name__ == '__main__':
    main()