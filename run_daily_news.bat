@echo off
REM ONDA 뉴스 일일 자동화 실행 스크립트
REM Windows Task Scheduler에서 사용

cd /d "c:\GitHub\AI-driven-work\scraping"

REM Python 실행
python daily_news_automation.py >> daily_news_log.txt 2>&1

exit /b %ERRORLEVEL%
