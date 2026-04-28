@echo off
title agente01 — Agente de Investigacion Financiera
color 0A

echo ============================================================
echo   agente01 — Agente de Investigacion Financiera
echo   Trading-agente-01
echo ============================================================
echo.

:: Ir al directorio del proyecto
cd /d "C:\Users\kenyb\Desktop\GEMINI\Trading-agente-01"

:: Verificar que el directorio existe
if not exist "agente01.py" (
    echo [ERROR] No se encontro agente01.py en este directorio.
    echo         Verifica la ruta del proyecto.
    pause
    exit /b 1
)

:: Verificar que el entorno virtual existe
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        echo         Asegurate de tener Python instalado.
        pause
        exit /b 1
    )
    echo [INFO] Instalando dependencias...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: Verificar que el .env existe
if not exist ".env" (
    echo [ERROR] No se encontro el archivo .env
    echo         Copia .env.example a .env y configura tus credenciales.
    pause
    exit /b 1
)

echo [OK] Entorno virtual activado
echo [OK] Directorio: %CD%
echo [OK] Iniciando agente01...
echo.

:: Ejecutar el agente (mantiene la ventana abierta si hay error)
python agente01.py

echo.
echo [INFO] agente01 se ha detenido.
pause
