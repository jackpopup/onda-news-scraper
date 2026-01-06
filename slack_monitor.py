"""
Slack 스레드 모니터링 - 피드백 자동 처리

사용법:
    python slack_monitor.py

스레드에 댓글이 달리면:
- 피드백 파싱 → 기사 수정 → 수정된 초안 스레드에 표시
- "발송" 또는 "확인" 댓글 → 최종 발송
"""

import json
import time
import os
import sys
from datetime import datetime
from slack_sender import (
    get_thread_replies,
    parse_feedback,
    apply_feedback_to_articles,
    send_updated_draft_to_thread,
    send_to_slack_via_bot,
    collect_feedback_from_thread,
    generate_news_html_page
)
import subprocess
import shutil

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

# 설정 (환경변수에서 로드)
BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID', 'C0A7D41B3ED')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'latest_news.json')
POLL_INTERVAL = 5  # 5초마다 확인


def load_news_data():
    """저장된 뉴스 데이터 로드"""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_news_data(data):
    """뉴스 데이터 저장"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_processed_replies(data):
    """이미 처리된 댓글 timestamp 목록"""
    return set(data.get('processed_replies', []))


# GitHub 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_PAGES_DIR = os.path.join(SCRIPT_DIR, 'news_pages')
GITHUB_REPO_URL = 'https://github.com/jackpopup/onda-news-scraper.git'
GITHUB_PAGES_URL = 'https://jackpopup.github.io/onda-news-scraper'
TEMP_REPO_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'onda-news-scraper-temp')


def regenerate_and_push_html(top_20_articles):
    """수정된 기사 목록으로 HTML 재생성 및 GitHub 푸시"""
    print("   → 📄 HTML 재생성 중...", flush=True)

    today = datetime.now().strftime('%Y-%m-%d')

    try:
        # HTML 생성
        result = generate_news_html_page(top_20_articles)
        # tuple인 경우 (path, filename) 형태
        if isinstance(result, tuple):
            html_path = result[0]
        else:
            html_path = result

        if not html_path:
            print("   → ⚠️ HTML 생성 실패", flush=True)
            return None

        print(f"   → HTML 생성: {html_path}", flush=True)

        # GitHub 레포에 푸시
        if os.path.exists(TEMP_REPO_DIR):
            subprocess.run(['git', 'pull'], cwd=TEMP_REPO_DIR, capture_output=True)
        else:
            subprocess.run(['git', 'clone', GITHUB_REPO_URL, TEMP_REPO_DIR], capture_output=True)

        # HTML 복사
        dest_filename = f"{today}.html"
        dest_path = os.path.join(TEMP_REPO_DIR, dest_filename)
        shutil.copy2(html_path, dest_path)

        # index.html도 업데이트
        index_path = os.path.join(TEMP_REPO_DIR, 'index.html')
        shutil.copy2(html_path, index_path)

        # Git 커밋 및 푸시
        subprocess.run(['git', 'add', '.'], cwd=TEMP_REPO_DIR, capture_output=True)
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=TEMP_REPO_DIR, capture_output=True, text=True)

        if status.stdout.strip():
            subprocess.run(['git', 'commit', '-m', f'Update news after feedback: {today}'], cwd=TEMP_REPO_DIR, capture_output=True)
            subprocess.run(['git', 'push'], cwd=TEMP_REPO_DIR, capture_output=True)
            print("   → ✅ GitHub 푸시 완료", flush=True)

        return f"{GITHUB_PAGES_URL}/{dest_filename}"

    except Exception as e:
        print(f"   → ⚠️ HTML 푸시 실패: {e}", flush=True)
        return None


def monitor_thread():
    """
    스레드 모니터링 메인 루프
    """
    print("=" * 60, flush=True)
    print("ONDA 뉴스 Slack 모니터링 시작", flush=True)
    print("=" * 60, flush=True)

    # 데이터 로드
    data = load_news_data()
    thread_ts = data.get('thread_ts')

    if not thread_ts:
        print("❌ thread_ts가 없습니다. 먼저 초안을 발송하세요.", flush=True)
        return

    print(f"📌 모니터링 스레드: {thread_ts}", flush=True)
    print(f"📌 채널: {CHANNEL_ID}", flush=True)
    print(f"📌 폴링 간격: {POLL_INTERVAL}초", flush=True)
    print("-" * 60, flush=True)
    print("💡 Ctrl+C로 종료", flush=True)
    print("-" * 60, flush=True)

    # 현재 기사 상태
    current_top3 = data.get('top_3', []).copy()
    top_20 = data.get('top_20', [])
    full_news_url = data.get('full_news_url')
    processed_replies = get_processed_replies(data)

    try:
        while True:
            # 스레드 댓글 가져오기
            result = get_thread_replies(CHANNEL_ID, thread_ts, BOT_TOKEN)

            if not result['success']:
                print(f"⚠️ 스레드 조회 실패: {result.get('error')}")
                time.sleep(POLL_INTERVAL)
                continue

            replies = result['replies']

            # 새 댓글 확인
            new_replies = []
            for reply in replies:
                reply_ts = reply.get('ts')
                if reply_ts and reply_ts not in processed_replies:
                    new_replies.append(reply)

            if new_replies:
                for reply in new_replies:
                    reply_ts = reply.get('ts')
                    text = reply.get('text', '')

                    print(f"\n📩 새 피드백 감지: \"{text}\"", flush=True)

                    # 피드백 파싱
                    commands = parse_feedback(text)

                    if not commands:
                        print("   → 인식된 명령 없음 (무시)", flush=True)
                        processed_replies.add(reply_ts)
                        continue

                    print(f"   → 파싱된 명령: {commands}", flush=True)

                    # 승인 여부 확인
                    is_approve = any(cmd['action'] == 'approve' for cmd in commands)

                    if is_approve:
                        # 최종 발송
                        print("   → ✅ 승인 확인! 최종 발송 중...")

                        # 최종 발송 (is_draft=False)
                        final_result = send_to_slack_via_bot(
                            articles=current_top3,
                            channel_id=CHANNEL_ID,
                            bot_token=BOT_TOKEN,
                            is_draft=False,
                            full_news_url=full_news_url
                        )

                        if final_result['success']:
                            print("   → 🎉 최종 발송 완료!")

                            # 데이터 저장 후 종료
                            data['processed_replies'] = list(processed_replies)
                            data['final_sent'] = True
                            data['final_sent_at'] = datetime.now().isoformat()
                            save_news_data(data)

                            print("\n" + "=" * 60)
                            print("모니터링 종료 - 최종 발송 완료")
                            print("=" * 60)
                            return
                        else:
                            print(f"   → ❌ 발송 실패: {final_result.get('message')}")
                    else:
                        # 피드백 적용 (TOP 3와 TOP 20 모두)
                        modified, changes = apply_feedback_to_articles(
                            current_top3, commands, top_20
                        )

                        print(f"   → 변경사항:\n{changes}", flush=True)

                        # TOP 20도 동일한 순서로 업데이트
                        # modified의 순서를 top_20에도 반영
                        updated_top_20 = list(modified)  # TOP 3 먼저
                        for article in top_20:
                            if article not in modified:
                                updated_top_20.append(article)
                        top_20 = updated_top_20[:20]

                        # HTML 재생성 및 GitHub 푸시
                        new_url = regenerate_and_push_html(top_20)
                        if new_url:
                            full_news_url = new_url
                            data['full_news_url'] = new_url

                        # 수정된 초안을 스레드에 표시
                        update_result = send_updated_draft_to_thread(
                            channel_id=CHANNEL_ID,
                            thread_ts=thread_ts,
                            articles=modified,
                            changes_summary=changes,
                            bot_token=BOT_TOKEN,
                            full_news_url=full_news_url
                        )

                        if update_result['success']:
                            print("   → 📝 수정된 초안 전송 완료", flush=True)
                            current_top3 = modified  # 상태 업데이트

                            # 데이터 저장
                            data['top_3'] = current_top3
                            data['top_20'] = top_20
                        else:
                            print(f"   → ❌ 초안 전송 실패: {update_result.get('error')}", flush=True)

                    # 처리 완료 표시
                    processed_replies.add(reply_ts)

                # 처리된 댓글 저장
                data['processed_replies'] = list(processed_replies)
                save_news_data(data)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n모니터링 중단됨 (Ctrl+C)")
        # 현재 상태 저장
        data['top_3'] = current_top3
        data['processed_replies'] = list(processed_replies)
        save_news_data(data)
        print("현재 상태 저장됨")


if __name__ == "__main__":
    monitor_thread()
