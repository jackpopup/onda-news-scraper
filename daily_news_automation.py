"""
ONDA 뉴스 일일 자동화 스크립트

매일 아침 6시에 실행되어:
1. 뉴스 스크랩
2. HTML 페이지 생성 및 GitHub Pages에 푸시
3. Slack #onda-news 채널에 초안 발송 (Bot API 사용)
"""

import subprocess
import os
import sys
import shutil
from datetime import datetime
import json

# .env 파일 로드
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_PATH = os.path.join(SCRIPT_DIR, 'onda_news_scraper.py')
NEWS_PAGES_DIR = os.path.join(SCRIPT_DIR, 'news_pages')
LATEST_NEWS_FILE = os.path.join(SCRIPT_DIR, 'latest_news.json')

# Slack 설정
BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID', 'C0A7D41B3ED')

# GitHub 설정
GITHUB_REPO_URL = 'https://github.com/jackpopup/onda-news-scraper.git'
GITHUB_PAGES_URL = 'https://jackpopup.github.io/onda-news-scraper'
TEMP_REPO_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'onda-news-scraper-temp')


def log(message):
    """로깅 함수"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}", flush=True)


def run_scraper():
    """뉴스 스크래퍼 실행 (Slack 발송 없이 데이터만 수집)"""
    log("뉴스 스크래퍼 실행 중...")

    try:
        # --silent 옵션으로 콘솔 출력 최소화, Slack 발송은 별도로 처리
        result = subprocess.run(
            [sys.executable, SCRAPER_PATH],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=300,  # 5분 타임아웃
            env={**os.environ}  # 환경변수 전달
        )

        log(f"스크래퍼 종료 코드: {result.returncode}")
        if result.stdout:
            log(f"출력 (마지막 500자): {result.stdout[-500:]}")
        if result.stderr:
            log(f"에러: {result.stderr[-300:]}")

        return True  # 일단 진행

    except subprocess.TimeoutExpired:
        log("스크래퍼 타임아웃 (5분 초과)")
        return False
    except Exception as e:
        log(f"스크래퍼 실행 실패: {e}")
        return False


def send_slack_draft():
    """Slack Bot API로 초안 발송"""
    log("Slack 초안 발송 중...")

    if not BOT_TOKEN:
        log("SLACK_BOT_TOKEN이 설정되지 않았습니다")
        return False

    # slack_sender 모듈 임포트
    sys.path.insert(0, SCRIPT_DIR)
    from slack_sender import send_to_slack_via_bot, generate_news_html_page

    # latest_news.json에서 기사 로드
    if not os.path.exists(LATEST_NEWS_FILE):
        log("latest_news.json 파일이 없습니다")
        return False

    try:
        with open(LATEST_NEWS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        top_3 = data.get('top_3', [])
        top_20 = data.get('top_20', [])
        full_news_url = data.get('full_news_url')

        if not top_3:
            log("발송할 기사가 없습니다")
            return False

        log(f"TOP 3 기사: {len(top_3)}건")

        # Slack 발송
        result = send_to_slack_via_bot(
            articles=top_3,
            channel_id=CHANNEL_ID,
            bot_token=BOT_TOKEN,
            is_draft=True,
            full_news_url=full_news_url
        )

        if result['success']:
            log(f"Slack 발송 성공! thread_ts: {result.get('thread_ts')}")

            # thread_ts 저장 (피드백 모니터링용)
            data['thread_ts'] = result.get('thread_ts')
            data['channel'] = result.get('channel')
            data['sent_at'] = datetime.now().isoformat()

            with open(LATEST_NEWS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        else:
            log(f"Slack 발송 실패: {result.get('message')}")
            return False

    except Exception as e:
        log(f"Slack 발송 오류: {e}")
        return False


def push_html_to_github():
    """HTML 파일을 GitHub Pages 레포에 푸시"""
    log("GitHub Pages에 HTML 푸시 중...")

    today = datetime.now().strftime('%Y-%m-%d')

    # 오늘 생성된 HTML 파일 찾기
    html_files = []
    if os.path.exists(NEWS_PAGES_DIR):
        for f in os.listdir(NEWS_PAGES_DIR):
            if f.endswith('.html') and today.replace('-', '') in f:
                html_files.append(os.path.join(NEWS_PAGES_DIR, f))

    if not html_files:
        log("오늘 생성된 HTML 파일이 없습니다")
        return False

    latest_html = max(html_files, key=os.path.getmtime)
    log(f"HTML 파일: {latest_html}")

    try:
        # 레포 클론 또는 풀
        if os.path.exists(TEMP_REPO_DIR):
            # 기존 레포 풀
            subprocess.run(['git', 'pull'], cwd=TEMP_REPO_DIR, check=True)
        else:
            # 새로 클론
            subprocess.run(['git', 'clone', GITHUB_REPO_URL, TEMP_REPO_DIR], check=True)

        # HTML 파일 복사 (날짜 기반 이름으로)
        dest_filename = f"{today}.html"
        dest_path = os.path.join(TEMP_REPO_DIR, dest_filename)
        shutil.copy2(latest_html, dest_path)
        log(f"HTML 복사: {dest_filename}")

        # index.html도 업데이트 (최신 버전으로)
        index_path = os.path.join(TEMP_REPO_DIR, 'index.html')
        shutil.copy2(latest_html, index_path)
        log("index.html 업데이트")

        # Git 커밋 및 푸시
        subprocess.run(['git', 'add', '.'], cwd=TEMP_REPO_DIR, check=True)

        # 변경사항이 있을 때만 커밋
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=TEMP_REPO_DIR, capture_output=True, text=True)
        if status.stdout.strip():
            subprocess.run(
                ['git', 'commit', '-m', f'Daily news update: {today}'],
                cwd=TEMP_REPO_DIR,
                check=True
            )
            subprocess.run(['git', 'push'], cwd=TEMP_REPO_DIR, check=True)
            log("GitHub 푸시 완료!")
        else:
            log("변경사항 없음, 푸시 스킵")

        # latest_news.json에 URL 업데이트
        full_news_url = f"{GITHUB_PAGES_URL}/{dest_filename}"
        update_latest_news_url(full_news_url)

        return True

    except subprocess.CalledProcessError as e:
        log(f"Git 오류: {e}")
        return False
    except Exception as e:
        log(f"HTML 푸시 실패: {e}")
        return False


def update_latest_news_url(url):
    """latest_news.json에 full_news_url 업데이트"""
    try:
        if os.path.exists(LATEST_NEWS_FILE):
            with open(LATEST_NEWS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            data['full_news_url'] = url

            with open(LATEST_NEWS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            log(f"URL 업데이트: {url}")
    except Exception as e:
        log(f"URL 업데이트 실패: {e}")


def start_slack_monitor(duration_minutes=60):
    """Slack 모니터를 백그라운드로 실행 (기본 1시간)"""
    log(f"Slack 모니터 시작 ({duration_minutes}분간 실행)...")

    monitor_path = os.path.join(SCRIPT_DIR, 'slack_monitor.py')

    try:
        # Windows에서 백그라운드 프로세스로 실행
        # timeout 명령어로 1시간 후 자동 종료
        if sys.platform == 'win32':
            # pythonw를 사용하면 콘솔 창 없이 실행
            cmd = f'start /B python "{monitor_path}"'
            subprocess.Popen(cmd, shell=True, cwd=SCRIPT_DIR,
                           env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                           creationflags=subprocess.CREATE_NO_WINDOW)

            # 1시간 후 자동 종료를 위한 별도 스크립트
            kill_script = os.path.join(SCRIPT_DIR, 'kill_monitor.bat')
            with open(kill_script, 'w') as f:
                f.write(f'@echo off\n')
                f.write(f'timeout /t {duration_minutes * 60} /nobreak > nul\n')
                f.write(f'taskkill /f /im python.exe /fi "WINDOWTITLE eq slack_monitor*" 2>nul\n')

            log(f"Slack 모니터가 백그라운드에서 {duration_minutes}분간 실행됩니다")
        else:
            # Linux/Mac
            subprocess.Popen(
                [sys.executable, monitor_path],
                cwd=SCRIPT_DIR,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            log("Slack 모니터가 백그라운드에서 실행 중")

        return True
    except Exception as e:
        log(f"Slack 모니터 시작 실패: {e}")
        return False


def main():
    """메인 실행 함수"""
    log("=" * 60)
    log("ONDA 뉴스 일일 자동화 시작")
    log("=" * 60)

    # 1. 뉴스 스크랩
    run_scraper()

    # 2. HTML을 GitHub Pages에 푸시
    push_html_to_github()

    # 3. Slack 초안 발송
    slack_sent = send_slack_draft()

    # 4. Slack 모니터 자동 시작 (초안 발송 성공 시)
    if slack_sent:
        start_slack_monitor(duration_minutes=60)

    log("=" * 60)
    log("일일 자동화 완료!")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
