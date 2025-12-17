@echo off
title Servidor Devila Tech - Dra. Carabelli
color 0A

:: 1. Garante que o comando rode DENTRO da pasta do projeto
cd /d "%~dp0"

echo ==========================================
echo      INICIANDO SISTEMA DEVILA TECH
echo ==========================================
echo.

:: 2. Verifica se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado! Instale o Python e marque "Add to PATH".
    pause
    exit
)

:: 3. Tenta ativar ambiente virtual (se voce usa venv ou .venv)
if exist venv\Scripts\activate (
    echo [INFO] Ativando ambiente virtual 'venv'...
    call venv\Scripts\activate
) else if exist .venv\Scripts\activate (
    echo [INFO] Ativando ambiente virtual '.venv'...
    call .venv\Scripts\activate
) else (
    echo [AVISO] Nenhum ambiente virtual encontrado. Rodando no Python global.
)

:: 4. Instala dependencias
echo [INFO] Verificando dependencias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit
)
echo.

:: 5. Roda o aplicativo
echo [INFO] Iniciando servidor...
python app.py

:: 6. Se der erro, nao fecha a janela na hora
echo.
echo ==========================================
echo O SERVIDOR PAROU.
echo Verifique o erro acima.
echo ==========================================
pause
