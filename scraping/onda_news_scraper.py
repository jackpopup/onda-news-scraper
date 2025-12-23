"""
ONDA 뉴스 스크래퍼
B2B Hospitality Tech 기업 ONDA를 위한 맞춤 뉴스 수집기

주요 수집 카테고리:
1. 국내외 OTA 관련 주요 이슈
2. 정부/지자체 숙박업 관련 발표
3. 숙박업 및 관련 스타트업 뉴스
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import argparse
import re
from urllib.parse import quote
from email_sender import create_onda_html_email, send_email_gmail

# ============================================
# 키워드 설정
# ============================================

# OTA 플랫폼 관련
OTA_KEYWORDS = [
    '아고다', '에어비앤비', '부킹닷컴', '트립닷컴', '익스피디아',
    '야놀자', '여기어때', '마이리얼트립', '호텔스닷컴', '호텔스컴바인',
    '트립어드바이저', 'OTA', '온라인여행사'
]

# 숙박업 관련
ACCOMMODATION_KEYWORDS = [
    '호텔', '리조트', '펜션', '숙박', '객실', '게스트하우스',
    '숙소', '모텔', '민박', '풀빌라', '호스텔'
]

# 정부/정책 관련
POLICY_KEYWORDS = [
    '관광공사', '관광재단', '문화체육관광부', '문체부', '관광진흥',
    '숙박업법', '공유숙박', '생활숙박', '관광정책', '규제'
]

# 트래블테크/스타트업 관련
TRAVELTECH_KEYWORDS = [
    '온다', 'ONDA', '트래블테크', '호스피탈리티', '여행테크',
    '트립비토즈', '야놀자클라우드', '호텔솔루션', 'PMS', '채널매니저'
]

# AI/DX 관련
AI_KEYWORDS = [
    'AI', '인공지능', 'DX', '디지털전환', '자동화', '챗봇'
]

# 고관심 키워드 (점수 높음)
HIGH_PRIORITY_KEYWORDS = OTA_KEYWORDS + ['온다', 'ONDA', '투자유치', '시리즈', '숙박플랫폼']

# 중관심 키워드
MEDIUM_PRIORITY_KEYWORDS = ACCOMMODATION_KEYWORDS + POLICY_KEYWORDS + TRAVELTECH_KEYWORDS

# 저관심 키워드
LOW_PRIORITY_KEYWORDS = AI_KEYWORDS + ['관광', '여행', '인바운드', '아웃바운드']

# ============================================
# 산업 임팩트 키워드 (Option C: 에디터 관점 선정 기준)
# ============================================

# 투자/M&A 관련 (산업 판도 변화 신호)
INVESTMENT_KEYWORDS = [
    '투자유치', '시리즈', '인수', '합병', 'M&A', '펀딩',
    '투자', '억원', '달러', '밸류에이션', 'IPO', '상장'
]

# 규제/정책 변화 (비즈니스 영향)
REGULATION_KEYWORDS = [
    '규제', '법안', '허용', '금지', '단속', '합법화',
    '시행령', '개정', '신고제', '등록제', '과태료'
]

# 신기술/서비스 런칭
NEWTECH_KEYWORDS = [
    '출시', '런칭', '오픈', '베타', '신규 서비스',
    '업데이트', '개편', 'AI 도입', '자동화'
]

# 시장 데이터/실적 (숫자가 있는 뉴스)
MARKET_DATA_KEYWORDS = [
    '매출', '영업이익', '성장률', '점유율', '거래액',
    '이용자', '예약', '객실점유율', 'ADR', 'RevPAR'
]


def get_naver_news_search(query, display=30):
    """
    네이버 뉴스 검색 (웹 스크래핑)
    """
    encoded_query = quote(query)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded_query}&sort=1"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        articles = []

        # 여러 가지 선택자 시도
        news_items = soup.select('div.news_area')
        if not news_items:
            news_items = soup.select('li.bx')
        if not news_items:
            news_items = soup.select('div.news_wrap')

        for item in news_items[:display]:
            try:
                # 제목 - 여러 선택자 시도
                title_elem = item.select_one('a.news_tit')
                if not title_elem:
                    title_elem = item.select_one('a.api_txt_lines')
                if not title_elem:
                    title_elem = item.select_one('a.news_tit_link')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')

                # 요약
                summary_elem = item.select_one('div.news_dsc')
                if not summary_elem:
                    summary_elem = item.select_one('div.api_txt_lines.dsc_txt_wrap')
                if not summary_elem:
                    summary_elem = item.select_one('a.api_txt_lines.dsc_txt_wrap')
                summary = summary_elem.get_text(strip=True) if summary_elem else ""

                # 언론사
                press_elem = item.select_one('a.info.press')
                if not press_elem:
                    press_elem = item.select_one('a.info')
                if not press_elem:
                    press_elem = item.select_one('span.info')
                press = press_elem.get_text(strip=True) if press_elem else "알 수 없음"
                press = press.replace('언론사 선정', '').strip()

                if title and link:
                    articles.append({
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'source': press,
                        'search_query': query
                    })
            except Exception as e:
                continue

        return articles
    except Exception as e:
        print(f"네이버 검색 오류 ({query}): {e}")
        return []


def get_naver_section_news(section_id="105"):
    """
    네이버 뉴스 섹션에서 기사 수집
    105: IT/과학, 101: 경제
    """
    url = f"https://news.naver.com/section/{section_id}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        articles = []

        # sa_text 클래스로 기사 찾기
        news_items = soup.select('div.sa_text')

        for item in news_items[:30]:
            try:
                # 제목
                title_elem = item.select_one('strong.sa_text_strong')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # 링크
                link_elem = item.select_one('a.sa_text_title')
                if not link_elem:
                    link_elem = item.select_one('a')
                link = link_elem.get('href', '') if link_elem else ""

                # 요약
                summary_elem = item.select_one('div.sa_text_lede')
                summary = summary_elem.get_text(strip=True) if summary_elem else ""

                # 언론사
                press_elem = item.select_one('div.sa_text_press')
                press = press_elem.get_text(strip=True) if press_elem else "네이버뉴스"

                if title and link:
                    articles.append({
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'source': press,
                        'search_query': 'section'
                    })
            except Exception:
                continue

        return articles
    except Exception as e:
        print(f"네이버 섹션 뉴스 오류: {e}")
        return []


def get_google_news_search(query, num_results=15):
    """
    구글 뉴스 검색 (웹 스크래핑)
    """
    encoded_query = quote(query)
    # 최근 1주일 뉴스 (tbs=qdr:w)
    url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&hl=ko&tbs=qdr:w"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ko-KR,ko;q=0.9'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        articles = []

        # 구글 뉴스 결과 파싱
        for item in soup.select('div.SoaBEf')[:num_results]:
            try:
                # 제목
                title_elem = item.select_one('div.n0jPhd')
                if not title_elem:
                    title_elem = item.select_one('div.MBeuO')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                # 링크
                link_elem = item.select_one('a')
                if not link_elem:
                    continue
                link = link_elem.get('href', '')

                # 요약
                summary_elem = item.select_one('div.GI74Re')
                summary = summary_elem.get_text(strip=True) if summary_elem else ""

                # 언론사 (여러 선택자 시도)
                source_elem = item.select_one('div.NUnG9d')
                if not source_elem:
                    source_elem = item.select_one('span.NUnG9d')
                if not source_elem:
                    source_elem = item.select_one('div.CEMjEf span')
                source = source_elem.get_text(strip=True) if source_elem else "알 수 없음"

                # 시간 정보 추출 (예: "3시간 전", "1일 전")
                time_elem = item.select_one('div.OSrXXb span')
                if not time_elem:
                    time_elem = item.select_one('span.WG9SHc')
                if not time_elem:
                    time_elem = item.select_one('div.ZE0LJd span')
                time_text = time_elem.get_text(strip=True) if time_elem else ""

                # 24시간 이내 여부 판단
                is_recent = False
                if time_text:
                    if '시간' in time_text or '분' in time_text:
                        is_recent = True
                    elif '1일' in time_text:
                        is_recent = True

                if title and link:
                    articles.append({
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'source': source,
                        'search_query': query,
                        'time_text': time_text,
                        'is_recent': is_recent
                    })
            except Exception:
                continue

        return articles
    except Exception as e:
        print(f"구글 검색 오류 ({query}): {e}")
        return []


def is_relevant_article(article):
    """
    ONDA 관련 기사인지 필터링
    핵심 키워드가 하나라도 있어야 관련 기사로 인정
    """
    text = (article['title'] + ' ' + article.get('summary', '')).lower()

    # 필수 키워드 - 이 중 하나라도 있어야 함
    must_have_keywords = (
        OTA_KEYWORDS +
        ACCOMMODATION_KEYWORDS +
        POLICY_KEYWORDS +
        TRAVELTECH_KEYWORDS +
        ['관광', '여행', '투어', '레저']
    )

    for keyword in must_have_keywords:
        if keyword.lower() in text:
            return True

    return False


def collect_all_news(silent=False):
    """
    구글 뉴스에서 ONDA 관련 뉴스 수집
    """
    all_articles = []

    # 키워드 검색 쿼리 - ONDA 비즈니스 관련 핵심 키워드
    search_queries = [
        # OTA 플랫폼 (핵심)
        "야놀자",
        "여기어때",
        "에어비앤비 한국",
        "아고다 한국",
        "부킹닷컴 한국",
        # 숙박업
        "호텔 업계 뉴스",
        "숙박업",
        "리조트 뉴스",
        # 정책/규제
        "숙박업 규제",
        "공유숙박",
        "관광공사",
        # 트래블테크/스타트업
        "트래블테크",
        "호스피탈리티 테크",
        "숙박 플랫폼",
        # ONDA 직접
        "온다 ONDA 숙박"
    ]

    total_queries = len(search_queries)

    for idx, query in enumerate(search_queries, 1):
        if not silent:
            print(f"   [{idx}/{total_queries}] '{query}' 검색 중...")

        # 구글 뉴스 검색
        google_articles = get_google_news_search(query, num_results=10)

        # 관련 기사만 필터링
        for article in google_articles:
            if is_relevant_article(article):
                all_articles.append(article)

    if not silent:
        print(f"   -> 관련 기사 {len(all_articles)}개 필터링 완료")

    return all_articles


def calculate_relevance_score(article):
    """
    ONDA 비즈니스 관련도에 따라 점수 계산
    숙박/OTA/여행 맥락에서만 점수 부여
    """
    text = (article['title'] + ' ' + article['summary']).lower()

    score = 0
    matched_keywords = []

    # ONDA 직접 언급 (최고 점수 100점)
    if '온다' in text or 'onda' in text:
        score += 100
        matched_keywords.append('ONDA')

    # OTA 플랫폼 언급 (각 25점) - 핵심 경쟁사/파트너
    for keyword in OTA_KEYWORDS:
        if keyword.lower() in text:
            score += 25
            matched_keywords.append(keyword)

    # 트래블테크/호스피탈리티 (각 20점)
    for keyword in TRAVELTECH_KEYWORDS:
        if keyword.lower() in text:
            score += 20
            matched_keywords.append(keyword)

    # 숙박업 키워드 (각 15점)
    for keyword in ACCOMMODATION_KEYWORDS:
        if keyword.lower() in text:
            score += 15
            matched_keywords.append(keyword)

    # 정책/규제 키워드 (각 12점)
    for keyword in POLICY_KEYWORDS:
        if keyword.lower() in text:
            score += 12
            matched_keywords.append(keyword)

    # 투자/펀딩 - 숙박/여행 관련 기사에서만 보너스 (15점)
    has_travel_context = any(kw.lower() in text for kw in OTA_KEYWORDS + ACCOMMODATION_KEYWORDS + TRAVELTECH_KEYWORDS)
    if has_travel_context:
        investment_keywords = ['투자유치', '펀딩', '시리즈a', '시리즈b', '시리즈c']
        for kw in investment_keywords:
            if kw in text:
                score += 15
                matched_keywords.append(f'투자:{kw}')
                break

    # 정책/규제 보너스 - 숙박 관련일 때만 (10점)
    if has_travel_context:
        policy_bonus = ['규제 완화', '규제 강화', '법안', '허용', '금지', '단속']
        for kw in policy_bonus:
            if kw in text:
                score += 10
                matched_keywords.append(f'정책:{kw}')
                break

    article['matched_keywords'] = list(set(matched_keywords))
    return score


def calculate_industry_impact_score(article):
    """
    [Option C] 산업 임팩트 점수 계산
    에디터 관점에서 "이 뉴스가 숙박/여행 업계에 얼마나 중요한가"를 판단

    기존 키워드 매칭 대신 다음 기준으로 점수 부여:
    1. 투자/M&A: 산업 판도 변화 신호 (최고 가중치)
    2. 규제/정책 변화: 비즈니스 직접 영향
    3. 신기술/서비스 런칭: 경쟁 동향
    4. 시장 데이터: 숫자가 있는 뉴스 (신뢰도/중요도 높음)
    """
    text = (article['title'] + ' ' + article.get('summary', '')).lower()
    title = article['title'].lower()

    impact_score = 0
    impact_factors = []

    # 1. 투자/M&A (40점) - 가장 높은 가중치
    investment_match = 0
    for kw in INVESTMENT_KEYWORDS:
        if kw.lower() in text:
            investment_match += 1
    if investment_match > 0:
        impact_score += min(40, investment_match * 15)
        impact_factors.append('투자/M&A')

    # 2. 규제/정책 변화 (35점)
    regulation_match = 0
    for kw in REGULATION_KEYWORDS:
        if kw.lower() in text:
            regulation_match += 1
    if regulation_match > 0:
        impact_score += min(35, regulation_match * 12)
        impact_factors.append('규제/정책')

    # 3. 신기술/서비스 런칭 (25점)
    newtech_match = 0
    for kw in NEWTECH_KEYWORDS:
        if kw.lower() in text:
            newtech_match += 1
    if newtech_match > 0:
        impact_score += min(25, newtech_match * 10)
        impact_factors.append('신규서비스')

    # 4. 시장 데이터/실적 (30점) - 숫자가 있으면 보너스
    market_match = 0
    for kw in MARKET_DATA_KEYWORDS:
        if kw.lower() in text:
            market_match += 1
    if market_match > 0:
        impact_score += min(30, market_match * 10)
        impact_factors.append('시장데이터')

    # 5. 숫자 포함 보너스 (구체적 데이터가 있는 기사)
    # 억원, %, 만명 등 숫자+단위가 있으면 +15점
    number_patterns = [
        r'\d+억', r'\d+만', r'\d+%', r'\d+조',
        r'\$\d+', r'USD\s*\d+', r'\d+달러'
    ]
    for pattern in number_patterns:
        if re.search(pattern, text):
            impact_score += 15
            impact_factors.append('구체적수치')
            break

    # 6. 제목에 핵심 키워드가 있으면 보너스 (+10점)
    # 제목에 있는 키워드가 더 중요
    title_keywords = INVESTMENT_KEYWORDS + REGULATION_KEYWORDS[:5] + ['출시', '런칭', '오픈']
    for kw in title_keywords:
        if kw.lower() in title:
            impact_score += 10
            break

    # 7. 국내 주요 OTA 우선순위 (야놀자, nol, 마리트, 여기어때)
    # 국내 OTA는 더 높은 가중치 (+35점), 해외 OTA는 기존 (+20점)
    domestic_ota = ['야놀자', 'nol', '놀', '마이리얼트립', '마리트', '여기어때']
    foreign_ota = ['에어비앤비', '아고다', '부킹닷컴', '트립닷컴', '익스피디아']
    onda = ['온다', 'onda']

    ota_found = False
    for company in onda:
        if company in text:
            impact_score += 50  # ONDA 직접 언급은 최고 보너스
            impact_factors.append(f'자사:{company}')
            ota_found = True
            break

    if not ota_found:
        for company in domestic_ota:
            if company in text:
                impact_score += 35  # 국내 주요 OTA 높은 보너스
                impact_factors.append(f'국내OTA:{company}')
                ota_found = True
                break

    if not ota_found:
        for company in foreign_ota:
            if company in text:
                impact_score += 20  # 해외 OTA 기본 보너스
                impact_factors.append(f'해외OTA:{company}')
                break

    # 8. 24시간 이내 기사 보너스 (+25점)
    if article.get('is_recent', False):
        impact_score += 25
        impact_factors.append('24시간이내')

    # 9. 프로모션/이벤트/할인 기사 페널티 (-40점)
    # 일반적인 마케팅 기사는 뉴스 가치가 낮음
    promo_keywords = [
        '할인', '프로모션', '이벤트', '쿠폰', '특가', '세일',
        '얼리버드', '최대 할인', '% 할인', '무료', '경품',
        '추첨', '응모', '선착순', '한정', '페스타', '위크'
    ]
    promo_count = 0
    for kw in promo_keywords:
        if kw in text:
            promo_count += 1

    if promo_count >= 2:
        # 프로모션 키워드가 2개 이상이면 큰 페널티
        impact_score -= 40
        impact_factors.append('프로모션기사')
    elif promo_count == 1:
        # 1개면 작은 페널티
        impact_score -= 20
        impact_factors.append('프로모션기사')

    # 10. 중요 발표 보너스 (기자간담회, 신제품 출시 등)
    major_event_keywords = [
        '기자간담회', '기자회견', '컨퍼런스', '신제품', '신규 서비스',
        '플랫폼 개편', '리브랜딩', '합작', '제휴', 'MOU', '협약'
    ]
    for kw in major_event_keywords:
        if kw in text:
            impact_score += 15
            impact_factors.append('주요발표')
            break

    # 11. 비판/이슈 기사 보너스 (+40점)
    # 기자 취재 기사, 플랫폼 횡포/갑질, 논란 등은 뉴스 가치 높음
    critical_keywords = [
        '갑질', '횡포', '논란', '피해', '불만', '분쟁', '고발',
        '제재', '과징금', '벌금', '소송', '고소', '수사', '조사',
        '의혹', '비판', '문제점', '부작용', '위법', '불법',
        '독점', '불공정', '폭리', '착취', '임금체불', '해고'
    ]
    critical_count = 0
    for kw in critical_keywords:
        if kw in text:
            critical_count += 1

    if critical_count >= 2:
        # 비판 키워드가 2개 이상이면 큰 보너스
        impact_score += 50
        impact_factors.append('비판/이슈기사')
    elif critical_count == 1:
        # 1개면 작은 보너스
        impact_score += 30
        impact_factors.append('비판/이슈기사')

    article['impact_score'] = impact_score
    article['impact_factors'] = impact_factors

    return impact_score


def calculate_similarity(title1, title2):
    """
    두 제목의 유사도 계산 (강화된 버전)
    """
    # 특수문자 제거하고 단어로 분리
    def clean_and_split(text):
        text = re.sub(r'[^\w\s]', '', text.lower())
        return set(text.split())

    words1 = clean_and_split(title1)
    words2 = clean_and_split(title2)

    if not words1 or not words2:
        return 0

    common = words1.intersection(words2)
    total = words1.union(words2)

    jaccard = len(common) / len(total) if total else 0

    # 핵심 키워드 중복 체크 (회사명, 금액 등)
    key_patterns = [
        r'야놀자', r'여기어때', r'에어비앤비', r'아고다', r'부킹', r'트립닷컴',
        r'마이리얼트립', r'nol', r'\d+억', r'\d+조', r'\d+%'
    ]

    title1_lower = title1.lower()
    title2_lower = title2.lower()

    shared_keys = 0
    for pattern in key_patterns:
        if re.search(pattern, title1_lower) and re.search(pattern, title2_lower):
            shared_keys += 1

    # 핵심 키워드가 2개 이상 공유되면 유사도 높임
    if shared_keys >= 2:
        jaccard = max(jaccard, 0.6)

    return jaccard


def extract_article_topic(article):
    """
    기사의 핵심 토픽 추출 (중복 판단용)
    """
    text = (article['title'] + ' ' + article.get('summary', '')).lower()

    # 회사명 추출
    companies = []
    company_patterns = ['야놀자', '여기어때', '에어비앤비', '아고다', '부킹닷컴',
                       '트립닷컴', '마이리얼트립', 'nol', '놀', '온다', 'onda']
    for company in company_patterns:
        if company in text:
            companies.append(company)

    # 금액 추출
    amounts = re.findall(r'\d+억|\d+조|\d+만', text)

    # 이벤트 타입 추출
    event_type = None
    if any(kw in text for kw in ['투자', '펀딩', '시리즈']):
        event_type = 'investment'
    elif any(kw in text for kw in ['인수', '합병', 'm&a']):
        event_type = 'ma'
    elif any(kw in text for kw in ['출시', '런칭', '오픈']):
        event_type = 'launch'
    elif any(kw in text for kw in ['실적', '매출', '영업이익']):
        event_type = 'earnings'

    return {
        'companies': companies,
        'amounts': amounts,
        'event_type': event_type
    }


def is_same_story(article1, article2):
    """
    두 기사가 같은 사건/스토리인지 판단 (강화된 버전)
    """
    topic1 = extract_article_topic(article1)
    topic2 = extract_article_topic(article2)

    # 같은 회사 + 같은 이벤트 타입 = 같은 스토리
    shared_companies = set(topic1['companies']) & set(topic2['companies'])
    if shared_companies and topic1['event_type'] == topic2['event_type'] and topic1['event_type'] is not None:
        return True

    # 같은 회사 + 같은 금액 = 같은 스토리
    shared_amounts = set(topic1['amounts']) & set(topic2['amounts'])
    if shared_companies and shared_amounts:
        return True

    # 제목의 첫 번째 회사명이 같고 비슷한 주제면 같은 스토리
    title1 = article1['title'].lower()
    title2 = article2['title'].lower()

    # 제목에서 회사명 추출
    companies_in_title = ['야놀자', '여기어때', '에어비앤비', '아고다', '부킹닷컴',
                          '트립닷컴', '마이리얼트립', 'nol', '놀유니버스', '온다']
    title1_company = None
    title2_company = None
    for company in companies_in_title:
        if company in title1 and title1_company is None:
            title1_company = company
        if company in title2 and title2_company is None:
            title2_company = company

    # 같은 회사가 제목에 있으면 중복 가능성 높음
    if title1_company and title1_company == title2_company:
        # 제목의 공통 단어가 3개 이상이면 중복
        words1 = set(re.sub(r'[^\w\s]', '', title1).split())
        words2 = set(re.sub(r'[^\w\s]', '', title2).split())
        common_words = words1 & words2
        # 불용어 제외
        stopwords = {'의', '를', '을', '이', '가', '은', '는', '에', '에서', '와', '과', '로', '으로', '도', '만', '더', '등'}
        meaningful_common = common_words - stopwords
        if len(meaningful_common) >= 3:
            return True

    return False


def remove_duplicates(articles, threshold=0.35):
    """
    중복 기사 제거 (강화된 버전)
    - 유사도 임계값 낮춤 (0.5 -> 0.35)
    - 같은 스토리 판단 로직 추가
    """
    unique = []

    for article in articles:
        is_duplicate = False

        for existing in unique:
            # 1. 제목 유사도 체크
            similarity = calculate_similarity(article['title'], existing['title'])

            # 2. 같은 스토리인지 체크 (회사+이벤트 또는 회사+금액)
            same_story = is_same_story(article, existing)

            if similarity >= threshold or same_story:
                is_duplicate = True
                # 점수가 더 높은 것 유지
                if article.get('score', 0) > existing.get('score', 0):
                    unique.remove(existing)
                    unique.append(article)
                break

        if not is_duplicate:
            unique.append(article)

    return unique


def apply_freshness_penalty(articles):
    """
    많이 보도된 주제는 점수 감소 (신선도 패널티)
    같은 키워드 조합이 많이 나온 기사는 점수 감소
    """
    from collections import Counter

    # 주요 키워드별 등장 횟수 카운트
    keyword_counts = Counter()
    for article in articles:
        keywords = article.get('matched_keywords', [])
        # OTA 이름 등 핵심 키워드만 카운트
        core_keywords = [kw for kw in keywords if kw in OTA_KEYWORDS or kw == 'ONDA']
        keyword_counts.update(core_keywords)

    # 기사별 패널티 적용
    for article in articles:
        keywords = article.get('matched_keywords', [])
        core_keywords = [kw for kw in keywords if kw in OTA_KEYWORDS or kw == 'ONDA']

        # 해당 키워드가 많이 등장할수록 패널티
        max_count = max([keyword_counts.get(kw, 0) for kw in core_keywords]) if core_keywords else 0

        if max_count > 5:
            # 5회 이상 등장한 키워드 기사는 점수 30% 감소
            penalty = 0.7
        elif max_count > 3:
            # 3~5회 등장은 15% 감소
            penalty = 0.85
        else:
            penalty = 1.0

        article['score'] = int(article['score'] * penalty)
        if penalty < 1.0:
            article['freshness_penalty'] = True

    return articles


def categorize_article(article):
    """
    기사 카테고리 분류
    """
    text = (article['title'] + ' ' + article['summary']).lower()

    # OTA 관련
    for kw in OTA_KEYWORDS:
        if kw.lower() in text:
            return "OTA/플랫폼"

    # 정책 관련
    for kw in POLICY_KEYWORDS:
        if kw.lower() in text:
            return "정책/규제"

    # 트래블테크
    for kw in TRAVELTECH_KEYWORDS:
        if kw.lower() in text:
            return "트래블테크"

    # 숙박업
    for kw in ACCOMMODATION_KEYWORDS:
        if kw.lower() in text:
            return "숙박업계"

    return "기타"


def ai_editor_select_top3(articles, silent=False):
    """
    [Option A] AI 에디터 레이어
    GPT/Claude가 온다 관점에서 가장 중요한 TOP 3 기사를 선정하고
    60-100자로 핵심 요약을 생성

    실제 온다 뉴스레터처럼:
    - 산업에 미치는 영향 기준으로 선정
    - 구체적 숫자 포함한 임팩트 있는 요약
    """
    import os
    import json

    openai_key = os.environ.get('OPENAI_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    # 상위 10개 기사 정보를 AI에게 전달
    articles_info = []
    for idx, article in enumerate(articles[:10], 1):
        articles_info.append({
            "번호": idx,
            "제목": article['title'],
            "요약": article.get('summary', '')[:200],
            "출처": article['source'],
            "키워드점수": article.get('score', 0),
            "임팩트점수": article.get('impact_score', 0),
            "임팩트요인": article.get('impact_factors', [])
        })

    prompt = f"""당신은 ONDA(온다)의 뉴스 에디터입니다. ONDA는 B2B 숙박 플랫폼 연동 솔루션 기업입니다.

아래 10개 기사 중에서 숙박/여행 업계에 가장 중요한 TOP 3 기사를 선정해주세요.

선정 기준 (중요도 순):
1. 투자/M&A 소식 (산업 판도 변화)
2. 규제/정책 변화 (비즈니스 직접 영향)
3. 주요 OTA/숙박 플랫폼의 신규 서비스
4. 구체적 시장 데이터가 있는 기사

각 선정 기사에 대해 60-100자 요약을 작성해주세요.
요약 작성 규칙:
- 반드시 구체적인 숫자를 포함 (금액, 비율, 증감률 등)
- "~했다", "~이다" 형식의 완결된 문장
- 핵심 팩트 1개만 전달

기사 목록:
{json.dumps(articles_info, ensure_ascii=False, indent=2)}

응답 형식 (JSON):
{{
  "top3": [
    {{"번호": 1, "요약": "60-100자 요약"}},
    {{"번호": 2, "요약": "60-100자 요약"}},
    {{"번호": 3, "요약": "60-100자 요약"}}
  ]
}}
"""

    result = None

    if openai_key:
        try:
            import openai
            openai.api_key = openai_key

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 B2B 호스피탈리티 업계 전문 뉴스 에디터입니다. JSON 형식으로만 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
        except Exception as e:
            if not silent:
                print(f"   OpenAI API 오류: {e}")

    if not result and anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                messages=[
                    {"role": "user", "content": prompt + "\n\nJSON 형식으로만 응답하세요."}
                ]
            )
            # Claude 응답에서 JSON 추출
            response_text = response.content[0].text
            # JSON 부분만 추출
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response_text[json_start:json_end])
        except Exception as e:
            if not silent:
                print(f"   Anthropic API 오류: {e}")

    # AI 응답 파싱 및 적용
    if result and 'top3' in result:
        selected_articles = []
        for item in result['top3']:
            idx = item['번호'] - 1  # 0-based index
            if 0 <= idx < len(articles):
                article = articles[idx].copy()
                article['ai_summary'] = item['요약']
                article['ai_selected'] = True
                selected_articles.append(article)

        if len(selected_articles) == 3:
            return selected_articles

    # AI 실패 시 임팩트 점수 기반 fallback
    if not silent:
        print("   -> AI 선정 실패, 임팩트 점수 기반 선정으로 대체")

    # 임팩트 점수 + 관련도 점수 결합하여 정렬
    for article in articles:
        combined = article.get('score', 0) + article.get('impact_score', 0) * 1.5
        article['combined_score'] = combined

    sorted_articles = sorted(articles, key=lambda x: x.get('combined_score', 0), reverse=True)

    return sorted_articles[:3]


def generate_short_summary(article, max_chars=100):
    """
    60-100자 짧은 요약 생성 (온다 뉴스레터 스타일)
    구체적인 숫자를 포함한 임팩트 있는 한 줄 요약
    """
    import os

    # AI 요약이 이미 있으면 그대로 사용
    if article.get('ai_summary'):
        return article['ai_summary']

    content = fetch_article_content(article['link'])
    if not content:
        content = article.get('summary', article['title'])

    openai_key = os.environ.get('OPENAI_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    prompt = f"""다음 기사를 60-100자로 요약해주세요.

요약 규칙:
1. 반드시 구체적인 숫자 포함 (금액, 비율, 증감률, 날짜 등)
2. "~했다", "~이다" 형식의 완결된 문장
3. 핵심 팩트 1개만 전달
4. 숙박/여행 업계 관점에서 중요한 포인트

예시:
- "야놀자가 500억원 규모 시리즈D 투자를 유치했다."
- "에어비앤비 한국 예약이 전년 대비 35% 증가했다."
- "숙박업 규제 완화로 1월부터 공유숙박 허용 지역이 확대된다."

제목: {article['title']}
내용: {content[:1500]}

60-100자 요약:"""

    if openai_key:
        try:
            import openai
            openai.api_key = openai_key

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )
            summary = response.choices[0].message.content.strip()
            # 따옴표 제거
            summary = summary.strip('"\'')
            if len(summary) <= 120:
                return summary
        except Exception:
            pass

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            summary = response.content[0].text.strip()
            summary = summary.strip('"\'')
            if len(summary) <= 120:
                return summary
        except Exception:
            pass

    # API 없으면 원문에서 숫자 포함 문장 추출 시도
    sentences = re.split(r'[.!?]', content)
    for sentence in sentences:
        sentence = sentence.strip()
        # 숫자가 포함된 60-100자 문장 찾기
        if re.search(r'\d+', sentence) and 40 <= len(sentence) <= 100:
            return sentence + "."

    # 최후의 수단: 제목 기반 요약
    if len(article['title']) <= 100:
        return article['title']
    return article['title'][:97] + "..."


def fetch_article_content(url):
    """
    기사 원문 가져오기
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        # 불필요한 태그 제거
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
            tag.decompose()

        # 기사 본문 찾기 (여러 선택자 시도)
        content = ""
        selectors = [
            'article',
            'div.article_body',
            'div.article-body',
            'div.news_body',
            'div.article_txt',
            'div#articleBodyContents',
            'div.content',
            'div.article-content',
            'div.view_txt',
            'div.newsct_article',
        ]

        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                content = elem.get_text(separator=' ', strip=True)
                break

        # 못 찾으면 body에서 가장 긴 텍스트 블록 찾기
        if not content or len(content) < 100:
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])

        return content[:3000]  # 최대 3000자
    except Exception as e:
        return ""


def generate_ai_summary(article, max_chars=400):
    """
    기사 내용을 바탕으로 AI 요약 생성 (OpenAI 또는 Claude 사용)
    API가 없으면 원문 요약 반환
    """
    # 먼저 기사 원문 가져오기
    content = fetch_article_content(article['link'])

    if not content:
        content = article.get('summary', article['title'])

    # API 키 확인
    import os
    openai_key = os.environ.get('OPENAI_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    if openai_key:
        try:
            import openai
            openai.api_key = openai_key

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 B2B 호스피탈리티/숙박업 전문 뉴스 에디터입니다. 기사를 ONDA(숙박 플랫폼 연동 솔루션 기업) 관점에서 핵심만 요약해주세요."},
                    {"role": "user", "content": f"다음 기사를 400자 이내로 완결된 문장으로 요약해주세요. 핵심 내용, 영향, 시사점을 포함해주세요.\n\n제목: {article['title']}\n\n내용:\n{content[:2000]}"}
                ],
                max_tokens=500,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            pass

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[
                    {"role": "user", "content": f"당신은 B2B 호스피탈리티/숙박업 전문 뉴스 에디터입니다. 다음 기사를 400자 이내로 완결된 문장으로 요약해주세요. 핵심 내용, 영향, 시사점을 포함해주세요.\n\n제목: {article['title']}\n\n내용:\n{content[:2000]}"}
                ]
            )
            return response.content[0].text.strip()
        except Exception as e:
            pass

    # API가 없으면 원문 기반 요약
    if content and len(content) > 50:
        # 첫 400자 추출 (문장 단위로 자르기)
        if len(content) > max_chars:
            # 마지막 마침표 찾기
            cut_point = content[:max_chars].rfind('.')
            if cut_point > 200:
                return content[:cut_point + 1]
            return content[:max_chars] + "..."
        return content

    # 원문을 가져오지 못한 경우 Google 검색 결과 요약 사용
    summary = article.get('summary', '')
    if summary:
        return summary

    return article['title']


def generate_summary(article):
    """
    기사 요약 생성 (기본 - 150자)
    """
    summary = article.get('summary', '')

    if not summary:
        return article['title']

    # 150자로 제한
    if len(summary) > 150:
        summary = summary[:147] + "..."

    return summary


def main():
    parser = argparse.ArgumentParser(description='ONDA 뉴스 스크래퍼')
    parser.add_argument('--email', action='store_true', help='이메일로 결과 전송')
    parser.add_argument('--to', type=str, help='받는 사람 이메일 주소')
    parser.add_argument('--silent', action='store_true', help='콘솔 출력 최소화')
    args = parser.parse_args()

    if not args.silent:
        print("=" * 80)
        print("ONDA 뉴스 스크래퍼 - B2B Hospitality Tech")
        print("=" * 80)
        print(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. 뉴스 수집
    if not args.silent:
        print("[1단계] 뉴스 수집 중...")

    articles = collect_all_news(silent=args.silent)

    if not args.silent:
        print(f"   -> {len(articles)}개 기사 수집 완료\n")

    # 2. 관련도 점수 계산
    if not args.silent:
        print("[2단계] 관련도 분석 중...")

    for article in articles:
        article['score'] = calculate_relevance_score(article)
        article['category'] = categorize_article(article)

    if not args.silent:
        print(f"   -> 키워드 점수 계산 완료")

    # 2.5 산업 임팩트 점수 계산 (Option C)
    if not args.silent:
        print("[2.5단계] 산업 임팩트 분석 중...")

    for article in articles:
        calculate_industry_impact_score(article)

    if not args.silent:
        print(f"   -> 임팩트 점수 계산 완료\n")

    # 3. 중복 제거 (1차 - 전체 기사)
    if not args.silent:
        print("[3단계] 중복 기사 제거 중...")

    before_count = len(articles)
    articles = remove_duplicates(articles, threshold=0.35)
    removed = before_count - len(articles)

    if not args.silent:
        print(f"   -> {removed}개 중복 제거 ({before_count}개 -> {len(articles)}개)\n")

    # 3.5 신선도 패널티 적용 (많이 보도된 주제 점수 감소)
    if not args.silent:
        print("[3.5단계] 신선도 분석 중...")
    articles = apply_freshness_penalty(articles)
    if not args.silent:
        print(f"   -> 신선도 패널티 적용 완료\n")

    # 4. 복합 점수로 정렬 (키워드 점수 + 임팩트 점수)
    for article in articles:
        # 임팩트 점수에 1.5배 가중치 (에디터 관점 중시)
        article['combined_score'] = article.get('score', 0) + article.get('impact_score', 0) * 1.5
    articles_sorted = sorted(articles, key=lambda x: x.get('combined_score', 0), reverse=True)

    # 5. 상위 10개 선택
    top_articles = articles_sorted[:10]

    # 5.5 TOP 10 내 추가 중복 제거 (더 엄격하게)
    if not args.silent:
        print("[4단계] TOP 10 내 중복 재검사 중...")

    final_top = []
    for article in top_articles:
        is_dup = False
        for existing in final_top:
            # 더 엄격한 유사도 체크 (0.25)
            sim = calculate_similarity(article['title'], existing['title'])
            same = is_same_story(article, existing)
            if sim >= 0.25 or same:
                is_dup = True
                break
        if not is_dup:
            final_top.append(article)

    # 부족하면 다음 순위에서 채움
    if len(final_top) < 10:
        for article in articles_sorted[10:]:
            if len(final_top) >= 10:
                break
            is_dup = False
            for existing in final_top:
                sim = calculate_similarity(article['title'], existing['title'])
                same = is_same_story(article, existing)
                if sim >= 0.25 or same:
                    is_dup = True
                    break
            if not is_dup:
                final_top.append(article)

    top_articles = final_top[:10]

    if not args.silent:
        print(f"   -> TOP 10 중복 제거 완료 (최종 {len(top_articles)}개)\n")

    # 6. AI 에디터로 TOP 3 선정 (Option A)
    if not args.silent:
        print("[4단계] AI 에디터 TOP 3 선정 중...")

    top3_articles = ai_editor_select_top3(top_articles, silent=args.silent)

    if not args.silent:
        ai_selected = sum(1 for a in top3_articles if a.get('ai_selected', False))
        print(f"   -> AI 선정 {ai_selected}개 완료")

    # 7. TOP 3 짧은 요약 생성 (60-100자)
    if not args.silent:
        print("[5단계] TOP 3 기사 요약 생성 중...")

    for idx, article in enumerate(top3_articles, 1):
        if not args.silent:
            print(f"   [{idx}/3] {article['title'][:30]}... 요약 중")
        # AI 에디터가 이미 요약했으면 스킵, 아니면 생성
        if not article.get('ai_summary'):
            article['short_summary'] = generate_short_summary(article, max_chars=100)
        else:
            article['short_summary'] = article['ai_summary']
        # 기존 호환성을 위해 detailed_summary도 설정
        article['detailed_summary'] = article['short_summary']

    if not args.silent:
        print(f"   -> TOP 3 요약 완료\n")

    # top_articles에 top3 반영 (이메일 등에서 사용)
    for i, article in enumerate(top3_articles):
        if i < len(top_articles):
            top_articles[i] = article

    # 7. 이메일 전송 (옵션)
    if args.email:
        if not args.to:
            print("오류: --to 옵션으로 받는 사람 이메일을 지정해주세요.")
            return

        if not args.silent:
            print("[4단계] 이메일 전송 중...")

        subject = f"ONDA 뉴스 브리핑 - {datetime.now().strftime('%Y년 %m월 %d일')}"
        html_content = create_onda_html_email(top_articles)

        success = send_email_gmail(args.to, subject, html_content)

        if success:
            if not args.silent:
                print(f"   -> 이메일 전송 완료: {args.to}\n")
            else:
                print(f"SUCCESS: Email sent to {args.to}")
        else:
            print(f"FAILED: Email sending failed")

        return

    # 8. 콘솔 출력
    print("\n" + "=" * 80)
    print("ONDA 뉴스 브리핑 - TOP 10")
    print("=" * 80)

    # TOP 3 상세 출력 (AI 에디터 선정)
    print("\n*** TOP 3 주요 뉴스 (AI 에디터 선정) ***\n")

    for idx, article in enumerate(top_articles[:3], 1):
        ai_badge = "[AI선정]" if article.get('ai_selected') else ""
        impact_info = f"임팩트: {article.get('impact_score', 0)}점" if article.get('impact_score') else ""
        print(f"[{idx}위] {ai_badge} {article['category']} | 키워드: {article['score']}점 | {impact_info}")
        print("-" * 80)
        print(f"제목: {article['title']}")
        print(f"\n요약 ({len(article.get('short_summary', ''))}자):")
        print(f"  {article.get('short_summary', article.get('detailed_summary', article['summary'][:100]))}")
        if article.get('impact_factors'):
            print(f"\n임팩트 요인: {', '.join(article['impact_factors'])}")
        print(f"\n출처: {article['source']}")
        print(f"링크: {article['link']}")
        print("=" * 80 + "\n")

    # 4~10위 간략 출력
    print("\n*** 4~10위 뉴스 ***\n")

    for idx, article in enumerate(top_articles[3:10], 4):
        combined = article.get('combined_score', article.get('score', 0))
        print(f"[{idx}위] [{article['category']}] {article['title']}")
        print(f"      출처: {article['source']} | 복합점수: {combined:.0f}점")
        print(f"      링크: {article['link']}")
        print()

    print("\n완료! ONDA 팀과 공유하세요.")


if __name__ == "__main__":
    main()
