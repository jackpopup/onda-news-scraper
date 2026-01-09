"""
WeeklyON 뉴스레터 자동 생성기

사용법:
1. 메인 콘텐츠(제목 + 본문) 입력
2. 스크랩된 뉴스에서 키워드 뉴스 후보 10개 제시
3. 5개 선택 후 완성된 뉴스레터 Google Docs 형식으로 출력

출력:
- Google Docs에 복사 가능한 형식
- HTML 파일 (웹 발행용)
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta


def load_scraped_news(json_path='latest_news.json'):
    """스크랩된 뉴스 로드"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('top_20', [])
    except FileNotFoundError:
        print(f"❌ {json_path} 파일을 찾을 수 없습니다.")
        return []


def generate_intro_summary(main_title, main_content, news_list):
    """
    오늘의 위클리온 섹션 생성 (3개 요약)
    - 메인 콘텐츠에서 1개
    - 스크랩 뉴스에서 2개
    """
    # 메인 콘텐츠 요약 (첫 문장 추출)
    first_sentence = main_content.split('.')[0] + '.'
    if len(first_sentence) > 80:
        first_sentence = first_sentence[:77] + '...'

    intro_items = [
        f"🏠 {main_title[:50]}{'...' if len(main_title) > 50 else ''}"
    ]

    # 스크랩 뉴스에서 2개 추가
    for news in news_list[:2]:
        title = news.get('title', '')[:50]
        if len(news.get('title', '')) > 50:
            title += '...'
        category = news.get('category', '')
        if 'OTA' in category or '플랫폼' in category:
            emoji = "💡"
        elif '정책' in category or '규제' in category:
            emoji = "📋"
        else:
            emoji = "⌨️"
        intro_items.append(f"{emoji} {title}")

    return intro_items


def select_trend_article(news_list):
    """
    호스피탈리티 트렌드 기사 자동 선택
    - OTA/플랫폼 또는 트래블테크 카테고리 우선
    - 임팩트 점수 높은 순
    """
    trend_categories = ['OTA/플랫폼', '트래블테크', '숙박업계']

    for news in news_list:
        if news.get('category') in trend_categories:
            return news

    # 없으면 첫 번째 뉴스 반환
    return news_list[0] if news_list else None


def get_keyword_news_candidates(news_list, exclude_indices=None, count=10):
    """
    키워드 뉴스 후보 10개 선정
    - 메인 콘텐츠와 트렌드 기사 제외
    - 카테고리 다양성 확보
    """
    if exclude_indices is None:
        exclude_indices = []

    candidates = []
    seen_categories = {}

    for i, news in enumerate(news_list):
        if i in exclude_indices:
            continue

        category = news.get('category', '기타')

        # 카테고리 다양성: 같은 카테고리는 최대 2개
        if seen_categories.get(category, 0) >= 2:
            continue

        candidates.append({
            'index': i,
            'title': news.get('title', ''),
            'source': news.get('source', ''),
            'category': category,
            'link': news.get('link', ''),
            'summary': news.get('short_summary', '') or news.get('summary', '')
        })

        seen_categories[category] = seen_categories.get(category, 0) + 1

        if len(candidates) >= count:
            break

    return candidates


def generate_keyword_news_section(selected_news):
    """
    키워드 뉴스 섹션 생성 (5개)
    """
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
    sections = []

    for i, news in enumerate(selected_news[:5]):
        title = news.get('title', '')
        link = news.get('link', '')
        summary = news.get('summary', '')[:100]
        if len(news.get('summary', '')) > 100:
            summary += '...'

        section = f"""{emojis[i]} {title} [👉[전체 뉴스 보기]]({link})
한줄요약: {summary}
"""
        sections.append(section)

    return '\n'.join(sections)


def generate_newsletter_markdown(
    main_title,
    main_content,
    trend_article,
    keyword_news,
    vol_number=None
):
    """
    완성된 뉴스레터를 Markdown 형식으로 생성
    """
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst)
    date_str = today.strftime("%Y년 %m월 %d일")

    if vol_number is None:
        vol_number = 162  # 기본값, 실제로는 마지막 발행 호수 + 1

    # 인트로 요약 생성
    news_list = load_scraped_news()
    intro_items = generate_intro_summary(main_title, main_content, news_list)

    # 트렌드 기사 섹션
    trend_section = ""
    if trend_article:
        trend_title = trend_article.get('title', '')
        trend_link = trend_article.get('link', '')
        trend_summary = trend_article.get('summary', '')[:150]
        trend_section = f"""## 💡 호스피탈리티 트렌드

**{trend_title}** [👉[전체 뉴스 보기]]({trend_link})

{trend_summary}

---
"""

    # 키워드 뉴스 섹션
    keyword_section = generate_keyword_news_section(keyword_news)

    newsletter = f"""# WeeklyON vol.{vol_number}

**{date_str}**

---

## 오늘의 위클리온

{chr(10).join(f'- {item}' for item in intro_items)}

---

## 🏠 산업 이야기

### {main_title}

{main_content}

---

{trend_section}

## ⌨️ 키워드 뉴스

{keyword_section}

---

## 뉴스레터 구독하기

숙박업 사장님들을 위한 주간 뉴스레터, WeeklyON을 구독하세요!

[구독하기](https://www.onda.me/newsletter)

---

*© ONDA. 무단 전재 및 재배포를 금지합니다.*
"""

    return newsletter


def generate_newsletter_html(
    main_title,
    main_content,
    trend_article,
    keyword_news,
    vol_number=None
):
    """
    완성된 뉴스레터를 HTML 형식으로 생성 (웹 발행용)
    """
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst)
    date_str = today.strftime("%Y년 %m월 %d일")

    if vol_number is None:
        vol_number = 162

    # 인트로 요약 생성
    news_list = load_scraped_news()
    intro_items = generate_intro_summary(main_title, main_content, news_list)

    # 메인 콘텐츠를 HTML 단락으로 변환
    main_paragraphs = main_content.split('\n\n')
    main_html = '\n'.join(f'<p>{p.strip()}</p>' for p in main_paragraphs if p.strip())

    # 소제목 처리 (숫자. 으로 시작하는 줄)
    main_html = re.sub(
        r'<p>(\d+\.\s+[^<]+)</p>',
        r'<h4>\1</h4>',
        main_html
    )

    # 트렌드 기사 HTML
    trend_html = ""
    if trend_article:
        trend_html = f"""
        <div class="section">
            <h3>💡 호스피탈리티 트렌드</h3>
            <div class="news-item">
                <h4>{trend_article.get('title', '')}</h4>
                <p>{trend_article.get('summary', '')[:150]}</p>
                <a href="{trend_article.get('link', '')}" class="read-more">👉 전체 뉴스 보기</a>
            </div>
        </div>
        """

    # 키워드 뉴스 HTML
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
    keyword_items = []
    for i, news in enumerate(keyword_news[:5]):
        keyword_items.append(f"""
            <div class="keyword-news">
                <span class="number">{emojis[i]}</span>
                <div class="content">
                    <h5>{news.get('title', '')}</h5>
                    <p class="summary">한줄요약: {news.get('summary', '')[:100]}</p>
                    <a href="{news.get('link', '')}">👉 전체 뉴스 보기</a>
                </div>
            </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WeeklyON vol.{vol_number} - {main_title}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Spoqa Han Sans Neo', 'Malgun Gothic', sans-serif;
            line-height: 1.8;
            color: #333;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 680px;
            margin: 0 auto;
            background: white;
            padding: 40px;
        }}
        .header {{
            text-align: center;
            padding-bottom: 30px;
            border-bottom: 2px solid #004FC5;
        }}
        .header h1 {{
            color: #004FC5;
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .header .date {{
            color: #666;
            font-size: 14px;
        }}
        .intro {{
            background: #f8f9fa;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
        }}
        .intro h3 {{
            font-size: 16px;
            margin-bottom: 15px;
            color: #004FC5;
        }}
        .intro ul {{
            list-style: none;
        }}
        .intro li {{
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        .intro li:last-child {{
            border-bottom: none;
        }}
        .section {{
            margin: 40px 0;
        }}
        .section h3 {{
            font-size: 20px;
            color: #004FC5;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }}
        .main-content {{
            font-size: 17px;
            line-height: 1.9;
        }}
        .main-content h4 {{
            font-size: 18px;
            margin: 25px 0 15px;
            color: #222;
        }}
        .main-content p {{
            margin-bottom: 18px;
        }}
        .keyword-news {{
            display: flex;
            gap: 15px;
            padding: 15px 0;
            border-bottom: 1px solid #eee;
        }}
        .keyword-news .number {{
            font-size: 20px;
        }}
        .keyword-news h5 {{
            font-size: 15px;
            margin-bottom: 5px;
        }}
        .keyword-news .summary {{
            font-size: 14px;
            color: #666;
        }}
        .keyword-news a {{
            font-size: 13px;
            color: #004FC5;
        }}
        .read-more {{
            display: inline-block;
            color: #004FC5;
            text-decoration: none;
            font-weight: 600;
        }}
        .cta {{
            text-align: center;
            padding: 40px;
            background: #004FC5;
            color: white;
            margin-top: 40px;
            border-radius: 8px;
        }}
        .cta h3 {{
            margin-bottom: 15px;
        }}
        .cta a {{
            display: inline-block;
            background: white;
            color: #004FC5;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            padding: 30px;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>WeeklyON vol.{vol_number}</h1>
            <p class="date">{date_str}</p>
        </div>

        <div class="intro">
            <h3>오늘의 위클리온</h3>
            <ul>
                {''.join(f'<li>{item}</li>' for item in intro_items)}
            </ul>
        </div>

        <div class="section">
            <h3>🏠 산업 이야기</h3>
            <h2 style="font-size: 24px; margin-bottom: 20px;">{main_title}</h2>
            <div class="main-content">
                {main_html}
            </div>
        </div>

        {trend_html}

        <div class="section">
            <h3>⌨️ 키워드 뉴스</h3>
            {''.join(keyword_items)}
        </div>

        <div class="cta">
            <h3>뉴스레터 구독하기</h3>
            <p>숙박업 사장님들을 위한 주간 뉴스레터!</p>
            <a href="https://www.onda.me/newsletter">구독하기</a>
        </div>

        <div class="footer">
            © ONDA. 무단 전재 및 재배포를 금지합니다.
        </div>
    </div>
</body>
</html>"""

    return html


def interactive_generate():
    """
    대화형 뉴스레터 생성
    """
    print("=" * 60)
    print("WeeklyON 뉴스레터 생성기")
    print("=" * 60)

    # 1. 스크랩된 뉴스 로드
    news_list = load_scraped_news()
    if not news_list:
        print("❌ 스크랩된 뉴스가 없습니다. 먼저 onda_news_scraper.py를 실행하세요.")
        return

    print(f"\n✅ {len(news_list)}개의 스크랩된 뉴스를 로드했습니다.\n")

    # 2. 메인 콘텐츠 입력 (파일에서 읽거나 직접 입력)
    print("메인 콘텐츠를 입력하세요.")
    print("(main_content.txt 파일에 저장해두면 자동으로 읽어옵니다)")
    print("-" * 40)

    main_title = ""
    main_content = ""

    if os.path.exists('main_content.txt'):
        with open('main_content.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
            main_title = lines[0]
            main_content = '\n'.join(lines[1:]).strip()
        print(f"📄 main_content.txt에서 로드됨")
        print(f"   제목: {main_title[:50]}...")
    else:
        main_title = input("메인 콘텐츠 제목: ")
        print("메인 콘텐츠 본문 (입력 완료 후 빈 줄에서 Enter 두 번):")
        lines = []
        while True:
            line = input()
            if line == "":
                if lines and lines[-1] == "":
                    break
            lines.append(line)
        main_content = '\n'.join(lines)

    # 3. 트렌드 기사 자동 선택
    print("\n" + "=" * 40)
    print("💡 호스피탈리티 트렌드 기사 (자동 선택)")
    print("-" * 40)

    trend_article = select_trend_article(news_list)
    if trend_article:
        print(f"선택됨: {trend_article.get('title', '')[:50]}...")
        print(f"카테고리: {trend_article.get('category', '')}")

    # 4. 키워드 뉴스 후보 제시 및 선택
    print("\n" + "=" * 40)
    print("⌨️ 키워드 뉴스 후보 (10개 중 5개 선택)")
    print("-" * 40)

    # 트렌드 기사 인덱스 찾기
    trend_idx = None
    for i, n in enumerate(news_list):
        if n.get('link') == trend_article.get('link'):
            trend_idx = i
            break

    candidates = get_keyword_news_candidates(
        news_list,
        exclude_indices=[0, trend_idx] if trend_idx else [0],
        count=10
    )

    for i, c in enumerate(candidates):
        print(f"[{i+1}] {c['title'][:45]}...")
        print(f"    출처: {c['source']} | 카테고리: {c['category']}")

    print("\n선택할 번호를 쉼표로 구분해서 입력하세요 (예: 1,3,5,7,9)")
    print("또는 Enter를 눌러 상위 5개 자동 선택")

    selection = input("선택: ").strip()

    if selection:
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected_news = [candidates[i] for i in indices if 0 <= i < len(candidates)]
        except ValueError:
            print("잘못된 입력. 상위 5개를 자동 선택합니다.")
            selected_news = candidates[:5]
    else:
        selected_news = candidates[:5]

    print(f"\n✅ {len(selected_news)}개 키워드 뉴스 선택됨")

    # 5. 뉴스레터 생성
    print("\n" + "=" * 40)
    print("뉴스레터 생성 중...")
    print("-" * 40)

    # Markdown 생성
    markdown = generate_newsletter_markdown(
        main_title, main_content,
        trend_article, selected_news
    )

    # HTML 생성
    html = generate_newsletter_html(
        main_title, main_content,
        trend_article, selected_news
    )

    # 파일 저장
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y%m%d")

    md_path = f"newsletter_{today}.md"
    html_path = f"newsletter_{today}.html"

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✅ 뉴스레터 생성 완료!")
    print(f"   - Markdown: {md_path}")
    print(f"   - HTML: {html_path}")
    print(f"\n💡 Google Docs에 복사하려면 {md_path}를 열어 내용을 복사하세요.")


if __name__ == "__main__":
    interactive_generate()
