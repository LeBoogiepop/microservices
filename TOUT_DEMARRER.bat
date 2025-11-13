@echo off
chcp 65001 >nul
echo ========================================
echo   INITIALISATION ET DEMARRAGE COMPLET
echo ========================================
echo.

echo [ETAPE 0] Arret des anciens services...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5001"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5002"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5003"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5004"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

echo [ETAPE 1] Initialisation de la base de donnees...
python init_db.py
if errorlevel 1 (
    echo ERREUR lors de l'initialisation!
    pause
    exit /b 1
)

echo.
echo [ETAPE 2] Demarrage des services...
echo.

start "Auth Service" cmd /k "cd /d %~dp0auth_service && python app.py"
timeout /t 3 /nobreak >nul

start "User Service" cmd /k "cd /d %~dp0user_service && python app.py"
timeout /t 3 /nobreak >nul

start "Orders Service" cmd /k "cd /d %~dp0orders_service && python app.py"
timeout /t 3 /nobreak >nul

start "Gateway" cmd /k "cd /d %~dp0gateway && python app.py"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   SERVICES DEMARRES
echo ========================================
echo.
echo 4 fenetres ont ete ouvertes (une par service):
echo   - Auth Service (port 5001)
echo   - User Service (port 5002)
echo   - Orders Service (port 5003)
echo   - API Gateway (port 5004)
echo.
echo Dans chaque fenetre, vous devriez voir:
echo   "Running on http://0.0.0.0:500X"
echo.
echo PROCHAINES ETAPES:
echo   1. Dans un nouveau terminal, activez le venv: .venv\Scripts\activate
echo   2. Demarrez l'application web: python app.py
echo   3. Accedez a http://localhost:5000/
echo   4. Pour tester: python test_tp.py ou .\TESTER.bat
echo.
pause

