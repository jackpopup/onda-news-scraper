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
    3단계 레이아웃: TOP 3 상세 카드 / 4-10위 2열 그리드 / 11-20위 테이블

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

    # TOP 3 상세 카드
    top3_html = ""
    rank_badges = ["1st", "2nd", "3rd"]
    rank_colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
    for i, article in enumerate(articles[:3]):
        summary = article.get('short_summary', article.get('summary', ''))[:150]
        category = article.get('category', '')
        top3_html += f"""
        <div class="top-card">
            <div class="card-header">
                <span class="rank-badge" style="background: {rank_colors[i]};">{rank_badges[i]}</span>
                <span class="category-tag">{category}</span>
            </div>
            <h3 class="card-title">
                <a href="{article.get('link', '#')}" target="_blank">{article.get('title', '')}</a>
            </h3>
            <p class="card-summary">{summary}</p>
            <div class="card-meta">
                <span>출처: {article.get('source', '')}</span>
                <span>점수: {article.get('score', 0)}점</span>
            </div>
            <a href="{article.get('link', '#')}" target="_blank" class="read-more">기사 원문 보기 →</a>
        </div>
        """

    # 4-10위 2열 그리드
    grid_html = ""
    for i, article in enumerate(articles[3:10], 4):
        category = article.get('category', '')
        grid_html += f"""
        <div class="grid-card">
            <div class="grid-rank">{i}위</div>
            <span class="grid-category">{category}</span>
            <h4 class="grid-title">
                <a href="{article.get('link', '#')}" target="_blank">{article.get('title', '')}</a>
            </h4>
            <div class="grid-meta">{article.get('source', '')} | 점수: {article.get('score', 0)}점</div>
        </div>
        """

    # 11-20위 테이블
    table_rows = ""
    for i, article in enumerate(articles[10:20], 11):
        table_rows += f"""
        <tr>
            <td class="rank-cell">{i}위</td>
            <td class="title-cell">
                <a href="{article.get('link', '#')}" target="_blank">{article.get('title', '')}</a>
            </td>
            <td class="source-cell">{article.get('source', '')}</td>
            <td class="score-cell">{article.get('score', 0)}점</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ONDA 뉴스 브리핑 - {date_str}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f7fa;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}

        /* 헤더 */
        .header {{
            background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(26,35,126,0.3);
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        .header .subtitle {{
            font-size: 14px;
            opacity: 0.9;
        }}

        /* 섹션 타이틀 */
        .section-title {{
            background: linear-gradient(90deg, #1a237e 0%, #3949ab 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            margin: 25px 0 20px 0;
            font-size: 16px;
            font-weight: 600;
        }}

        /* TOP 3 카드 */
        .top-card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            border-left: 4px solid #1a237e;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}
        .rank-badge {{
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }}
        .category-tag {{
            background: #e8eaf6;
            color: #3949ab;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .card-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
            line-height: 1.4;
        }}
        .card-title a {{
            color: #1a237e;
            text-decoration: none;
        }}
        .card-title a:hover {{
            text-decoration: underline;
        }}
        .card-summary {{
            color: #666;
            font-size: 14px;
            margin-bottom: 15px;
            line-height: 1.6;
        }}
        .card-meta {{
            display: flex;
            gap: 20px;
            color: #888;
            font-size: 13px;
            margin-bottom: 12px;
        }}
        .read-more {{
            display: inline-block;
            color: #1a237e;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
        }}
        .read-more:hover {{
            text-decoration: underline;
        }}

        /* 4-10위 그리드 */
        .grid-container {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }}
        .grid-card {{
            background: white;
            border-radius: 10px;
            padding: 18px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        .grid-rank {{
            display: inline-block;
            background: #1a237e;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .grid-category {{
            display: inline-block;
            background: #e8eaf6;
            color: #3949ab;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 8px;
        }}
        .grid-title {{
            font-size: 14px;
            font-weight: 600;
            margin: 10px 0;
            line-height: 1.4;
        }}
        .grid-title a {{
            color: #333;
            text-decoration: none;
        }}
        .grid-title a:hover {{
            color: #1a237e;
        }}
        .grid-meta {{
            color: #888;
            font-size: 12px;
        }}

        /* 11-20위 테이블 */
        .table-container {{
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #f8f9fa;
            padding: 14px 16px;
            text-align: left;
            font-size: 13px;
            font-weight: 600;
            color: #555;
            border-bottom: 2px solid #e0e0e0;
        }}
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid #f0f0f0;
            font-size: 13px;
        }}
        tr:hover {{
            background: #fafafa;
        }}
        .rank-cell {{
            width: 60px;
            font-weight: 600;
            color: #1a237e;
        }}
        .title-cell a {{
            color: #333;
            text-decoration: none;
        }}
        .title-cell a:hover {{
            color: #1a237e;
        }}
        .source-cell {{
            width: 100px;
            color: #888;
        }}
        .score-cell {{
            width: 70px;
            color: #888;
            text-align: right;
        }}

        /* 푸터 */
        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 40px;
            padding: 20px;
        }}

        /* 반응형 */
        @media (max-width: 600px) {{
            .grid-container {{
                grid-template-columns: 1fr;
            }}
            .card-meta {{
                flex-direction: column;
                gap: 5px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ONDA 뉴스 브리핑</h1>
            <p class="subtitle">B2B Hospitality Tech | {date_str} | TOP 20</p>
        </div>

        <div class="section-title">TOP 3 주요 뉴스</div>
        {top3_html}

        <div class="section-title">4-10위 뉴스</div>
        <div class="grid-container">
            {grid_html}
        </div>

        <div class="section-title">11-20위 뉴스</div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>순위</th>
                        <th>제목</th>
                        <th>출처</th>
                        <th>점수</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>

        <div class="footer">
            이 페이지는 ONDA 뉴스 수집 시스템에서 자동으로 생성되었습니다.<br>
            Powered by AI News Scraper
        </div>
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
        summary = article.get('short_summary', '') or article.get('summary', '')
        summary = summary[:100] if summary else ''

        # 요약이 있으면 포함, 없으면 제목/출처만 표시
        if summary:
            text = f"{medals[i]} *<{link}|{title}>*\n_{source} | {category}_\n{summary}"
        else:
            text = f"{medals[i]} *<{link}|{title}>*\n_{source} | {category}_"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
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
