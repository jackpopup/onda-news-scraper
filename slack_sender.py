"""
ONDA News Slack Sender (v2 - 이모지 기반 피드백)

워크플로우:
1. 06:00 - 20개 기사를 Slack에 발송 (각 기사별 메시지)
2. 06:00~08:00 - 사용자가 :star: 이모지로 TOP 3 선택
3. 08:00 - 이모지 확인 후 최종 발송
"""

import requests
import json
import os
from datetime import datetime, timezone, timedelta


def get_bot_token(bot_token=None):
    """Bot Token 가져오기"""
    if bot_token:
        return bot_token
    return os.environ.get('SLACK_BOT_TOKEN')


def get_channel_id(channel_id=None):
    """Channel ID 가져오기"""
    if channel_id:
        return channel_id
    return os.environ.get('SLACK_CHANNEL_ID', 'C0A7D41B3ED')


# =============================================================================
# HTML 페이지 생성
# =============================================================================

def generate_news_html_page(articles, output_dir=None, filename=None):
    """
    20개 전체 뉴스를 보여주는 HTML 페이지 생성

    Returns:
        tuple: (파일 경로, 파일명)
    """
    # url/link 필드 정규화
    for article in articles:
        if 'link' not in article and 'url' in article:
            article['link'] = article['url']
        elif 'url' not in article and 'link' in article:
            article['url'] = article['link']

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    date_str = now.strftime("%Y년 %m월 %d일")
    date_filename = now.strftime("%Y-%m-%d")

    if not output_dir:
        output_dir = os.path.join(os.path.dirname(__file__), 'news_pages')
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        filename = f"{date_filename}.html"

    output_path = os.path.join(output_dir, filename)

    # TOP 3 카드
    top3_html = ""
    for i, article in enumerate(articles[:3], 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        summary = article.get('short_summary', article.get('summary', ''))[:100]
        top3_html += f"""
        <div class="top-card">
            <div class="rank">{medal} {i}위</div>
            <h3><a href="{article.get('link', '#')}" target="_blank">{article.get('title', '')}</a></h3>
            <p class="summary">{summary}</p>
            <div class="meta">{article.get('source', '')} | {article.get('category', '')}</div>
        </div>
        """

    # 4~20위 테이블
    table_rows = ""
    for i, article in enumerate(articles[3:20], 4):
        table_rows += f"""
        <tr>
            <td class="rank-cell">{i}</td>
            <td><a href="{article.get('link', '#')}" target="_blank">{article.get('title', '')}</a></td>
            <td>{article.get('source', '')}</td>
            <td>{article.get('category', '')}</td>
        </tr>
        """

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
        .header h1 {{ margin: 0; font-size: 24px; }}
        .header p {{ margin: 8px 0 0 0; opacity: 0.9; font-size: 13px; }}
        .section-title {{
            background: #1a237e;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            margin: 20px 0 15px 0;
            font-size: 16px;
        }}
        .top-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .top-card .rank {{
            color: #1a237e;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .top-card h3 {{
            margin: 0 0 10px 0;
            font-size: 18px;
        }}
        .top-card h3 a {{
            color: #333;
            text-decoration: none;
        }}
        .top-card h3 a:hover {{
            color: #1a237e;
            text-decoration: underline;
        }}
        .top-card .summary {{
            color: #666;
            font-size: 14px;
            margin: 0 0 10px 0;
        }}
        .top-card .meta {{
            color: #999;
            font-size: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}
        .rank-cell {{
            width: 40px;
            text-align: center;
            font-weight: bold;
            color: #1a237e;
        }}
        td a {{
            color: #333;
            text-decoration: none;
        }}
        td a:hover {{
            color: #1a237e;
            text-decoration: underline;
        }}
        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 30px;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ONDA 뉴스 브리핑</h1>
        <p>{date_str} | B2B Hospitality Tech</p>
    </div>

    <div class="section-title">TOP 3 주요 뉴스</div>
    {top3_html}

    <div class="section-title">4~20위 뉴스</div>
    <table>
        <thead>
            <tr>
                <th>순위</th>
                <th>제목</th>
                <th>출처</th>
                <th>분류</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>

    <div class="footer">
        ONDA News Scraper | 자동 생성된 뉴스 브리핑
    </div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return (output_path, filename)


# =============================================================================
# 06:00 - 초안 발송 (20개 기사 개별 메시지)
# =============================================================================

def send_draft_articles(articles, channel_id=None, bot_token=None):
    """
    20개 기사를 개별 메시지로 발송 (이모지 선택용)
    각 메시지에 번호 이모지 추가

    Returns:
        dict: {success, message_ts_list, header_ts}
    """
    bot_token = get_bot_token(bot_token)
    channel_id = get_channel_id(channel_id)

    if not bot_token:
        return {'success': False, 'message': 'Bot token not found'}

    headers = {
        'Authorization': f'Bearer {bot_token}',
        'Content-Type': 'application/json'
    }

    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime('%Y년 %m월 %d일')

    # 1. 헤더 메시지 발송
    header_blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📰 ONDA 뉴스 브리핑 - {today}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*TOP 3로 선정할 기사에 ⭐ 이모지를 달아주세요!*\n08:00에 선택된 기사가 최종 발송됩니다."
            }
        },
        {"type": "divider"}
    ]

    response = requests.post(
        'https://slack.com/api/chat.postMessage',
        headers=headers,
        json={
            'channel': channel_id,
            'blocks': header_blocks,
            'text': f'ONDA 뉴스 브리핑 - {today}'
        }
    )

    result = response.json()
    if not result.get('ok'):
        return {'success': False, 'message': result.get('error', 'Header send failed')}

    header_ts = result.get('ts')
    message_ts_list = []

    # 2. 각 기사를 개별 메시지로 발송
    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟',
                     '1️⃣1️⃣', '1️⃣2️⃣', '1️⃣3️⃣', '1️⃣4️⃣', '1️⃣5️⃣', '1️⃣6️⃣', '1️⃣7️⃣', '1️⃣8️⃣', '1️⃣9️⃣', '2️⃣0️⃣']

    for i, article in enumerate(articles[:20]):
        emoji = number_emojis[i] if i < len(number_emojis) else f"#{i+1}"
        title = article.get('title', '제목 없음')
        source = article.get('source', '')
        category = article.get('category', '')
        link = article.get('link', article.get('url', '#'))
        summary = article.get('short_summary', article.get('summary', ''))[:80]

        text = f"{emoji} *<{link}|{title}>*\n_{source} | {category}_\n{summary}..."

        response = requests.post(
            'https://slack.com/api/chat.postMessage',
            headers=headers,
            json={
                'channel': channel_id,
                'text': text,
                'unfurl_links': False
            }
        )

        result = response.json()
        if result.get('ok'):
            message_ts_list.append({
                'ts': result.get('ts'),
                'index': i,
                'title': title
            })

    # 3. 메시지 정보 저장 (08:00에 이모지 확인용)
    save_draft_info(channel_id, header_ts, message_ts_list, articles)

    return {
        'success': True,
        'header_ts': header_ts,
        'message_ts_list': message_ts_list,
        'message': f'{len(message_ts_list)}개 기사 발송 완료'
    }


def save_draft_info(channel_id, header_ts, message_ts_list, articles):
    """초안 정보를 JSON 파일로 저장"""
    data = {
        'channel_id': channel_id,
        'header_ts': header_ts,
        'message_ts_list': message_ts_list,
        'articles': articles[:20],
        'sent_at': datetime.now().isoformat()
    }

    with open('draft_info.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# 08:00 - 이모지 확인 및 최종 발송
# =============================================================================

def get_starred_articles(channel_id=None, bot_token=None):
    """
    ⭐ 이모지가 달린 기사들 확인

    Returns:
        list: 선택된 기사 인덱스 리스트 (최대 3개)
    """
    bot_token = get_bot_token(bot_token)
    channel_id = get_channel_id(channel_id)

    # 저장된 초안 정보 로드
    try:
        with open('draft_info.json', 'r', encoding='utf-8') as f:
            draft_info = json.load(f)
    except FileNotFoundError:
        return []

    headers = {
        'Authorization': f'Bearer {bot_token}',
        'Content-Type': 'application/json'
    }

    starred_indices = []

    print(f"[DEBUG] Checking {len(draft_info.get('message_ts_list', []))} messages for reactions...")

    # 각 메시지의 reactions 확인
    for msg_info in draft_info.get('message_ts_list', []):
        ts = msg_info.get('ts')
        idx = msg_info.get('index')

        response = requests.get(
            'https://slack.com/api/reactions.get',
            headers=headers,
            params={
                'channel': channel_id,
                'timestamp': ts
            }
        )

        result = response.json()
        if result.get('ok'):
            message = result.get('message', {})
            reactions = message.get('reactions', [])

            # ⭐ (star) 이모지 확인
            for reaction in reactions:
                if reaction.get('name') == 'star':
                    print(f"[DEBUG] Found ⭐ on message index {idx}: {msg_info.get('title', '')[:30]}")
                    starred_indices.append(idx)
                    break
        else:
            print(f"[DEBUG] API error for message {idx}: {result.get('error')}")

    print(f"[DEBUG] Starred indices: {starred_indices}")

    # 최대 3개만 반환 (먼저 선택된 순서)
    return starred_indices[:3]


def send_final_news(top3_indices=None, channel_id=None, bot_token=None, full_news_url=None):
    """
    최종 뉴스 발송 (Slack)

    Args:
        top3_indices: TOP 3 기사 인덱스 리스트 (없으면 자동 확인)
        full_news_url: 20개 전체보기 URL
    """
    bot_token = get_bot_token(bot_token)
    channel_id = get_channel_id(channel_id)

    # 저장된 초안 정보 로드
    try:
        with open('draft_info.json', 'r', encoding='utf-8') as f:
            draft_info = json.load(f)
    except FileNotFoundError:
        return {'success': False, 'message': 'draft_info.json not found'}

    articles = draft_info.get('articles', [])

    # 이모지로 선택된 기사 확인
    if top3_indices is None:
        top3_indices = get_starred_articles(channel_id, bot_token)

    # 선택된 기사가 없으면 AI 선정 (상위 3개)
    if not top3_indices:
        top3_indices = [0, 1, 2]
        selection_note = "(AI 자동 선정)"
    else:
        selection_note = "(에디터 선정)"

    # TOP 3 기사 추출
    top3_articles = [articles[i] for i in top3_indices if i < len(articles)]

    headers = {
        'Authorization': f'Bearer {bot_token}',
        'Content-Type': 'application/json'
    }

    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime('%Y년 %m월 %d일')

    # 최종 메시지 블록 구성
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📰 ONDA 뉴스 브리핑 - {today}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*오늘의 TOP 3 뉴스* {selection_note}"
            }
        },
        {"type": "divider"}
    ]

    # TOP 3 기사 추가
    medals = ["🥇", "🥈", "🥉"]
    for i, article in enumerate(top3_articles):
        title = article.get('title', '제목 없음')
        source = article.get('source', '')
        category = article.get('category', '')
        link = article.get('link', article.get('url', '#'))
        summary = article.get('short_summary', article.get('summary', ''))[:100]

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{medals[i]} *<{link}|{title}>*\n_{source} | {category}_\n{summary}"
            }
        })

    # 20개 전체보기 링크
    if full_news_url:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📋 *<{full_news_url}|20개 전체 뉴스 보기>*"
            }
        })

    # 발송
    response = requests.post(
        'https://slack.com/api/chat.postMessage',
        headers=headers,
        json={
            'channel': channel_id,
            'blocks': blocks,
            'text': f'ONDA 뉴스 브리핑 - {today}'
        }
    )

    result = response.json()
    if result.get('ok'):
        return {
            'success': True,
            'ts': result.get('ts'),
            'top3_indices': top3_indices,
            'selection_note': selection_note
        }
    else:
        return {'success': False, 'message': result.get('error')}


# =============================================================================
# 하위 호환성을 위한 기존 함수 (단순화)
# =============================================================================

def send_to_slack_via_bot(articles, channel_id=None, bot_token=None, is_draft=True, full_news_url=None):
    """
    기존 코드 호환용 함수
    """
    if is_draft:
        return send_draft_articles(articles, channel_id, bot_token)
    else:
        return send_final_news(channel_id=channel_id, bot_token=bot_token, full_news_url=full_news_url)


# =============================================================================
# CLI 테스트
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='ONDA News Slack Sender')
    parser.add_argument('--draft', action='store_true', help='Send draft (20 articles)')
    parser.add_argument('--final', action='store_true', help='Send final (check emoji, send TOP 3)')
    parser.add_argument('--check', action='store_true', help='Check starred articles')

    args = parser.parse_args()

    if args.check:
        starred = get_starred_articles()
        print(f"Starred articles: {starred}")
    elif args.final:
        result = send_final_news()
        print(f"Final send result: {result}")
    else:
        print("Use --draft, --final, or --check")
