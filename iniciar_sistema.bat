@echo off
title Servidor Devila Tech - Dra. Carabelli
color 0A

:: 1. Garante que o comando rode DENTRO da pasta do projeto
cd /d "%~dp0"

echo ==========================================
echo      INICIANDO SISTEMA DEVILA TECH
echo ==========================================
echo.

:: 2. Tenta ativar ambiente virtual (se voce usa venv ou .venv)
if exist venv\Scripts\activate (
    echo [INFO] Ativando ambiente virtual 'venv'...
    call venv\Scripts\activate
) else if exist .venv\Scripts\activate (
    echo [INFO] Ativando ambiente virtual '.venv'...
    call .venv\Scripts\activate
)

:: 3. Roda o aplicativo
echo [INFO] Rodando app.py...
python app.py

:: 4. Se der erro, nao fecha a janela na hora
echo.
echo ==========================================
echo O SERVIDOR PAROU.
echo Verifique o erro acima.
echo ==========================================
pause