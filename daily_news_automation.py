"""
ONDA 뉴스 일일 자동화 스크립트

매일 아침 6시에 실행되어:
1. 뉴스 스크랩
2. HTML 페이지 생성 및 GitHub Pages에 푸시
3. Slack #onda-news 채널에 초안 발송
"""

import subprocess
import os
import sys
import shutil
from datetime import datetime
import json

# 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_PATH = os.path.join(SCRIPT_DIR, 'onda_news_scraper.py')
NEWS_PAGES_DIR = os.path.join(SCRIPT_DIR, 'news_pages')
LATEST_NEWS_FILE = os.path.join(SCRIPT_DIR, 'latest_news.json')

# GitHub 설정
GITHUB_REPO_URL = 'https://github.com/jackpopup/onda-news-scraper.git'
GITHUB_PAGES_URL = 'https://jackpopup.github.io/onda-news-scraper'
TEMP_REPO_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'onda-news-pages-temp')


def log(message):
    """로깅 함수"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def run_scraper():
    """뉴스 스크래퍼 실행 및 Slack 초안 발송"""
    log("뉴스 스크래퍼 실행 중...")

    try:
        result = subprocess.run(
            [sys.executable, SCRAPER_PATH, '--slack-draft'],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5분 타임아웃
        )

        if result.returncode == 0:
            log("스크래퍼 실행 완료")
            log(f"출력: {result.stdout[-500:] if len(result.stdout) > 500 else result.stdout}")
            return True
        else:
            log(f"스크래퍼 오류: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        log("스크래퍼 타임아웃 (5분 초과)")
        return False
    except Exception as e:
        log(f"스크래퍼 실행 실패: {e}")
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
        subprocess.run(
            ['git', 'commit', '-m', f'Daily news update: {today}'],
            cwd=TEMP_REPO_DIR,
            check=True
        )
        subprocess.run(['git', 'push'], cwd=TEMP_REPO_DIR, check=True)

        log("GitHub 푸시 완료!")

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


def main():
    """메인 실행 함수"""
    log("=" * 60)
    log("ONDA 뉴스 일일 자동화 시작")
    log("=" * 60)

    # 1. 뉴스 스크랩 및 Slack 초안 발송
    if not run_scraper():
        log("스크래퍼 실패 - 종료")
        return 1

    # 2. HTML을 GitHub Pages에 푸시
    push_html_to_github()  # 실패해도 계속 진행 (Slack 발송은 완료됨)

    log("=" * 60)
    log("일일 자동화 완료!")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
