@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title TwitchLink - Backup

:: ============================================================
::  BACKUP_TwitchLink.bat
::  Guarda configuracion y archivos de TwitchLink en un ZIP
::  con fecha y hora. Compatible con Windows 10/11.
:: ============================================================

:: --- Rutas de la aplicacion ---
set "APP_DIR=%ProgramFiles%\TwitchLink"
set "APPDATA_DIR=%APPDATA%\TwitchLink"

:: --- Carpeta donde se guardan los backups ---
set "BACKUP_ROOT=%USERPROFILE%\Documents\TwitchLink_Backups"

:: --- Nombre del backup con fecha y hora ---
for /f "tokens=1-3 delims=/" %%a in ("%DATE%") do (
    set "DIA=%%a"
    set "MES=%%b"
    set "ANO=%%c"
)
for /f "tokens=1-2 delims=:." %%a in ("%TIME: =0%") do (
    set "HORA=%%a"
    set "MIN=%%b"
)
set "TIMESTAMP=%ANO%-%MES%-%DIA%_%HORA%h%MIN%m"
set "BACKUP_NAME=TwitchLink_Backup_%TIMESTAMP%"
set "BACKUP_FOLDER=%BACKUP_ROOT%\%BACKUP_NAME%"
set "ZIP_FILE=%BACKUP_ROOT%\%BACKUP_NAME%.zip"

echo.
echo  =====================================================
echo   TwitchLink - Herramienta de Backup
echo  =====================================================
echo.
echo  Backup: %BACKUP_NAME%
echo  Destino: %BACKUP_ROOT%
echo.

:: --- Verificar que existe al menos una fuente ---
set "HAY_APPDATA=0"
set "HAY_APP=0"

if exist "%APPDATA_DIR%" set "HAY_APPDATA=1"
if exist "%APP_DIR%"     set "HAY_APP=1"

if "%HAY_APPDATA%"=="0" if "%HAY_APP%"=="0" (
    echo  [ERROR] No se encontro TwitchLink instalado.
    echo.
    echo  Rutas buscadas:
    echo    - %APPDATA_DIR%
    echo    - %APP_DIR%
    echo.
    pause
    exit /b 1
)

:: --- Crear carpeta de backups si no existe ---
if not exist "%BACKUP_ROOT%" (
    mkdir "%BACKUP_ROOT%"
    echo  [OK] Carpeta de backups creada: %BACKUP_ROOT%
)

:: --- Crear carpeta temporal de staging ---
mkdir "%BACKUP_FOLDER%"

echo  Copiando archivos...
echo.

:: --- Backup de configuracion (settings, historial, etc.) ---
if "%HAY_APPDATA%"=="1" (
    echo  [1/2] Configuracion y ajustes...  (%APPDATA_DIR%)
    xcopy "%APPDATA_DIR%" "%BACKUP_FOLDER%\AppData\" /E /H /I /Y /Q >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo       OK
    ) else (
        echo       ADVERTENCIA: algunos archivos no se copiaron
    )
) else (
    echo  [1/2] Configuracion: no encontrada, se omite.
)

:: --- Backup de archivos de la aplicacion ---
if "%HAY_APP%"=="1" (
    echo  [2/2] Archivos de la aplicacion...  (%APP_DIR%)
    xcopy "%APP_DIR%" "%BACKUP_FOLDER%\AppFiles\" /E /H /I /Y /Q >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo       OK
    ) else (
        echo       ADVERTENCIA: algunos archivos no se copiaron
    )
) else (
    echo  [2/2] Aplicacion: no encontrada en Program Files, se omite.
)

:: --- Guardar informacion del backup ---
(
    echo TwitchLink Backup Info
    echo ======================
    echo Fecha:        %DATE% %TIME%
    echo Version app:  3.5.4
    echo AppData:      %APPDATA_DIR%
    echo AppFiles:     %APP_DIR%
    echo Usuario:      %USERNAME%
    echo PC:           %COMPUTERNAME%
) > "%BACKUP_FOLDER%\backup_info.txt"

:: --- Comprimir todo en ZIP ---
echo.
echo  Comprimiendo backup en ZIP...
powershell -NoProfile -Command ^
    "Compress-Archive -Path '%BACKUP_FOLDER%\*' -DestinationPath '%ZIP_FILE%' -Force" ^
    >nul 2>&1

if exist "%ZIP_FILE%" (
    :: Calcular tamaño del ZIP
    for %%F in ("%ZIP_FILE%") do set "SIZE_BYTES=%%~zF"
    set /a "SIZE_KB=!SIZE_BYTES! / 1024"
    set /a "SIZE_MB=!SIZE_KB! / 1024"

    :: Limpiar carpeta temporal
    rmdir /S /Q "%BACKUP_FOLDER%"

    echo.
    echo  =====================================================
    echo   BACKUP COMPLETADO EXITOSAMENTE
    echo  =====================================================
    echo.
    echo   Archivo: %ZIP_FILE%
    echo   Tamaño:  ~!SIZE_MB! MB  ^(!SIZE_KB! KB^)
    echo.
    echo   Contenido del backup:
    if "%HAY_APPDATA%"=="1" echo     Configuracion y ajustes  ^(settings.json, historial^)
    if "%HAY_APP%"=="1"     echo     Archivos de la aplicacion
    echo.
) else (
    :: Si fallo el ZIP, al menos dejar la carpeta sin comprimir
    echo.
    echo  [AVISO] No se pudo crear el ZIP.
    echo   Los archivos quedaron sin comprimir en:
    echo   %BACKUP_FOLDER%
    echo.
)

:: --- Listar backups existentes ---
echo  Backups guardados en %BACKUP_ROOT%:
echo  ------------------------------------
set "CONTADOR=0"
for %%F in ("%BACKUP_ROOT%\*.zip") do (
    set /a "CONTADOR+=1"
    echo   !CONTADOR!. %%~nxF
)
if "%CONTADOR%"=="0" echo   (ninguno)
echo.

pause
endlocal
exit /b 0
