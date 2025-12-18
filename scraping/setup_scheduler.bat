@echo off
REM 매일 오전 9시에 뉴스 수집 및 이메일 전송 작업 등록
REM 실행 방법: 관리자 권한으로 이 파일을 실행하세요.

echo ========================================
echo AI 뉴스 수집 자동화 스케줄러 설정
echo ========================================
echo.

REM Python 경로 찾기
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo 오류: Python이 설치되어 있지 않거나 PATH에 등록되지 않았습니다.
    echo Python을 설치한 후 다시 시도해주세요.
    pause
    exit /b 1
)

REM 현재 스크립트 경로 확인
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%ai_startup_news.py

echo 스크립트 경로: %SCRIPT_PATH%
echo.

REM 받는 사람 이메일 입력
set /p RECIPIENT_EMAIL="받는 사람 이메일 주소를 입력하세요: "

REM 이메일 서비스 선택
echo.
echo 이메일 서비스를 선택하세요:
echo 1. Gmail
echo 2. Outlook
set /p EMAIL_SERVICE_CHOICE="선택 (1 또는 2): "

if "%EMAIL_SERVICE_CHOICE%"=="1" (
    set EMAIL_SERVICE=gmail
) else if "%EMAIL_SERVICE_CHOICE%"=="2" (
    set EMAIL_SERVICE=outlook
) else (
    echo 잘못된 선택입니다. Gmail로 설정됩니다.
    set EMAIL_SERVICE=gmail
)

REM Windows 작업 스케줄러에 등록
echo.
echo 작업 스케줄러에 등록 중...
echo.

schtasks /create /tn "PopupStudio_DailyNews" /tr "python \"%SCRIPT_PATH%\" --email --email-service %EMAIL_SERVICE% --to %RECIPIENT_EMAIL% --silent" /sc daily /st 09:00 /f

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo 등록 완료!
    echo ========================================
    echo.
    echo 매일 오전 9시에 %RECIPIENT_EMAIL%로 뉴스가 전송됩니다.
    echo.
    echo 작업 확인: 작업 스케줄러 열기 ^> "PopupStudio_DailyNews" 찾기
    echo 작업 삭제: schtasks /delete /tn "PopupStudio_DailyNews" /f
    echo.
) else (
    echo.
    echo 오류: 작업 등록에 실패했습니다.
    echo 관리자 권한으로 실행했는지 확인해주세요.
    echo.
)

pause
