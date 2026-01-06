"""
Slack 발송 모듈
뉴스 수집 결과를 Slack으로 전송 및 피드백 수집

사용법:
1. Slack 워크스페이스에서 Incoming Webhook 생성
   - https://api.slack.com/apps 에서 앱 생성
   - Incoming Webhooks 활성화
   - 채널에 Webhook 추가하고 URL 복사
2. 환경변수 또는 직접 URL 전달

피드백 기능:
- Bot User OAuth Token 필요 (xoxb-...)
- channels:history, channels:read 권한 필요
"""

import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta


def get_webhook_url(webhook_url=None):
    """
    Webhook URL 가져오기 (인자 > 환경변수 순서)
    """
    if webhook_url:
        return webhook_url
    return os.environ.get('SLACK_WEBHOOK_URL')


def generate_news_html_page(articles, output_dir=None, filename=None):
    """
    20개 전체 뉴스를 보여주는 HTML 페이지 생성 (이메일과 동일한 레이아웃)

    Args:
        articles: 뉴스 기사 리스트
        output_dir: 저장 디렉토리 (없으면 기본 경로 사용)
        filename: 파일명 (없으면 날짜 기반 자동 생성, 예: 2026-01-06.html)

    Returns:
        tuple: (파일 경로, 파일명)
    """
    # url/link 필드 정규화 (둘 다 지원)
    for article in articles:
        if 'link' not in article and 'url' in article:
            article['link'] = article['url']
        elif 'url' not in article and 'link' in article:
            article['url'] = article['link']

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    date_str = now.strftime("%Y년 %m월 %d일")
    date_filename = now.strftime("%Y-%m-%d")  # 날짜별 URL용

    if not output_dir:
        output_dir = os.path.join(os.path.dirname(__file__), 'news_pages')
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        filename = f"{date_filename}.html"

    output_path = os.path.join(output_dir, filename)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ONDA 뉴스 브리핑 - {date_str}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 25px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .header p {{
            margin: 8px 0 0 0;
            opacity: 0.9;
            font-size: 13px;
        }}
        .section-title {{
            background: #1a237e;
            color: white;
            padding: 8px 16px;
            border-radius: 5px;
            margin: 20px 0 12px 0;
            font-size: 14px;
            font-weight: bold;
        }}
        .top-article {{
            background: white;
            border-left: 5px solid #ff6f00;
            padding: 16px;
            margin-bottom: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }}
        .rank {{
            display: inline-block;
            background: #ff6f00;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }}
        .category {{
            display: inline-block;
            background: #e3f2fd;
            color: #1a237e;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            margin-left: 8px;
        }}
        .title {{
            font-size: 16px;
            font-weight: bold;
            color: #1a237e;
            margin: 10px 0 6px 0;
            line-height: 1.4;
        }}
        .title a {{
            color: #1a237e;
            text-decoration: none;
        }}
        .title a:hover {{
            text-decoration: underline;
        }}
        .summary {{
            color: #555;
            margin: 10px 0;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
            font-size: 13px;
            line-height: 1.6;
        }}
        .meta {{
            color: #888;
            font-size: 11px;
            margin-top: 8px;
        }}
        .link {{
            display: inline-block;
            background: #1a237e;
            color: white;
            padding: 6px 14px;
            text-decoration: none;
            border-radius: 4px;
            font-size: 12px;
            margin-top: 8px;
        }}
        .link:hover {{
            background: #0d47a1;
        }}
        /* 4~10위: 테이블 기반 2열 그리드 */
        .grid-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 8px;
        }}
        .grid-cell {{
            width: 50%;
            background: white;
            border-left: 3px solid #1a237e;
            padding: 12px;
            border-radius: 5px;
            vertical-align: top;
        }}
        .grid-rank {{
            display: inline-block;
            background: #1a237e;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: bold;
        }}
        .grid-title {{
            font-size: 13px;
            font-weight: bold;
            color: #333;
            margin: 8px 0 4px 0;
            line-height: 1.4;
        }}
        .grid-title a {{
            color: #1a237e;
            text-decoration: none;
        }}
        .grid-title a:hover {{
            text-decoration: underline;
        }}
        .grid-meta {{
            color: #888;
            font-size: 10px;
        }}
        /* 11~20위: 테이블 형식 */
        .news-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 5px;
            overflow: hidden;
            font-size: 12px;
        }}
        .news-table th {{
            background: #e8eaf6;
            color: #1a237e;
            padding: 8px 10px;
            text-align: left;
            font-weight: bold;
            font-size: 11px;
        }}
        .news-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
            vertical-align: middle;
        }}
        .news-table tr:last-child td {{
            border-bottom: none;
        }}
        .news-table tr:hover {{
            background: #f8f9fa;
        }}
        .table-rank {{
            background: #e8eaf6;
            color: #1a237e;
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 10px;
            font-weight: bold;
            white-space: nowrap;
        }}
        .table-title {{
            color: #333;
            font-weight: 500;
        }}
        .table-title a {{
            color: #1a237e;
            text-decoration: none;
        }}
        .table-title a:hover {{
            text-decoration: underline;
        }}
        .table-source {{
            color: #888;
            font-size: 10px;
            white-space: nowrap;
        }}
        .footer {{
            text-align: center;
            margin-top: 25px;
            padding: 15px;
            background: white;
            border-radius: 5px;
            color: #666;
            font-size: 11px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ONDA 뉴스 브리핑</h1>
        <p>B2B Hospitality Tech | {date_str} | TOP {len(articles)}</p>
    </div>

    <div class="section-title">🏆 TOP 3 주요 뉴스</div>
"""

    # TOP 3 상세 출력
    for idx, article in enumerate(articles[:3], 1):
        summary = article.get('detailed_summary', article.get('short_summary', article.get('summary', '')))
        if len(summary) > 180:
            summary = summary[:177] + "..."

        html += f"""
    <div class="top-article">
        <span class="rank">{idx}위</span>
        <span class="category">{article.get('category', '기타')}</span>
        <div class="title"><a href="{article['link']}" target="_blank">{article['title']}</a></div>
        <div class="summary">{summary if summary else '(요약 없음)'}</div>
        <div class="meta">출처: {article.get('source', '알 수 없음')} | 점수: {article.get('score', 0)}점</div>
        <a href="{article['link']}" target="_blank" class="link">기사 읽기 →</a>
    </div>
"""

    # 4~10위: 테이블 기반 2열 그리드
    if len(articles) > 3:
        html += '<div class="section-title">📰 4~10위 뉴스</div>'
        html += '<table class="grid-table"><tbody>'

        articles_4_10 = list(enumerate(articles[3:10], 4))
        for i in range(0, len(articles_4_10), 2):
            html += '<tr>'
            # 첫 번째 셀
            idx, article = articles_4_10[i]
            title = article['title']
            if len(title) > 45:
                title = title[:42] + "..."
            html += f'''
            <td class="grid-cell">
                <span class="grid-rank">{idx}위</span>
                <span class="category">{article.get('category', '기타')}</span>
                <div class="grid-title"><a href="{article['link']}" target="_blank">{title}</a></div>
                <div class="grid-meta">{article.get('source', '알 수 없음')} | {article.get('score', 0)}점</div>
            </td>
'''
            # 두 번째 셀 (있으면)
            if i + 1 < len(articles_4_10):
                idx2, article2 = articles_4_10[i + 1]
                title2 = article2['title']
                if len(title2) > 45:
                    title2 = title2[:42] + "..."
                html += f'''
            <td class="grid-cell">
                <span class="grid-rank">{idx2}위</span>
                <span class="category">{article2.get('category', '기타')}</span>
                <div class="grid-title"><a href="{article2['link']}" target="_blank">{title2}</a></div>
                <div class="grid-meta">{article2.get('source', '알 수 없음')} | {article2.get('score', 0)}점</div>
            </td>
'''
            else:
                html += '<td class="grid-cell" style="background:transparent;border:none;"></td>'
            html += '</tr>'

        html += '</tbody></table>'

    # 11~20위: 테이블 형식
    if len(articles) > 10:
        html += '<div class="section-title">📋 11~20위 뉴스</div>'
        html += '''
    <table class="news-table">
        <tr>
            <th style="width:40px;">순위</th>
            <th>제목</th>
            <th style="width:70px;">출처</th>
            <th style="width:50px;">점수</th>
        </tr>
'''

        for idx, article in enumerate(articles[10:20], 11):
            title = article['title']
            if len(title) > 50:
                title = title[:47] + "..."
            source = article.get('source', '알 수 없음')
            if len(source) > 8:
                source = source[:7] + ".."
            html += f"""
        <tr>
            <td><span class="table-rank">{idx}위</span></td>
            <td class="table-title"><a href="{article['link']}" target="_blank">{title}</a></td>
            <td class="table-source">{source}</td>
            <td class="table-source">{article.get('score', 0)}점</td>
        </tr>
"""

        html += '</table>'

    html += """
    <div class="footer">
        <p>이 페이지는 ONDA 뉴스 수집 시스템에서 자동으로 생성되었습니다.</p>
        <p>🤖 Powered by AI News Scraper</p>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path, filename


def create_slack_blocks(articles, is_draft=True, full_news_url=None):
    """
    Slack Block Kit 형식으로 뉴스 메시지 생성 (간소화 버전)

    Args:
        articles: 뉴스 기사 리스트 (슬랙에 표시할 TOP 기사들)
        is_draft: 초안 여부 (True면 검토용, False면 최종본)
        full_news_url: 20개 전체 뉴스 페이지 URL
    """
    # 한국 시간
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    date_str = now.strftime("%Y년 %m월 %d일")

    blocks = []

    # 헤더
    if is_draft:
        header_text = f"📰 ONDA 뉴스 초안 - {date_str}"
    else:
        header_text = f"📰 ONDA 뉴스 브리핑 - {date_str}"

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": header_text,
            "emoji": True
        }
    })

    # 초안일 경우 안내 메시지
    if is_draft:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*검토가 필요한 뉴스 {len(articles)}건입니다.*"
            }
        })
        blocks.append({"type": "divider"})

    # 기사 목록 (간소화: 한 줄씩)
    article_lines = []
    for i, article in enumerate(articles, 1):
        title = article.get('title', '제목 없음')
        # url/link 둘 다 지원
        link = article.get('url') or article.get('link', '#')
        source = article.get('source', '출처 미상')

        # 한 줄 포맷: 번호. 제목 | 출처
        article_lines.append(f"{i}. <{link}|{title}> | _{source}_")

    # 10개씩 나눠서 블록 생성 (슬랙 텍스트 길이 제한 때문)
    chunk_size = 10
    for i in range(0, len(article_lines), chunk_size):
        chunk = article_lines[i:i+chunk_size]
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(chunk)
            }
        })

    blocks.append({"type": "divider"})

    # 20개 전체 뉴스 더보기 버튼
    if full_news_url:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📋 <{full_news_url}|*20개 뉴스 전체 보기*>"
            }
        })
        blocks.append({"type": "divider"})

    # 푸터
    if is_draft:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 피드백은 이 스레드에 답글로 남겨주세요. 예: \"3번 제외\", \"AI 기사 더 추가\""
                }
            ]
        })
    else:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🤖 ONDA 뉴스 스크래퍼 | 총 {len(articles)}건"
                }
            ]
        })

    return blocks


def create_simple_slack_message(articles, is_draft=True, full_news_url=None):
    """
    Block Kit이 지원되지 않는 경우를 위한 간단한 텍스트 메시지
    """
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    date_str = now.strftime("%Y년 %m월 %d일")

    if is_draft:
        lines = [f"📝 *ONDA 뉴스 초안 - {date_str}*\n"]
    else:
        lines = [f"📰 *ONDA 뉴스 브리핑 - {date_str}*\n"]

    for i, article in enumerate(articles, 1):
        title = article.get('title', '제목 없음')
        link = article.get('link', '#')
        source = article.get('source', '출처 미상')
        lines.append(f"{i}. <{link}|{title}> | {source}")

    if full_news_url:
        lines.append(f"\n📋 <{full_news_url}|20개 뉴스 전체 보기>")

    if is_draft:
        lines.append("\n💡 피드백은 스레드에 답글로 남겨주세요.")

    return "\n".join(lines)


def send_to_slack(articles, webhook_url=None, is_draft=True, use_blocks=True, full_news_url=None):
    """
    Slack으로 뉴스 발송 (Webhook 사용)

    Args:
        articles: 뉴스 기사 리스트
        webhook_url: Slack Webhook URL (없으면 환경변수 사용)
        is_draft: 초안 여부
        use_blocks: Block Kit 사용 여부
        full_news_url: 20개 전체 뉴스 페이지 URL

    Returns:
        dict: {'success': bool, 'message': str}
    """
    url = get_webhook_url(webhook_url)

    if not url:
        return {
            'success': False,
            'message': 'Slack Webhook URL이 설정되지 않았습니다. SLACK_WEBHOOK_URL 환경변수를 설정하거나 webhook_url 인자를 전달하세요.'
        }

    if not articles:
        return {
            'success': False,
            'message': '발송할 기사가 없습니다.'
        }

    try:
        if use_blocks:
            payload = {
                "blocks": create_slack_blocks(articles, is_draft, full_news_url)
            }
        else:
            payload = {
                "text": create_simple_slack_message(articles, is_draft, full_news_url)
            }

        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        if response.status_code == 200:
            return {
                'success': True,
                'message': f'Slack으로 {len(articles)}건의 뉴스를 발송했습니다.'
            }
        else:
            return {
                'success': False,
                'message': f'Slack 발송 실패: {response.status_code} - {response.text}'
            }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'message': 'Slack 발송 타임아웃'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Slack 발송 오류: {str(e)}'
        }


def send_to_slack_via_bot(articles, channel_id, bot_token=None, is_draft=True, full_news_url=None):
    """
    Slack Bot API로 뉴스 발송 (thread_ts 반환 - 피드백 수집용)

    Args:
        articles: 뉴스 기사 리스트
        channel_id: 채널 ID (예: C07XXXXXX)
        bot_token: Bot User OAuth Token
        is_draft: 초안 여부
        full_news_url: 20개 전체 뉴스 페이지 URL

    Returns:
        dict: {'success': bool, 'message': str, 'thread_ts': str, 'channel': str}
    """
    token = get_bot_token(bot_token)

    if not token:
        return {
            'success': False,
            'message': 'Bot Token이 설정되지 않았습니다.'
        }

    if not articles:
        return {
            'success': False,
            'message': '발송할 기사가 없습니다.'
        }

    try:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "channel": channel_id,
            "blocks": create_slack_blocks(articles, is_draft, full_news_url),
            "text": f"ONDA 뉴스 {'초안' if is_draft else '브리핑'}",  # 알림용 fallback
            "unfurl_links": False,  # URL 미리보기 비활성화
            "unfurl_media": False   # 미디어 미리보기 비활성화
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()

        if data.get('ok'):
            return {
                'success': True,
                'message': f'Slack으로 {len(articles)}건의 뉴스를 발송했습니다.',
                'thread_ts': data.get('ts'),  # 피드백 수집에 필요
                'channel': data.get('channel')
            }
        else:
            return {
                'success': False,
                'message': f"Slack 발송 실패: {data.get('error')}"
            }

    except Exception as e:
        return {
            'success': False,
            'message': f'Slack 발송 오류: {str(e)}'
        }


def send_draft_for_review(articles, webhook_url=None, full_news_url=None):
    """
    검토용 초안 발송 (편의 함수)
    """
    return send_to_slack(articles, webhook_url, is_draft=True, full_news_url=full_news_url)


def send_final_to_client(articles, webhook_url=None, full_news_url=None):
    """
    클라이언트에게 최종본 발송 (편의 함수)
    """
    return send_to_slack(articles, webhook_url, is_draft=False, full_news_url=full_news_url)


# ============================================
# 피드백 수집 기능 (Slack Bot API 사용)
# ============================================

def get_bot_token(bot_token=None):
    """Bot User OAuth Token 가져오기"""
    if bot_token:
        return bot_token
    return os.environ.get('SLACK_BOT_TOKEN')


def get_channel_messages(channel_id, bot_token=None, limit=20):
    """
    채널의 최근 메시지 가져오기

    Args:
        channel_id: 슬랙 채널 ID (예: C07XXXXXX)
        bot_token: Bot User OAuth Token
        limit: 가져올 메시지 수

    Returns:
        list: 메시지 리스트
    """
    token = get_bot_token(bot_token)
    if not token:
        return {'success': False, 'error': 'Bot token이 설정되지 않았습니다.'}

    url = "https://slack.com/api/conversations.history"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "channel": channel_id,
        "limit": limit
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        data = response.json()

        if data.get('ok'):
            return {'success': True, 'messages': data.get('messages', [])}
        else:
            return {'success': False, 'error': data.get('error', 'Unknown error')}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_thread_replies(channel_id, thread_ts, bot_token=None):
    """
    특정 메시지의 스레드 답글 가져오기

    Args:
        channel_id: 슬랙 채널 ID
        thread_ts: 부모 메시지의 timestamp (스레드 ID)
        bot_token: Bot User OAuth Token

    Returns:
        list: 스레드 답글 리스트
    """
    token = get_bot_token(bot_token)
    if not token:
        return {'success': False, 'error': 'Bot token이 설정되지 않았습니다.'}

    url = "https://slack.com/api/conversations.replies"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {
        "channel": channel_id,
        "ts": thread_ts
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        data = response.json()

        if data.get('ok'):
            # 첫 번째 메시지는 부모 메시지이므로 제외
            replies = data.get('messages', [])[1:]
            return {'success': True, 'replies': replies}
        else:
            return {'success': False, 'error': data.get('error', 'Unknown error')}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def parse_feedback(feedback_text):
    """
    피드백 텍스트를 파싱하여 구조화된 명령으로 변환

    지원하는 피드백 형식:
    - "3번 제외" / "3 제외" / "3번 삭제" → 3번 기사 제외
    - "5번 위로" / "5번 올려" → 5번 기사 순위 올리기
    - "AI 기사 더" / "AI 더 추가" → AI 관련 기사 더 추가
    - "OTA 빼줘" / "플랫폼 제외" → 해당 카테고리 기사 제외
    - "1번이랑 3번 바꿔" → 1번과 3번 순서 교체

    Returns:
        list: 파싱된 명령 리스트
        [{'action': 'exclude', 'target': 3}, ...]
    """
    commands = []
    text = feedback_text.lower().strip()

    # 번호 제외 패턴: "3번 제외", "3 빼", "3번 삭제"
    exclude_pattern = r'(\d+)\s*번?\s*(제외|빼|삭제|제거)'
    for match in re.finditer(exclude_pattern, text):
        num = int(match.group(1))
        commands.append({'action': 'exclude', 'target': num})

    # 번호 올리기 패턴: "5번 위로", "5번 올려"
    up_pattern = r'(\d+)\s*번?\s*(위로|올려|상위|앞으로)'
    for match in re.finditer(up_pattern, text):
        num = int(match.group(1))
        commands.append({'action': 'move_up', 'target': num})

    # 번호 내리기 패턴: "5번 아래로", "5번 내려"
    down_pattern = r'(\d+)\s*번?\s*(아래로|내려|하위|뒤로)'
    for match in re.finditer(down_pattern, text):
        num = int(match.group(1))
        commands.append({'action': 'move_down', 'target': num})

    # 순서 교체 패턴: "1번이랑 3번 바꿔", "1, 3 교체", "1번 2번 위치 바꿔"
    swap_pattern = r'(\d+)\s*번?\s*(이랑|하고|,|과|와)?\s*(\d+)\s*번?\s*(위치\s*)?(바꿔|바꾸고|교체|스왑)'
    for match in re.finditer(swap_pattern, text):
        num1 = int(match.group(1))
        num2 = int(match.group(3))
        commands.append({'action': 'swap', 'target': (num1, num2)})

    # 교체 의미의 다른 패턴: "15번을 1번에 넣고 1번은 15번으로" → 15와 1 교체
    swap_pattern2 = r'(\d+)\s*번?\s*(을|를)?\s*(\d+)\s*번?\s*(에|으로)?\s*(넣고|하고)'
    for match in re.finditer(swap_pattern2, text):
        num1 = int(match.group(1))
        num2 = int(match.group(3))
        # 이미 같은 swap이 없을 때만 추가
        swap_exists = any(c['action'] == 'swap' and set(c['target']) == {num1, num2} for c in commands)
        if not swap_exists:
            commands.append({'action': 'swap', 'target': (num1, num2)})

    # 기사 추가 패턴: "17번 넣어", "15번 추가", "11번 넣고"
    add_pattern = r'(\d+)\s*번?\s*(넣어|넣고|추가|포함|살려)'
    for match in re.finditer(add_pattern, text):
        num = int(match.group(1))
        commands.append({'action': 'add', 'target': num})

    # 대체 패턴: "3번 대신 17번", "3번을 17번으로", "3번 17번으로 교체"
    replace_pattern = r'(\d+)\s*번?\s*(대신|을|를)?\s*(\d+)\s*번?\s*(으로|로)?\s*(교체|대체|바꿔)?'
    for match in re.finditer(replace_pattern, text):
        # "대신" 또는 "으로 교체/대체" 패턴이 있을 때만
        if match.group(2) == '대신' or match.group(5) in ['교체', '대체']:
            old_num = int(match.group(1))
            new_num = int(match.group(3))
            commands.append({'action': 'replace', 'target': (old_num, new_num)})

    # 카테고리 더 추가 패턴: "AI 더", "스타트업 더 추가"
    more_pattern = r'(ai|인공지능|ota|플랫폼|호텔|숙박|여행|스타트업|정책|규제)\s*(기사\s*)?(더|추가|늘려)'
    for match in re.finditer(more_pattern, text):
        category = match.group(1)
        commands.append({'action': 'add_more', 'target': category})

    # 카테고리 제외 패턴: "AI 빼", "스타트업 제외"
    less_pattern = r'(ai|인공지능|ota|플랫폼|호텔|숙박|여행|스타트업|정책|규제)\s*(기사\s*)?(빼|제외|삭제|줄여)'
    for match in re.finditer(less_pattern, text):
        category = match.group(1)
        commands.append({'action': 'exclude_category', 'target': category})

    # 승인 패턴: "확인", "좋아", "발송해", "괜찮아"
    approve_pattern = r'(확인|좋아|ok|발송|보내|괜찮|승인|ㅇㅋ|완료)'
    if re.search(approve_pattern, text):
        commands.append({'action': 'approve'})

    return commands


def apply_feedback_to_articles(articles, commands, all_articles=None):
    """
    피드백 명령을 기사 리스트에 적용

    Args:
        articles: 현재 선택된 기사 리스트 (10개)
        commands: parse_feedback()에서 반환된 명령 리스트
        all_articles: 전체 기사 리스트 (20개) - add/replace 시 필요

    Returns:
        tuple: (수정된 기사 리스트, 변경 내역 문자열)
    """
    result = articles.copy()
    changes = []

    for cmd in commands:
        action = cmd['action']
        target = cmd.get('target')

        if action == 'exclude':
            # 번호는 1부터 시작, 인덱스는 0부터
            idx = target - 1
            if 0 <= idx < len(result):
                removed = result.pop(idx)
                changes.append(f"✓ {target}번 '{removed['title'][:20]}...' 제외됨")

        elif action == 'move_up':
            idx = target - 1
            if 0 < idx < len(result):  # 첫 번째가 아니면
                result[idx], result[idx-1] = result[idx-1], result[idx]
                changes.append(f"✓ {target}번 기사를 위로 이동")

        elif action == 'move_down':
            idx = target - 1
            if 0 <= idx < len(result) - 1:  # 마지막이 아니면
                result[idx], result[idx+1] = result[idx+1], result[idx]
                changes.append(f"✓ {target}번 기사를 아래로 이동")

        elif action == 'swap':
            num1, num2 = target[0], target[1]
            idx1, idx2 = num1 - 1, num2 - 1

            # 둘 다 현재 목록 내에 있으면 기존 swap
            if 0 <= idx1 < len(result) and 0 <= idx2 < len(result):
                result[idx1], result[idx2] = result[idx2], result[idx1]
                changes.append(f"✓ {num1}번과 {num2}번 순서 교체")
            # 하나가 범위 밖이면 all_articles에서 가져와서 대체
            elif all_articles:
                # idx2가 현재 목록 내, idx1은 all_articles에서 가져옴 (예: "15번을 1번에")
                if 0 <= idx2 < len(result) and 0 <= idx1 < len(all_articles):
                    new_article = all_articles[idx1]
                    old_article = result[idx2]
                    result[idx2] = new_article
                    changes.append(f"✓ {num2}번 위치에 {num1}번 '{new_article['title'][:20]}...' 삽입 (기존: '{old_article['title'][:15]}...')")
                # idx1이 현재 목록 내, idx2는 all_articles에서 가져옴
                elif 0 <= idx1 < len(result) and 0 <= idx2 < len(all_articles):
                    new_article = all_articles[idx2]
                    old_article = result[idx1]
                    result[idx1] = new_article
                    changes.append(f"✓ {num1}번 위치에 {num2}번 '{new_article['title'][:20]}...' 삽입 (기존: '{old_article['title'][:15]}...')")
                else:
                    changes.append(f"⚠ {num1}번 또는 {num2}번 기사를 찾을 수 없음")
            else:
                changes.append(f"⚠ {num1}번 또는 {num2}번이 범위를 벗어남 (전체 기사 목록 필요)")

        elif action == 'add':
            # 전체 기사에서 해당 번호 기사를 추가
            if all_articles:
                idx = target - 1
                if 0 <= idx < len(all_articles):
                    article_to_add = all_articles[idx]
                    # 이미 있는지 확인 (제목으로)
                    if not any(a['title'] == article_to_add['title'] for a in result):
                        result.append(article_to_add)
                        changes.append(f"✓ {target}번 '{article_to_add['title'][:20]}...' 추가됨")
                    else:
                        changes.append(f"⚠ {target}번 기사는 이미 포함되어 있음")
                else:
                    changes.append(f"⚠ {target}번 기사를 찾을 수 없음")
            else:
                changes.append(f"⚠ 전체 기사 목록이 없어 {target}번 추가 불가")

        elif action == 'replace':
            # old_num 기사를 new_num 기사로 대체
            old_num, new_num = target
            old_idx = old_num - 1
            if all_articles:
                new_idx = new_num - 1
                if 0 <= old_idx < len(result) and 0 <= new_idx < len(all_articles):
                    old_article = result[old_idx]
                    new_article = all_articles[new_idx]
                    result[old_idx] = new_article
                    changes.append(f"✓ {old_num}번 → {new_num}번으로 교체 ('{new_article['title'][:20]}...')")
                else:
                    changes.append(f"⚠ {old_num}번 또는 {new_num}번 기사를 찾을 수 없음")
            else:
                changes.append(f"⚠ 전체 기사 목록이 없어 교체 불가")

        elif action == 'approve':
            changes.append("✓ 승인됨 - 최종 발송 준비 완료")

    return result, "\n".join(changes) if changes else "변경사항 없음"


def collect_feedback_from_thread(channel_id, thread_ts, bot_token=None):
    """
    스레드에서 모든 피드백을 수집하고 파싱

    Args:
        channel_id: 채널 ID
        thread_ts: 초안 메시지의 timestamp
        bot_token: Bot token

    Returns:
        dict: {
            'success': bool,
            'commands': list,  # 파싱된 모든 명령
            'raw_feedback': list,  # 원본 피드백 텍스트들
            'approved': bool  # 승인 여부
        }
    """
    result = get_thread_replies(channel_id, thread_ts, bot_token)

    if not result['success']:
        return {'success': False, 'error': result['error']}

    all_commands = []
    raw_feedback = []
    approved = False

    for reply in result['replies']:
        text = reply.get('text', '')
        if text:
            raw_feedback.append(text)
            commands = parse_feedback(text)
            all_commands.extend(commands)

            # 승인 여부 체크
            if any(cmd['action'] == 'approve' for cmd in commands):
                approved = True

    return {
        'success': True,
        'commands': all_commands,
        'raw_feedback': raw_feedback,
        'approved': approved
    }


def send_feedback_summary_to_thread(channel_id, thread_ts, changes_summary, bot_token=None):
    """
    피드백 처리 결과를 스레드에 답글로 전송
    """
    token = get_bot_token(bot_token)
    if not token:
        return {'success': False, 'error': 'Bot token 없음'}

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "channel": channel_id,
        "thread_ts": thread_ts,
        "text": f"📝 피드백 처리 완료:\n{changes_summary}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        return {'success': data.get('ok'), 'error': data.get('error')}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_updated_draft_to_thread(channel_id, thread_ts, articles, changes_summary, bot_token=None, full_news_url=None):
    """
    피드백 처리 후 수정된 기사 목록을 스레드에 표시

    Args:
        channel_id: 채널 ID
        thread_ts: 스레드 timestamp
        articles: 수정된 기사 리스트
        changes_summary: 변경 내역
        bot_token: Bot token
        full_news_url: 전체 뉴스 페이지 URL
    """
    token = get_bot_token(bot_token)
    if not token:
        return {'success': False, 'error': 'Bot token 없음'}

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 변경 내역 + 수정된 기사 블록 생성
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📝 *피드백 반영 완료*\n```{changes_summary}```"
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "📰 *수정된 뉴스 목록:*"
            }
        }
    ]

    # 수정된 기사 추가
    for i, article in enumerate(articles, 1):
        title = article.get('title', '제목 없음')
        url_link = article.get('url') or article.get('link', '#')
        source = article.get('source', '')
        category = article.get('category', '')

        article_text = f"*{i}. <{url_link}|{title}>*"
        if category:
            article_text += f"\n`{category}`"
        if source:
            article_text += f" | {source}"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": article_text
            }
        })

    # 승인 요청 메시지
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "✅ 이대로 발송하려면 *\"확인\"* 또는 *\"발송\"*이라고 답글 달아주세요.\n🔄 추가 수정이 필요하면 피드백을 계속 달아주세요."
        }
    })

    # 20개 전체보기 링크
    if full_news_url:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📋 <{full_news_url}|20개 전체 뉴스 보기>"
            }
        })

    payload = {
        "channel": channel_id,
        "thread_ts": thread_ts,
        "blocks": blocks,
        "text": f"피드백 반영 완료 - {len(articles)}건"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        return {'success': data.get('ok'), 'error': data.get('error')}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def review_and_send_workflow(articles, review_channel_id, final_webhook_url, bot_token=None, full_news_url=None):
    """
    전체 검토 워크플로우 실행

    1. 검토 채널에 초안 발송
    2. 피드백 대기 (수동으로 호출)
    3. 피드백 수집 및 적용
    4. 최종본 발송

    Args:
        articles: 뉴스 기사 리스트
        review_channel_id: 검토용 Slack 채널 ID
        final_webhook_url: 최종 발송할 Webhook URL
        bot_token: Bot Token
        full_news_url: 전체 뉴스 페이지 URL

    Returns:
        dict: 워크플로우 상태 정보
    """
    # 1. 초안 발송
    draft_result = send_to_slack_via_bot(
        articles,
        review_channel_id,
        bot_token,
        is_draft=True,
        full_news_url=full_news_url
    )

    if not draft_result['success']:
        return {
            'step': 'draft',
            'success': False,
            'error': draft_result['message']
        }

    return {
        'step': 'draft_sent',
        'success': True,
        'thread_ts': draft_result['thread_ts'],
        'channel': draft_result['channel'],
        'message': '초안이 발송되었습니다. 피드백 후 process_feedback_and_send()를 호출하세요.'
    }


def process_feedback_and_send(articles, review_channel_id, thread_ts, final_webhook_url, bot_token=None, full_news_url=None, all_articles=None):
    """
    피드백 수집 후 최종 발송

    Args:
        articles: 현재 선택된 기사 리스트 (10개)
        review_channel_id: 검토 채널 ID
        thread_ts: 초안 메시지의 thread_ts
        final_webhook_url: 최종 발송 Webhook URL
        bot_token: Bot Token
        full_news_url: 전체 뉴스 페이지 URL
        all_articles: 전체 기사 리스트 (20개) - "17번 넣어" 같은 피드백 처리용

    Returns:
        dict: 처리 결과
    """
    # 1. 피드백 수집
    feedback = collect_feedback_from_thread(review_channel_id, thread_ts, bot_token)

    if not feedback['success']:
        return {
            'success': False,
            'step': 'feedback_collection',
            'error': feedback['error']
        }

    # 2. 피드백 적용 (all_articles 전달)
    modified_articles, changes = apply_feedback_to_articles(articles, feedback['commands'], all_articles)

    # 3. 피드백 처리 결과를 스레드에 알림
    send_feedback_summary_to_thread(review_channel_id, thread_ts, changes, bot_token)

    # 4. 승인 확인
    if not feedback['approved']:
        return {
            'success': True,
            'step': 'waiting_approval',
            'modified_articles': modified_articles,
            'changes': changes,
            'message': '피드백이 적용되었습니다. "확인" 또는 "발송" 피드백 후 다시 호출하세요.'
        }

    # 5. 최종 발송
    final_result = send_to_slack(
        modified_articles,
        final_webhook_url,
        is_draft=False,
        full_news_url=full_news_url
    )

    return {
        'success': final_result['success'],
        'step': 'final_sent',
        'modified_articles': modified_articles,
        'changes': changes,
        'message': final_result['message']
    }


# 테스트용
if __name__ == "__main__":
    # 테스트 기사
    test_articles = [
        {
            'title': '야놀자, 글로벌 호텔 체인과 전략적 파트너십 체결',
            'link': 'https://example.com/1',
            'source': '한국경제',
            'category': 'OTA/플랫폼',
            'score': 85,
            'summary': '야놀자가 글로벌 호텔 체인과 기술 협력 파트너십을 체결했다.'
        },
        {
            'title': '정부, 숙박업 규제 완화 방안 발표',
            'link': 'https://example.com/2',
            'source': '연합뉴스',
            'category': '정책/규제',
            'score': 90,
            'summary': '문화체육관광부가 숙박업 관련 규제 완화 방안을 발표했다.'
        },
        {
            'title': 'AI 기반 호텔 예약 시스템 스타트업 시리즈A 투자 유치',
            'link': 'https://example.com/3',
            'source': '스타트업투데이',
            'category': '스타트업',
            'score': 75,
            'summary': 'AI 호텔 예약 시스템 스타트업이 100억원 규모 투자를 유치했다.'
        }
    ]

    # HTML 페이지 생성 테스트
    html_path = generate_news_html_page(test_articles)
    print(f"HTML 페이지 생성: {html_path}")

    # 블록 미리보기 출력
    blocks = create_slack_blocks(test_articles, is_draft=True, full_news_url="https://example.com/full-news")
    print("\n=== Slack Block Kit Preview ===")
    print(json.dumps(blocks, ensure_ascii=False, indent=2))
