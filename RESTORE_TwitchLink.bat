@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title TwitchLink - Restaurar Backup

:: ============================================================
::  RESTORE_TwitchLink.bat
::  Restaura un backup de TwitchLink creado con BACKUP_TwitchLink.bat
::  Compatible con Windows 10/11.
:: ============================================================

:: --- Rutas de destino ---
set "APP_DIR=%ProgramFiles%\TwitchLink"
set "APPDATA_DIR=%APPDATA%\TwitchLink"

:: --- Carpeta de backups ---
set "BACKUP_ROOT=%USERPROFILE%\Documents\TwitchLink_Backups"

:: --- Carpeta temporal para extraer ---
set "TEMP_EXTRACT=%TEMP%\TwitchLink_Restore_Temp"

echo.
echo  =====================================================
echo   TwitchLink - Restaurar Backup
echo  =====================================================
echo.

:: --- Verificar que la carpeta de backups existe ---
if not exist "%BACKUP_ROOT%" (
    echo  [ERROR] No se encontro la carpeta de backups.
    echo.
    echo  Se busco en: %BACKUP_ROOT%
    echo.
    echo  Crea primero un backup con BACKUP_TwitchLink.bat
    echo  o copia tus archivos .zip a esa carpeta.
    echo.
    pause
    exit /b 1
)

:: --- Listar backups disponibles ---
echo  Backups disponibles:
echo  ---------------------
set "NUM=0"
for %%F in ("%BACKUP_ROOT%\*.zip") do (
    set /a "NUM+=1"
    set "BACKUP_!NUM!=%%F"
    set "BACKUP_NAME_!NUM!=%%~nxF"
    echo   [!NUM!] %%~nxF
)

if "%NUM%"=="0" (
    echo   No hay archivos .zip en %BACKUP_ROOT%
    echo.
    pause
    exit /b 1
)

echo.
set /p "OPCION=  Elige el numero del backup a restaurar (1-%NUM%): "

:: --- Validar opcion ---
set "ZIP_ELEGIDO="
set "ZIP_NOMBRE="
for /L %%I in (1,1,%NUM%) do (
    if "!OPCION!"=="%%I" (
        set "ZIP_ELEGIDO=!BACKUP_%%I!"
        set "ZIP_NOMBRE=!BACKUP_NAME_%%I!"
    )
)

if not defined ZIP_ELEGIDO (
    echo.
    echo  [ERROR] Opcion no valida. Escribe un numero entre 1 y %NUM%.
    echo.
    pause
    exit /b 1
)

echo.
echo  Backup seleccionado: %ZIP_NOMBRE%
echo.

:: --- Advertencia antes de restaurar ---
echo  ATENCION: Esta operacion sobreescribira la configuracion
echo  actual de TwitchLink con la del backup.
echo.
set /p "CONFIRMAR=  Escribir S para continuar o N para cancelar: "
if /i not "%CONFIRMAR%"=="S" (
    echo.
    echo  Operacion cancelada.
    echo.
    pause
    exit /b 0
)

:: --- Cerrar TwitchLink si esta abierto ---
echo.
echo  Cerrando TwitchLink si esta en ejecucion...
taskkill /IM TwitchLink.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

:: --- Limpiar y crear carpeta temporal ---
if exist "%TEMP_EXTRACT%" rmdir /S /Q "%TEMP_EXTRACT%"
mkdir "%TEMP_EXTRACT%"

:: --- Extraer el ZIP ---
echo  Extrayendo backup...
powershell -NoProfile -Command ^
    "Expand-Archive -Path '%ZIP_ELEGIDO%' -DestinationPath '%TEMP_EXTRACT%' -Force" ^
    >nul 2>&1

if not exist "%TEMP_EXTRACT%" (
    echo.
    echo  [ERROR] No se pudo extraer el ZIP. El archivo puede estar dañado.
    echo.
    pause
    exit /b 1
)

:: --- Detectar que hay en el backup ---
set "TIENE_APPDATA=0"
set "TIENE_APPFILES=0"

if exist "%TEMP_EXTRACT%\AppData\"  set "TIENE_APPDATA=1"
if exist "%TEMP_EXTRACT%\AppFiles\" set "TIENE_APPFILES=1"

echo.
echo  Contenido encontrado en el backup:
if "%TIENE_APPDATA%"=="1"  echo    Configuracion y ajustes
if "%TIENE_APPFILES%"=="1" echo    Archivos de la aplicacion
echo.

:: --- Restaurar configuracion ---
if "%TIENE_APPDATA%"=="1" (
    echo  [1] Restaurando configuracion y ajustes...
    if not exist "%APPDATA_DIR%" mkdir "%APPDATA_DIR%"
    xcopy "%TEMP_EXTRACT%\AppData\" "%APPDATA_DIR%\" /E /H /I /Y /Q >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo      OK - Configuracion restaurada en: %APPDATA_DIR%
    ) else (
        echo      ADVERTENCIA: Algunos archivos no se restauraron correctamente.
    )
) else (
    echo  [1] Configuracion: no hay datos en este backup, se omite.
)

:: --- Restaurar archivos de aplicacion ---
if "%TIENE_APPFILES%"=="1" (
    echo.
    echo  [2] El backup contiene archivos de la aplicacion.
    echo      Ubicacion de destino: %APP_DIR%
    echo.
    set /p "REST_APP=      Restaurar archivos de la aplicacion? (S/N): "
    if /i "!REST_APP!"=="S" (
        :: Necesita permisos de administrador para Program Files
        net session >nul 2>&1
        if !ERRORLEVEL! NEQ 0 (
            echo.
            echo      [AVISO] Se requieren permisos de Administrador
            echo      para restaurar en Program Files.
            echo      Ejecuta este .bat como Administrador e intenta de nuevo.
        ) else (
            if not exist "%APP_DIR%" mkdir "%APP_DIR%"
            xcopy "%TEMP_EXTRACT%\AppFiles\" "%APP_DIR%\" /E /H /I /Y /Q >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                echo      OK - Archivos restaurados en: %APP_DIR%
            ) else (
                echo      ADVERTENCIA: Algunos archivos no se restauraron.
            )
        )
    ) else (
        echo      Archivos de aplicacion omitidos.
    )
) else (
    echo  [2] Archivos de aplicacion: no hay en este backup, se omite.
)

:: --- Limpiar temporales ---
rmdir /S /Q "%TEMP_EXTRACT%" >nul 2>&1

:: --- Mostrar info del backup si existe ---
echo.
if exist "%APPDATA_DIR%\backup_info.txt" (
    echo  Informacion del backup restaurado:
    echo  ------------------------------------
    type "%APPDATA_DIR%\backup_info.txt"
    echo.
)

echo  =====================================================
echo   RESTAURACION COMPLETADA
echo  =====================================================
echo.
echo  Puedes abrir TwitchLink ahora.
echo.
pause
endlocal
exit /b 0
