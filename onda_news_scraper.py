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
import os
import json
from urllib.parse import quote
from email_sender import create_onda_html_email, send_email_gmail
# Slack 발송은 워크플로우에서 직접 처리 (CLI 옵션 비활성화됨)

# ============================================
# 스크랩 히스토리 관리 (중복 기사 방지)
# ============================================

HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'scrape_history.json')
HISTORY_DAYS = 7  # 7일간 히스토리 유지


def load_scrape_history():
    """
    스크랩 히스토리 로드
    """
    if not os.path.exists(HISTORY_FILE):
        return {'articles': [], 'last_updated': None}

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)

        # 오래된 항목 제거 (7일 이상)
        cutoff = datetime.now() - timedelta(days=HISTORY_DAYS)
        history['articles'] = [
            a for a in history['articles']
            if datetime.fromisoformat(a['scraped_at']) > cutoff
        ]

        return history
    except Exception:
        return {'articles': [], 'last_updated': None}


def save_scrape_history(history):
    """
    스크랩 히스토리 저장
    """
    history['last_updated'] = datetime.now().isoformat()
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"히스토리 저장 실패: {e}")


def add_to_history(articles, history):
    """
    스크랩한 기사를 히스토리에 추가
    """
    now = datetime.now().isoformat()
    for article in articles:
        history['articles'].append({
            'title': article['title'],
            'link': article['link'],
            'scraped_at': now
        })
    return history


def is_already_scraped(article, history):
    """
    이미 스크랩한 기사인지 확인
    - 같은 링크
    - 또는 제목 유사도 50% 이상 (기존 70%에서 하향)
    - 또는 핵심 키워드가 동일한 경우
    """
    for hist_article in history['articles']:
        # 같은 링크면 중복
        if article['link'] == hist_article['link']:
            return True

        # 제목 유사도 체크 (50% 이상이면 중복 - 기존 70%에서 하향)
        similarity = calculate_similarity(article['title'], hist_article['title'])
        if similarity >= 0.5:
            return True

        # 핵심 키워드 기반 중복 체크 (새로 추가)
        # 제목에서 핵심 키워드 추출하여 비교
        if has_same_core_keywords(article['title'], hist_article['title']):
            return True

        # 같은 스토리인지 체크
        # (히스토리 기사는 summary가 없을 수 있으므로 간단히 체크)
        hist_as_article = {'title': hist_article['title'], 'summary': ''}
        if is_same_story(article, hist_as_article):
            return True

    return False


def has_same_core_keywords(title1, title2):
    """
    두 제목이 같은 핵심 키워드를 공유하는지 확인
    예: "해외숙박 예약 플랫폼 이용자 절반 이상 피해 경험"
        "해외숙박 예약 플랫폼 이용자 54.6% 피해 경험"
    -> 핵심 키워드: 해외숙박, 플랫폼, 이용자, 피해 -> 중복
    """
    import re

    # 불용어 (의미 없는 단어)
    stopwords = {
        '의', '를', '을', '이', '가', '은', '는', '에', '에서', '와', '과',
        '로', '으로', '도', '만', '더', '등', '및', '또', '그', '저', '이런',
        '것', '수', '중', '후', '전', '약', '각', '매', '내', '외', '상', '하',
        '대', '소', '신', '구', '위', '아래', '앞', '뒤', '간', '별', '당',
        '말', '년', '월', '일', '시', '분', '초', '명', '개', '곳', '번',
        '절반', '이상', '최대', '최소', '약', '경험', '집중', '새해', '올해'
    }

    # 중요 회사명/브랜드 (이것만 같아도 같은 주제일 가능성 높음)
    important_entities = [
        '야놀자', '야놀자리서치', '여기어때', '에어비앤비', '부킹닷컴', '익스피디아',
        '트립닷컴', '아고다', '호텔스닷컴', '마이리얼트립', '온다', 'onda',
        '네이버', '카카오', '쏘카', '인터파크'
    ]

    # 핵심 키워드 추출 (2글자 이상, 숫자/% 제외, 불용어 제외)
    def extract_keywords(title):
        # 숫자와 % 제거
        title_clean = re.sub(r'\d+\.?\d*%?', '', title)
        # 특수문자 제거 (한글, 영문, 숫자만 남김)
        title_clean = re.sub(r'[^\w\s가-힣]', ' ', title_clean)
        # 단어 분리
        words = title_clean.lower().split()
        # 2글자 이상, 불용어 제외
        keywords = set(w for w in words if len(w) >= 2 and w not in stopwords)
        return keywords

    def find_entities(title):
        """제목에서 중요 엔티티(회사명) 찾기"""
        title_lower = title.lower()
        found = set()
        for entity in important_entities:
            if entity.lower() in title_lower:
                found.add(entity.lower())
        return found

    kw1 = extract_keywords(title1)
    kw2 = extract_keywords(title2)

    # 중요 엔티티(회사명) 체크 - 같은 회사가 언급되면 중복 가능성 높음
    entities1 = find_entities(title1)
    entities2 = find_entities(title2)
    common_entities = entities1 & entities2

    if not kw1 or not kw2:
        return False

    # 공통 키워드 비율 계산
    common = kw1 & kw2
    smaller_set = min(len(kw1), len(kw2))

    # 같은 회사명 + 공통 키워드 2개 이상이면 중복
    if common_entities and len(common) >= 2:
        return True

    # 작은 집합의 50% 이상이 공통이면 중복 (기존 60%에서 하향)
    if smaller_set > 0 and len(common) / smaller_set >= 0.5:
        return True

    # 핵심 주제 키워드가 3개 이상 공통이면 중복
    if len(common) >= 3:
        return True

    return False


def filter_already_scraped(articles, history, silent=False):
    """
    이미 스크랩한 기사 필터링
    """
    new_articles = []
    skipped = 0

    for article in articles:
        if is_already_scraped(article, history):
            skipped += 1
        else:
            new_articles.append(article)

    if not silent and skipped > 0:
        print(f"   -> 이전 스크랩 기사 {skipped}개 제외")

    return new_articles

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
    # 최근 3일 뉴스 (tbs=qdr:d3) - 신선도 유지
    url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&hl=ko&tbs=qdr:d3"

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


def extract_actual_publish_date(url, timeout=5):
    """
    기사 URL에서 실제 발행일 추출 (구글 뉴스 time_text 검증용)

    Returns:
        str: YYYY-MM-DD 형식 날짜 또는 None
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. meta article:published_time (가장 신뢰할 수 있음)
        meta = soup.find('meta', {'property': 'article:published_time'})
        if meta and meta.get('content'):
            return meta['content'][:10]

        # 2. meta datePublished
        meta = soup.find('meta', {'itemprop': 'datePublished'})
        if meta and meta.get('content'):
            return meta['content'][:10]

        # 3. JSON-LD structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.text)
                if isinstance(data, dict) and 'datePublished' in data:
                    return data['datePublished'][:10]
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'datePublished' in item:
                            return item['datePublished'][:10]
            except:
                pass

        # 4. time 태그의 datetime 속성
        time_tag = soup.find('time', datetime=True)
        if time_tag:
            return time_tag['datetime'][:10]

        # 5. URL에서 날짜 패턴 추출 (fallback)
        date_patterns = [
            r'/(\d{4})/(\d{2})/(\d{2})/',
            r'/(\d{4})(\d{2})(\d{2})',
            r'[=/](\d{4})-(\d{2})-(\d{2})',
            r'[=/](\d{4})\.(\d{2})\.(\d{2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, url)
            if match:
                return f'{match.group(1)}-{match.group(2)}-{match.group(3)}'

        return None
    except Exception:
        return None


def verify_article_freshness(article, max_days=2):
    """
    기사의 실제 발행일을 확인하여 신선도 검증

    Args:
        article: 기사 dict (link/url 필드 필요)
        max_days: 허용할 최대 일수 (기본 2일)

    Returns:
        tuple: (is_fresh: bool, actual_date: str or None)
    """
    url = article.get('link') or article.get('url')
    if not url:
        return False, None

    actual_date = extract_actual_publish_date(url)
    if not actual_date:
        return True, None  # 날짜를 못 찾으면 일단 통과 (time_text에 의존)

    try:
        pub_date = datetime.strptime(actual_date, '%Y-%m-%d')
        days_old = (datetime.now() - pub_date).days

        article['actual_publish_date'] = actual_date
        article['days_old'] = days_old

        return days_old <= max_days, actual_date
    except:
        return True, actual_date


def is_too_old_article(article):
    """
    48시간(2일) 이상 지난 기사인지 체크
    True면 너무 오래된 기사 (제외 대상)

    신선한 뉴스 브리핑을 위해 엄격하게 필터링:
    - 24시간 이내: 통과
    - 1일 전: 통과
    - 2일 전 이상: 제외
    """
    time_text = article.get('time_text', '')
    if not time_text:
        return True  # 시간 정보가 없으면 오래된 것으로 간주하여 제외

    # 신선한 기사 마커 (통과)
    fresh_markers = ['분 전', '시간 전', '1일 전', '1일전', '어제']
    for marker in fresh_markers:
        if marker in time_text:
            return False  # 신선한 기사

    # 2일 이상 된 기사는 모두 제외
    old_markers = ['2일', '3일', '4일', '5일', '6일', '7일', '주일', '주 전', '개월', '년 전']
    for marker in old_markers:
        if marker in time_text:
            return True

    return False  # 알 수 없는 형식이면 일단 통과


def is_relevant_article(article):
    """
    ONDA 관련 기사인지 필터링
    - 핵심 키워드가 하나라도 있어야 관련 기사로 인정
    - 48시간(2일) 이상 지난 기사는 제외
    - 신뢰할 수 없는 소스(MSN 등)는 제외
    """
    # 신뢰할 수 없는 소스 제외 (날짜 검증 불가, 오래된 기사 재노출 문제)
    UNTRUSTED_SOURCES = ['msn.com', 'nate.com']
    link = article.get('link', '') or article.get('url', '')
    for source in UNTRUSTED_SOURCES:
        if source in link.lower():
            return False

    # 48시간 이상 지난 기사는 제외
    if is_too_old_article(article):
        return False

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

    # 2. 규제/정책 변화 (45점) - 정책 기사 우선순위 상향
    regulation_match = 0
    for kw in REGULATION_KEYWORDS:
        if kw.lower() in text:
            regulation_match += 1
    if regulation_match > 0:
        impact_score += min(45, regulation_match * 15)
        impact_factors.append('규제/정책')

    # 2-1. 숙박업 직접 관련 정책만 보너스 (+35점)
    # 숙박업법, 공유숙박 등 숙박업 직접 관련 정책만 높은 점수
    accommodation_policy_keywords = [
        '숙박업법', '공유숙박', '생활숙박', '숙박업 규제', '숙박시설',
        '호텔업', '숙박업 허가', '숙박업 등록', '객실 규제'
    ]
    accom_policy_match = 0
    for kw in accommodation_policy_keywords:
        if kw in text:
            accom_policy_match += 1
    if accom_policy_match > 0:
        impact_score += min(35, accom_policy_match * 15)
        impact_factors.append('숙박정책')

    # 2-2. 일반 관광 정책은 낮은 점수 (+15점)
    # 숙박과 직접 관련 없는 관광 정책은 낮은 가중치
    general_tourism_keywords = [
        '관광진흥', '관광정책', 'K-관광', '관광산업', '인바운드', '아웃바운드',
        '관광객 유치', '관광 활성화'
    ]
    general_tourism_match = 0
    for kw in general_tourism_keywords:
        if kw in text:
            general_tourism_match += 1
    if general_tourism_match > 0 and accom_policy_match == 0:
        # 숙박 정책이 없을 때만 일반 관광 점수 부여 (낮은 점수)
        impact_score += min(15, general_tourism_match * 8)
        impact_factors.append('일반관광정책')

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

    # 6-1. 제목에 회사명/업계 키워드가 있으면 보너스 (+30점)
    # 제목에 특정 회사나 업계가 명시되면 뉴스 가치가 높음
    title_company_keywords = [
        # 주요 OTA/플랫폼
        '야놀자', '여기어때', '에어비앤비', '아고다', '부킹닷컴', '트립닷컴',
        '마이리얼트립', '호텔스닷컴', '익스피디아', '트립어드바이저',
        # 호텔 체인
        '메리어트', '힐튼', '아코르', '하얏트', '신라호텔', '롯데호텔',
        # 업계 키워드
        '숙박업', '호텔업', 'OTA', '여행업', '관광업', '호스피탈리티'
    ]
    for kw in title_company_keywords:
        if kw.lower() in title:
            impact_score += 30
            impact_factors.append(f'제목회사:{kw}')
            break

    # 6-2. B2B 숙박 IT/솔루션 관련 보너스 (+50점)
    # ONDA 핵심 비즈니스와 직접 관련된 B2B 솔루션/IT 키워드
    b2b_solution_keywords = [
        # 숙박 솔루션
        'pms', 'cms', 'rms', '채널매니저', '채널 매니저', '예약 시스템',
        '숙박 솔루션', '호텔 솔루션', '숙박업 솔루션', '통합 관리',
        '객실 관리', '예약 관리', '재고 관리', '요금 관리',
        # B2B 키워드
        'b2b', 'saas', 'api', '연동', '플랫폼 연동', 'ota 연동',
        # 업계 행사
        '호텔페어', '호텔쇼', '관광박람회', 'itb', 'wtm',
        # 기술 키워드
        '자동화', 'ai 도입', '디지털 전환', 'dx', '클라우드'
    ]
    b2b_match = 0
    for kw in b2b_solution_keywords:
        if kw.lower() in text:
            b2b_match += 1
    if b2b_match >= 2:
        impact_score += 50
        impact_factors.append('B2B솔루션')
    elif b2b_match == 1:
        impact_score += 25
        impact_factors.append('B2B솔루션')

    # 6-3. 숙박업계 AI 활용 관련 보너스 (+70점)
    # 호스피탈리티 업계의 AI 도입, 디지털 전환 관련 기사는 매우 중요
    ai_hospitality_keywords = [
        # AI + 숙박/호텔 조합
        'ai 호텔', 'ai 숙박', 'ai 예약', 'ai 플랫폼', 'ai 도입',
        '인공지능 호텔', '인공지능 숙박', '인공지능 예약',
        # 숙박업 디지털 전환
        '숙박 ai', '호텔 ai', '숙박플랫폼', '플랫폼 탈출',
        '직접 예약', 'd2c', '자체 예약', '수수료 절감',
        # 챗봇/자동화
        '호텔 챗봇', '숙박 챗봇', '예약 챗봇', '자동 응대',
        # 데이터/분석
        '수요 예측', '가격 최적화', '동적 가격', '레비뉴 매니지먼트'
    ]
    ai_hosp_match = 0
    for kw in ai_hospitality_keywords:
        if kw.lower() in text:
            ai_hosp_match += 1
    if ai_hosp_match >= 2:
        impact_score += 70
        impact_factors.append('AI숙박업')
    elif ai_hosp_match == 1:
        impact_score += 40
        impact_factors.append('AI숙박업')

    # 7. 회사별 중요도 점수 (업계 기업 소식 우선)
    # Tier 0: 자사 ONDA (+80점) - 상향
    # Tier 1: 국내 대형 OTA (+60점) - 상향: 야놀자, 여기어때, 마이리얼트립
    # Tier 2: 국내 주요 플랫폼 (+50점) - 상향: 네이버, 카카오, 쏘카, 인터파크트리플
    # Tier 3: 글로벌 대형 OTA (+50점) - 상향: 에어비앤비, 부킹홀딩스, 익스피디아, 트립닷컴
    # Tier 4: 글로벌 메타서치/검색 (+40점) - 상향
    # Tier 5: 국내 중소 플랫폼 (+45점) - 상향
    # Tier 6: 글로벌 숙박/호텔 플랫폼 (+35점) - 상향
    # Tier 7: 호텔 체인/숙박업체 (+40점) - 신규 추가
    # 업계 키워드: PMS, CMS, GDS 등 (+35점)

    company_tiers = {
        # Tier 0: 자사 (최고 우선순위)
        0: {
            'score': 80,
            'label': '자사',
            'keywords': ['온다', 'onda']
        },
        # Tier 1: 국내 대형 OTA (시총/기업가치 높음)
        1: {
            'score': 60,
            'label': '국내대형OTA',
            'keywords': ['야놀자', 'nol', '놀유니버스', '여기어때', '마이리얼트립', '마리트']
        },
        # Tier 2: 국내 주요 플랫폼 (대기업/상장사)
        2: {
            'score': 50,
            'label': '국내플랫폼',
            'keywords': ['네이버', '카카오', '쏘카', '인터파크트리플', '인터파크', '위메프', '티몬']
        },
        # Tier 3: 글로벌 대형 OTA (시총 수십~수백조)
        3: {
            'score': 50,
            'label': '글로벌대형OTA',
            'keywords': ['에어비앤비', 'airbnb', '부킹닷컴', 'booking.com', '부킹홀딩스',
                        '익스피디아', 'expedia', '트립닷컴', 'trip.com']
        },
        # Tier 4: 글로벌 메타서치/검색엔진 (트래픽 대형)
        4: {
            'score': 40,
            'label': '메타서치',
            'keywords': ['구글호텔', 'google hotel', '트립어드바이저', 'tripadvisor',
                        '스카이스캐너', 'skyscanner', '카약', 'kayak', '트리바고', 'trivago',
                        '호텔스컴바인', '메타서치', '여행 검색 엔진', '호텔 검색 플랫폼']
        },
        # Tier 5: 국내 중소 플랫폼 (국내라 해외보다 우선)
        5: {
            'score': 45,
            'label': '국내중소OTA',
            'keywords': ['트립비토즈', '타이드스퀘어', '크리에이트립', '세시간전',
                        '더케이교직원나라', '교직원나라']
        },
        # Tier 6: 글로벌 숙박/호텔 플랫폼
        6: {
            'score': 35,
            'label': '글로벌숙박',
            'keywords': ['아고다', 'agoda', '호텔스닷컴', 'hotels.com']
        },
        # Tier 7: 호텔 체인/숙박업체 (점수 낮춤 - B2B 고객 아님)
        7: {
            'score': 15,
            'label': '호텔체인',
            'keywords': ['메리어트', 'marriott', '힐튼', 'hilton', '아코르', 'accor',
                        'ihg', '하얏트', 'hyatt', '신라호텔', '롯데호텔', '파라다이스호텔',
                        '조선호텔', '그랜드하얏트', '호텔신라', '워커힐']
        },
        # Tier 8: 중소형 숙박 (ONDA 주요 고객층)
        8: {
            'score': 35,
            'label': '중소형숙박',
            'keywords': ['펜션', '모텔', '게스트하우스', '민박', '풀빌라', '호스텔',
                        '중소형 숙박', '소형 숙박', '개인 숙박', '독채', '한옥스테이']
        },
    }

    # 업계 키워드 (회사 특정 안되어도 업계 전체 이슈면 중요)
    industry_keywords = {
        'score': 35,
        'label': '업계이슈',
        'keywords': ['여행/숙박/호텔업계', '여행/숙박/호텔산업', '숙박 위탁 운영', '숙박 예약',
                    '생활형 숙박시설', 'gds', 'pms', 'cms', 'ota', '온라인여행사',
                    '호스피탈리티', '숙박업', '숙박산업', '호텔산업', '객실 점유율',
                    'adr', 'revpar', '채널매니저', '예약 시스템']
    }

    company_found = False

    # Tier 순서대로 체크 (낮은 Tier = 높은 우선순위)
    for tier in sorted(company_tiers.keys()):
        if company_found:
            break
        tier_info = company_tiers[tier]
        for keyword in tier_info['keywords']:
            if keyword.lower() in text:
                impact_score += tier_info['score']
                impact_factors.append(f"{tier_info['label']}:{keyword}")
                company_found = True
                break

    # 회사가 특정되지 않았으면 업계 키워드 체크
    if not company_found:
        for keyword in industry_keywords['keywords']:
            if keyword.lower() in text:
                impact_score += industry_keywords['score']
                impact_factors.append(f"{industry_keywords['label']}:{keyword}")
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

    # 9-1. 호텔 B2C 기사 페널티 (-50점)
    # 호텔 패키지, 뷔페, F&B, 다이닝 등은 B2B 숙박 IT와 관련 낮음
    hotel_b2c_keywords = [
        # 패키지/상품
        '패키지', '상품 출시', '신년 패키지', '연말 패키지', '겨울 패키지',
        '해돋이', '새해맞이', '연말연시',
        # F&B/다이닝
        '뷔페', 'f&b', '다이닝', '레스토랑', '조식', '브런치',
        '먹거리', '맛집', '미식', '셰프', '메뉴',
        # 호텔 시설/서비스 (B2C)
        '스파', '수영장', '피트니스', '웨딩', '연회', '컨벤션',
        '호캉스', '스테이케이션', '휴식'
    ]
    hotel_b2c_count = 0
    for kw in hotel_b2c_keywords:
        if kw in text:
            hotel_b2c_count += 1

    # 호텔업계 + B2C 키워드 조합이면 페널티
    hotel_industry_keywords = ['호텔업계', '호텔·리조트', '특급호텔', '5성급', '호텔 업계']
    has_hotel_industry = any(kw in text for kw in hotel_industry_keywords)

    if has_hotel_industry and hotel_b2c_count >= 2:
        impact_score -= 60
        impact_factors.append('호텔B2C기사')
    elif hotel_b2c_count >= 3:
        impact_score -= 50
        impact_factors.append('호텔B2C기사')
    elif has_hotel_industry and hotel_b2c_count >= 1:
        impact_score -= 30
        impact_factors.append('호텔B2C기사')

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

    # 10-1. 지방정부/지방공기업 페널티 (-100점 ~ -500점)
    # 지자체, 지방관광공사, 도청, 시청 등 지방 이슈는 ONDA 비즈니스와 관련 낮음
    # 단, 직접적인 숙박업 지원책/모집 공고는 예외
    local_gov_keywords = [
        '지자체', '도청', '시청', '군청', '구청',
        '도지사', '시장', '군수', '구청장',
        '지방관광공사', '도관광공사', '시관광공사',
        # 지방관광공사/재단 (전체 - 인천 등 누락분 추가)
        '경기관광공사', '강원관광재단', '충남관광재단', '충북관광재단',
        '전남관광재단', '전북관광재단', '경남관광재단', '경북관광공사',
        '인천관광공사', '부산관광공사', '대구관광재단', '대전관광공사',
        '광주관광재단', '울산관광재단', '제주관광공사', '세종관광재단',
        # 지역 이슈
        '지역 관광', '지역 축제', '지역 행사', '군 축제', '읍면동',
        '관광안내소', '관광 인프라', '지역 명소', '옹진군', '선재도'
    ]

    # 신년사/취임사 등 일반 행정 기사는 강력히 제외
    ceremonial_keywords = [
        '신년사', '취임사', '이취임', '시무식', '기념식',
        '신년 인사', '신년 메시지', '새해 인사', '새해 메시지',
        '시정연설', '도정연설', '군정연설', '구정연설'
    ]

    # 직접적 지원책 키워드 (이 경우 페널티 감소) - 숙박업 직접 관련만
    direct_support_keywords = [
        '숙박업 지원', '숙박시설 지원', '숙박업체 지원',
        '소상공인 지원', '창업 지원', '융자', '대출 지원',
        '숙박업 보조금', '숙박 지원금'
    ]

    local_gov_count = 0
    for kw in local_gov_keywords:
        if kw in text:
            local_gov_count += 1

    ceremonial_count = 0
    for kw in ceremonial_keywords:
        if kw in text:
            ceremonial_count += 1

    direct_support_count = 0
    for kw in direct_support_keywords:
        if kw in text:
            direct_support_count += 1

    # 신년사/취임사 등은 강력한 페널티 (-500점, 사실상 제외)
    if ceremonial_count > 0:
        impact_score -= 500
        impact_factors.append('신년사/취임사제외')
    elif local_gov_count >= 2 and direct_support_count == 0:
        # 지방정부 기사인데 직접 지원책이 아니면 강한 페널티
        impact_score -= 100
        impact_factors.append('지방정부기사')
    elif local_gov_count == 1 and direct_support_count == 0:
        impact_score -= 50
        impact_factors.append('지방정부기사')

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

    # 11-1. 해외 사건/사고 기사 페널티 (-100점)
    # 해외 리조트 화재, 사고 등은 국내 숙박 IT 업계와 직접 관련 없음
    incident_keywords = ['폭발', '화재', '사망', '부상', '참사', '재난', '테러', '총격', '붕괴', '침몰', '추락']
    foreign_keywords = ['스위스', '미국', '일본', '중국', '유럽', '태국', '베트남', '프랑스', '독일', '영국', '호주', '뉴질랜드', '캐나다', '멕시코', '브라질', '인도네시아', '필리핀', '말레이시아', '이탈리아', '스페인']

    has_incident = any(kw in text for kw in incident_keywords)
    has_foreign = any(kw in text for kw in foreign_keywords)

    # 해외 + 사건/사고 조합이면 페널티
    if has_incident and has_foreign:
        impact_score -= 100
        impact_factors.append('해외사건사고')
    elif has_incident:
        # 국내 사건/사고도 약한 페널티 (업계 뉴스와 관련 낮음)
        impact_score -= 30
        impact_factors.append('사건사고')

    # 12. 정치 기사 페널티 (-500점, 완전 제외)
    # 정치인 개인의 사적 이슈, 수사, 기소, 스캔들 등은 산업 뉴스와 무관
    # 정책 기사(산업에 영향)와 정치 기사(개인 이슈)를 구분
    politics_keywords = [
        # 정치인/정당 관련 (한국)
        '대통령', '전 대통령', '국회의원', '장관', '전 장관',
        '여당', '야당', '민주당', '국민의힘', '정치인',
        # 해외 정치인 (추가)
        '트럼프', 'trump', '바이든', 'biden', '오바마', '시진핑',
        '푸틴', '마크롱', '기시다', '백악관', 'white house',
        # 정치 스캔들/수사 관련 (강화)
        '기소', '구속', '체포', '영장', '검찰', '경찰 수사',
        '뇌물', '횡령', '배임', '비리', '스캔들', '탄핵',
        '청문회', '국정감사', '특검', '공소', '재판', '불구속',
        '피의자', '혐의', '압수수색',
        # 성범죄/스캔들 관련 (추가)
        '엡스타인', 'epstein', '성범죄', '성추행', '성폭행',
        # 정치인 가족/측근 (강화)
        '문다혜', '문재인', '윤석열', '김건희',
        '딸', '아들', '부인', '남편', '측근', '비서', '사위', '며느리',
        # 선거 관련
        '대선', '총선', '지방선거', '후보', '공천', '출마'
    ]
    politics_count = 0
    for kw in politics_keywords:
        if kw in text:
            politics_count += 1

    # 정치 키워드가 1개라도 있으면 강력한 페널티
    if politics_count >= 2:
        impact_score -= 500  # 완전 제외 수준
        impact_factors.append('정치기사제외')
    elif politics_count == 1:
        impact_score -= 200  # 강한 페널티
        impact_factors.append('정치관련제외')

    # 12-1. 호스피탈리티/숙박 맥락 검증 페널티 (-80점)
    # 야놀자 등 키워드가 매칭되어도 실제 숙박/여행 관련 내용이 아니면 페널티
    # 예: 야구장에서 야놀자 광고가 언급되는 경우
    hospitality_context_keywords = [
        # 숙박 관련
        '숙박', '호텔', '객실', '예약', '체크인', '체크아웃', '숙소',
        '리조트', '펜션', '게스트하우스', '모텔', '민박', '풀빌라',
        # 여행 관련
        '여행', '관광', '투어', '휴양', '휴가', '여행객', '관광객',
        # 플랫폼/서비스 관련
        'OTA', '플랫폼', '앱', '예약 서비스', '숙박 플랫폼',
        # 업계 관련
        '호스피탈리티', '숙박업', '호텔업', '여행업', '관광업',
        # 비즈니스 관련
        '투자', '펀딩', '인수', '합병', '실적', '매출', '영업이익'
    ]

    # 비관련 맥락 키워드 (이 키워드가 많으면 숙박/여행과 관련 없을 가능성)
    unrelated_context_keywords = [
        # 스포츠
        '야구', '축구', '농구', '배구', '경기장', '스타디움', '관중',
        '프로야구', 'KBO', 'K리그', '올림픽', '월드컵',
        # 연예/엔터
        '드라마', '영화', '콘서트', '공연', '연예인', '아이돌', '배우',
        # 정치
        '국회', '정당', '선거', '후보',
        # 기타
        '주식', '코스피', '코스닥', '부동산', '아파트', '분양'
    ]

    hospitality_context_count = 0
    for kw in hospitality_context_keywords:
        if kw in text:
            hospitality_context_count += 1

    unrelated_context_count = 0
    for kw in unrelated_context_keywords:
        if kw in text:
            unrelated_context_count += 1

    # 호스피탈리티 맥락이 거의 없고 비관련 맥락이 많으면 페널티
    if hospitality_context_count <= 1 and unrelated_context_count >= 2:
        impact_score -= 80
        impact_factors.append('맥락불일치')
    elif hospitality_context_count == 0 and unrelated_context_count >= 1:
        impact_score -= 60
        impact_factors.append('맥락불일치')

    # 13. 오래된 기사 페널티 (강화됨)
    # 신선한 뉴스 브리핑을 위해 엄격한 시간 기반 페널티
    time_text = article.get('time_text', '')

    if not time_text:
        # 시간 정보가 없으면 오래된 것으로 간주
        impact_score -= 100
        impact_factors.append('시간미상')
    elif any(x in time_text for x in ['2일', '3일', '4일', '5일', '6일', '7일', '주일', '주 전', '개월', '년 전']):
        # 2일 이상 된 기사는 강한 페널티
        impact_score -= 150  # 강화된 페널티
        impact_factors.append('오래된기사')
    elif '1일' in time_text and '시간' not in time_text:
        # "1일 전"은 약한 페널티 (24~48시간 사이)
        impact_score -= 30
        impact_factors.append('어제기사')
    elif '시간' in time_text or '분' in time_text:
        # 24시간 이내 기사는 보너스
        impact_score += 20
        impact_factors.append('최신기사')

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
    - 핵심 키워드 공유 체크 추가
    """
    unique = []

    for article in articles:
        is_duplicate = False

        for existing in unique:
            # 1. 제목 유사도 체크
            similarity = calculate_similarity(article['title'], existing['title'])

            # 2. 같은 스토리인지 체크 (회사+이벤트 또는 회사+금액)
            same_story = is_same_story(article, existing)

            # 3. 핵심 키워드 공유 체크 (회사명 + 공통 키워드)
            same_keywords = has_same_core_keywords(article['title'], existing['title'])

            if similarity >= threshold or same_story or same_keywords:
                is_duplicate = True
                # 점수가 더 높은 것 유지
                if article.get('score', 0) > existing.get('score', 0):
                    unique.remove(existing)
                    unique.append(article)
                break

        if not is_duplicate:
            unique.append(article)

    return unique


def get_main_company(article):
    """
    기사의 주요 회사명 추출 (OTA/플랫폼 중심)
    Tier 순서대로 체크하여 가장 중요한 회사 반환
    """
    text = (article['title'] + ' ' + article.get('summary', '')).lower()

    # 회사 그룹 정의 (같은 그룹은 동일 회사로 취급)
    # 주의: 순서가 중요함! 더 구체적인 키워드를 먼저 체크
    company_groups = [
        # Tier 1: 국내 대형 OTA (야놀자를 먼저 체크해야 "야놀자리서치...온다" 같은 기사에서 야놀자로 분류됨)
        ('야놀자', ['야놀자', 'nol', '놀유니버스', '놀 유니버스', '야놀자리서치', '야놀자클라우드']),
        # Tier 0: 자사 (온다는 동사로 오인될 수 있어 나중에 체크)
        ('온다', ['onda']),  # '온다'는 동사와 혼동되므로 영문만 사용
        ('여기어때', ['여기어때', '위드이노베이션']),
        ('마이리얼트립', ['마이리얼트립', '마리트']),
        # Tier 2: 국내 주요 플랫폼
        ('네이버', ['네이버']),
        ('카카오', ['카카오']),
        ('쏘카', ['쏘카', 'socar']),
        ('인터파크', ['인터파크트리플', '인터파크']),
        ('티몬', ['티몬', 'tmon']),
        ('위메프', ['위메프']),
        # Tier 3: 글로벌 대형 OTA
        ('에어비앤비', ['에어비앤비', 'airbnb']),
        ('부킹닷컴', ['부킹닷컴', 'booking.com', '부킹홀딩스', '부킹']),
        ('익스피디아', ['익스피디아', 'expedia']),
        ('트립닷컴', ['트립닷컴', 'trip.com']),
        # Tier 4: 글로벌 메타서치
        ('구글호텔', ['구글호텔', 'google hotel']),
        ('트립어드바이저', ['트립어드바이저', 'tripadvisor']),
        ('스카이스캐너', ['스카이스캐너', 'skyscanner']),
        ('카약', ['카약', 'kayak']),
        ('트리바고', ['트리바고', 'trivago']),
        ('호텔스컴바인', ['호텔스컴바인']),
        # Tier 5: 국내 중소 OTA
        ('트립비토즈', ['트립비토즈']),
        ('타이드스퀘어', ['타이드스퀘어']),
        ('크리에이트립', ['크리에이트립']),
        ('세시간전', ['세시간전']),
        ('더케이교직원나라', ['더케이교직원나라', '교직원나라']),
        # Tier 6: 글로벌 숙박
        ('아고다', ['아고다', 'agoda']),
        ('호텔스닷컴', ['호텔스닷컴', 'hotels.com']),
    ]

    for main_company, aliases in company_groups:
        for alias in aliases:
            if alias in text:
                return main_company

    return None


def get_article_topic(article):
    """
    기사의 주요 주제/이슈 추출
    같은 이슈에 대한 기사가 여러 개일 때 다양성 확보용
    """
    text = (article['title'] + ' ' + article.get('summary', '')).lower()

    # 주요 이슈/주제 키워드 그룹
    topic_groups = [
        ('생활숙박시설', ['생활숙박시설', '생숙', '레지던스', '주거용', '불법숙박', '숙박시설 규제']),
        ('외국인관광객', ['외국인 관광객', '외래 관광객', '인바운드', '방한 관광객', '관광객 유치']),
        ('항공', ['항공', '비행기', '공항', '노선', '취항', '항공권']),
        ('크루즈', ['크루즈', '유람선', '선박']),
        ('카지노', ['카지노', '복합리조트', 'ir']),
        ('면세점', ['면세점', '면세']),
        ('호캉스', ['호캉스', '스테이케이션', '호텔 패키지']),
        ('투자유치', ['투자 유치', '시리즈', '펀딩', '투자금']),
        ('인수합병', ['인수', '합병', 'm&a', '매각']),
        ('ipo', ['ipo', '상장', '기업공개']),
        ('실적발표', ['실적', '매출', '영업이익', '분기']),
    ]

    for topic_name, keywords in topic_groups:
        for kw in keywords:
            if kw in text:
                return topic_name

    return None


def diversify_by_company(articles, max_per_company=1, silent=False):
    """
    같은 회사/주제 기사는 max_per_company개만 선정 (다양성 확보)
    점수가 높은 기사를 우선 선정
    """
    company_count = {}
    topic_count = {}
    diversified = []
    skipped = []

    for article in articles:
        company = get_main_company(article)
        topic = get_article_topic(article)

        # 회사 또는 주제 중 하나라도 이미 max 도달하면 스킵
        company_full = company and company_count.get(company, 0) >= max_per_company
        topic_full = topic and topic_count.get(topic, 0) >= max_per_company

        if company_full or topic_full:
            skipped.append(article)
        else:
            diversified.append(article)
            if company:
                company_count[company] = company_count.get(company, 0) + 1
            if topic:
                topic_count[topic] = topic_count.get(topic, 0) + 1

    if not silent and skipped:
        print(f"   -> 회사/주제별 다양성 적용: {len(skipped)}개 기사 후순위로 이동")

    # 스킵된 기사는 뒤에 추가 (혹시 필요할 경우 대비)
    return diversified + skipped


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

        # 인코딩 처리 개선: HTML 내 charset 선언 우선 확인
        encoding = None

        # 1. Content-Type 헤더에서 charset 확인
        content_type = response.headers.get('Content-Type', '').lower()
        if 'charset=' in content_type:
            charset_match = re.search(r'charset=([^\s;]+)', content_type)
            if charset_match:
                encoding = charset_match.group(1)

        # 2. HTML meta 태그에서 charset 확인 (가장 신뢰성 높음)
        if not encoding:
            html_head = response.content[:2000].decode('latin-1', errors='replace')
            charset_match = re.search(r'charset=["\']?([^"\'\s>]+)', html_head, re.I)
            if charset_match:
                encoding = charset_match.group(1)

        # 3. UTF-8 디코드 시도
        if not encoding:
            try:
                response.content.decode('utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                pass

        # 4. 최종 fallback
        if not encoding:
            encoding = response.apparent_encoding or 'utf-8'

        response.encoding = encoding
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
    parser.add_argument('--no-history', action='store_true', help='히스토리 체크 스킵 (테스트용)')
    parser.add_argument('--slack', action='store_true', help='Slack으로 초안 발송 (검토용)')
    parser.add_argument('--slack-final', action='store_true', help='Slack으로 최종본 발송 (클라이언트용)')
    parser.add_argument('--slack-webhook', type=str, help='Slack Webhook URL (없으면 SLACK_WEBHOOK_URL 환경변수 사용)')
    args = parser.parse_args()

    if not args.silent:
        print("=" * 80)
        print("ONDA 뉴스 스크래퍼 - B2B Hospitality Tech")
        print("=" * 80)
        print(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 0. 스크랩 히스토리 로드
    history = load_scrape_history()
    if not args.silent:
        print(f"[0단계] 스크랩 히스토리 로드... ({len(history['articles'])}개 기존 기사)")

    # 1. 뉴스 수집
    if not args.silent:
        print("[1단계] 뉴스 수집 중...")

    articles = collect_all_news(silent=args.silent)

    if not args.silent:
        print(f"   -> {len(articles)}개 기사 수집 완료")

    # 1.5 이미 스크랩한 기사 제외
    if not args.no_history:
        if not args.silent:
            print("[1.5단계] 이전 스크랩 기사 필터링 중...")
        before_filter = len(articles)
        articles = filter_already_scraped(articles, history, silent=args.silent)
        if not args.silent:
            filtered = before_filter - len(articles)
            print(f"   -> {filtered}개 이전 기사 제외 ({before_filter}개 -> {len(articles)}개)\n")
    else:
        if not args.silent:
            print("   -> 히스토리 체크 스킵\n")

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

    # 4.5 회사별 다양성 적용 (같은 회사 기사는 1개만 TOP에 선정)
    if not args.silent:
        print("[4단계] 회사별 다양성 적용 중...")
    articles_sorted = diversify_by_company(articles_sorted, max_per_company=1, silent=args.silent)
    if not args.silent:
        print()

    # 5. 상위 20개 선택
    top_articles = articles_sorted[:20]

    # 5.5 TOP 20 내 추가 중복 제거 + 주제 다양성 (더 엄격하게)
    if not args.silent:
        print("[5단계] TOP 20 내 중복/다양성 재검사 중...")

    final_top = []
    topic_in_top = {}  # 주제별 카운트

    for article in top_articles:
        is_dup = False
        for existing in final_top:
            # 더 엄격한 유사도 체크 (0.25)
            sim = calculate_similarity(article['title'], existing['title'])
            same = is_same_story(article, existing)
            if sim >= 0.25 or same:
                is_dup = True
                break

        # 같은 주제가 이미 있으면 스킵 (주제별 다양성)
        topic = get_article_topic(article)
        if topic and topic_in_top.get(topic, 0) >= 1:
            is_dup = True

        if not is_dup:
            final_top.append(article)
            if topic:
                topic_in_top[topic] = topic_in_top.get(topic, 0) + 1

    # 부족하면 다음 순위에서 채움
    if len(final_top) < 20:
        for article in articles_sorted[20:]:
            if len(final_top) >= 20:
                break
            is_dup = False
            for existing in final_top:
                sim = calculate_similarity(article['title'], existing['title'])
                same = is_same_story(article, existing)
                if sim >= 0.25 or same:
                    is_dup = True
                    break

            # 같은 주제가 이미 있으면 스킵
            topic = get_article_topic(article)
            if topic and topic_in_top.get(topic, 0) >= 1:
                is_dup = True

            if not is_dup:
                final_top.append(article)
                if topic:
                    topic_in_top[topic] = topic_in_top.get(topic, 0) + 1

    top_articles = final_top[:20]

    if not args.silent:
        print(f"   -> TOP 20 중복 제거 완료 (최종 {len(top_articles)}개)\n")

    # 5.6 실제 발행일 검증 (구글 뉴스 time_text 오류 방지)
    if not args.silent:
        print("[5.5단계] 실제 발행일 검증 중...")

    verified_articles = []
    removed_old = 0

    for article in top_articles:
        is_fresh, actual_date = verify_article_freshness(article, max_days=2)
        if is_fresh:
            verified_articles.append(article)
        else:
            removed_old += 1
            if not args.silent:
                print(f"   ⚠ 오래된 기사 제외: {actual_date} - {article['title'][:30]}...")

    # 제외된 만큼 다음 순위에서 보충
    if len(verified_articles) < 20 and removed_old > 0:
        for article in articles_sorted[20:]:
            if len(verified_articles) >= 20:
                break
            # 이미 포함되어 있는지 확인
            if any(a['title'] == article['title'] for a in verified_articles):
                continue
            is_fresh, actual_date = verify_article_freshness(article, max_days=2)
            if is_fresh:
                verified_articles.append(article)

    top_articles = verified_articles[:20]

    if not args.silent:
        print(f"   -> 발행일 검증 완료 ({removed_old}개 오래된 기사 제외)\n")

    # 6. AI 에디터로 TOP 3 선정 (Option A)
    if not args.silent:
        print("[4단계] AI 에디터 TOP 3 선정 중...")

    top3_articles = ai_editor_select_top3(top_articles, silent=args.silent)

    if not args.silent:
        ai_selected = sum(1 for a in top3_articles if a.get('ai_selected', False))
        print(f"   -> AI 선정 {ai_selected}개 완료")

    # 7. TOP 20 짧은 요약 생성 (60-100자) - 이모지 선택 시스템을 위해 전체 기사에 요약 필요
    if not args.silent:
        print("[5단계] TOP 20 기사 요약 생성 중...")

    for idx, article in enumerate(top_articles[:20], 1):
        if not args.silent:
            print(f"   [{idx}/20] {article['title'][:30]}... 요약 중")
        # AI 에디터가 이미 요약했으면 스킵, 아니면 생성
        if not article.get('ai_summary'):
            article['short_summary'] = generate_short_summary(article, max_chars=100)
        else:
            article['short_summary'] = article['ai_summary']

        # short_summary가 비어있으면 원본 summary 또는 제목 사용
        if not article.get('short_summary'):
            if article.get('summary'):
                article['short_summary'] = article['summary'][:100]
            else:
                article['short_summary'] = article['title'][:100]

        # 기존 호환성을 위해 detailed_summary도 설정
        article['detailed_summary'] = article['short_summary']

    if not args.silent:
        print(f"   -> TOP 20 요약 완료\n")

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
                print(f"   -> 이메일 전송 완료: {args.to}")

            # 히스토리에 TOP 10 기사 저장 (다음번 스크랩에서 제외)
            if not args.no_history:
                history = add_to_history(top_articles, history)
                save_scrape_history(history)
                if not args.silent:
                    print(f"   -> 히스토리에 {len(top_articles)}개 기사 저장 완료\n")
            else:
                print(f"SUCCESS: Email sent to {args.to}")
        else:
            print(f"FAILED: Email sending failed")

        return

    # 8. Slack 발송 - 워크플로우에서 직접 처리 (CLI 옵션 비활성화)
    if args.slack or args.slack_final:
        print("NOTE: Slack 발송은 GitHub Actions 워크플로우에서 직접 처리됩니다.")
        print("      onda-news-morning.yml / onda-news-final.yml 참조")
        return

    # 8. latest_news.json 저장 (GitHub Actions용)
    import json as json_module
    latest_news_data = {
        'top_3': top_articles[:3],
        'top_20': top_articles[:20],
        'scraped_at': datetime.now().isoformat()
    }
    with open('latest_news.json', 'w', encoding='utf-8') as f:
        json_module.dump(latest_news_data, f, ensure_ascii=False, indent=2)
    if not args.silent:
        print(f"   -> latest_news.json 저장 완료")

    # 9. 콘솔 출력
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
