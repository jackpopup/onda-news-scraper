"""
WeeklyON 뉴스레터 생성 서버

로컬 서버를 실행하면:
1. 링크만 입력하면 자동으로 기사 내용 추출
2. AI로 요약 생성 (호스피탈리티 트렌드: 500자, 키워드 뉴스: 한줄)

실행: python newsletter_server.py
브라우저에서: http://localhost:8000
"""

import http.server
import socketserver
import json
import re
import os
from urllib.parse import parse_qs, urlparse
import requests
from bs4 import BeautifulSoup


PORT = 8000


def fetch_article(url):
    """기사 URL에서 제목, 본문 추출"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        # 인코딩 처리
        encoding = None
        content_type = response.headers.get('Content-Type', '').lower()
        if 'charset=' in content_type:
            match = re.search(r'charset=([^\s;]+)', content_type)
            if match:
                encoding = match.group(1)

        if not encoding:
            html_head = response.content[:2000].decode('latin-1', errors='replace')
            match = re.search(r'charset=["\']?([^"\'\s>]+)', html_head, re.I)
            if match:
                encoding = match.group(1)

        if not encoding:
            try:
                response.content.decode('utf-8')
                encoding = 'utf-8'
            except:
                encoding = response.apparent_encoding or 'utf-8'

        response.encoding = encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        # 제목 추출
        title = ''
        title_selectors = [
            'meta[property="og:title"]',
            'meta[name="title"]',
            'h1.article-title',
            'h1.news-title',
            'h1',
            'title'
        ]
        for sel in title_selectors:
            elem = soup.select_one(sel)
            if elem:
                title = elem.get('content') if elem.name == 'meta' else elem.get_text(strip=True)
                if title:
                    break

        # 본문 추출
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'ad']):
            tag.decompose()

        content = ''
        content_selectors = [
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

        for sel in content_selectors:
            elem = soup.select_one(sel)
            if elem:
                content = elem.get_text(separator=' ', strip=True)
                break

        if not content or len(content) < 100:
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30])

        # 출처 추출
        source = ''
        source_selectors = [
            'meta[property="og:site_name"]',
            'meta[name="publisher"]',
        ]
        for sel in source_selectors:
            elem = soup.select_one(sel)
            if elem:
                source = elem.get('content', '')
                if source:
                    break

        if not source:
            # URL에서 추출
            domain = urlparse(url).netloc
            source = domain.replace('www.', '').split('.')[0]

        return {
            'success': True,
            'title': title[:200] if title else '',
            'content': content[:5000] if content else '',
            'source': source
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def summarize_article(content, title, summary_type='short'):
    """
    기사 요약 생성
    - short: 한줄요약 (50-80자) - 핵심 팩트만
    - long: 상세요약 (800-1000자) - 팩트 중심
    """
    openai_key = os.environ.get('OPENAI_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    if summary_type == 'long':
        prompt = f"""당신은 숙박업 전문 뉴스 에디터입니다. 다음 기사를 800-1000자로 팩트 중심 요약해주세요.

[필수 규칙]
1. 도입부의 장황한 설명, 배경 설명은 건너뛰고 핵심 팩트부터 시작
2. "무엇이 어떻게 됐다"는 팩트를 먼저, 그 다음 영향/의미 설명
3. 구체적인 숫자, 날짜, 금액, 퍼센트는 반드시 포함
4. 숙박업 사장님에게 실질적으로 도움되는 정보 위주
5. 불필요한 수식어, 감정적 표현 제거
6. 단락을 나눠서 가독성 있게 작성

[피해야 할 것]
- "최근", "요즘", "화제가 되고 있다" 같은 모호한 표현
- 기사 서두의 뻔한 배경 설명 복사
- "~라고 한다", "~인 것으로 알려졌다" 같은 간접 인용 남발

제목: {title}
기사 전문: {content[:4000]}

팩트 중심 요약 (800-1000자):"""
        max_tokens = 1200
    else:
        prompt = f"""당신은 숙박업 전문 뉴스 에디터입니다. 다음 기사의 가장 중요한 팩트 1개를 50-80자로 요약해주세요.

[필수 규칙]
1. 기사에서 가장 중요한 핵심 팩트 1개만 추출
2. "누가/무엇이 + 어떻게 됐다" 형식
3. 숫자가 있으면 반드시 포함 (금액, 퍼센트, 날짜 등)
4. 완결된 문장으로 끝내기

[피해야 할 것]
- 기사 첫 문장을 그대로 가져오기
- "~에 대해", "~관련" 같은 모호한 표현
- 배경 설명이나 도입부 내용

제목: {title}
기사 전문: {content[:2500]}

핵심 팩트 한줄 (50-80자):"""
        max_tokens = 150

    # OpenAI 시도
    if openai_key:
        try:
            import openai
            openai.api_key = openai_key

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3
            )
            summary = response.choices[0].message.content.strip()
            return summary.strip('"\'')
        except Exception as e:
            print(f"OpenAI error: {e}")

    # Anthropic 시도
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response.content[0].text.strip()
            return summary.strip('"\'')
        except Exception as e:
            print(f"Anthropic error: {e}")

    # API 없으면 본문에서 핵심 문장 추출 (첫 문장 제외)
    sentences = [s.strip() for s in re.split(r'[.!?]', content) if len(s.strip()) > 30]

    if summary_type == 'long':
        # 긴 요약: 2번째 문장부터 시작 (첫 문장은 대개 도입부)
        result = []
        for s in sentences[1:10]:  # 2~10번째 문장 사용
            result.append(s + '.')
            if len(' '.join(result)) > 800:
                break
        return ' '.join(result)[:1000] if result else title
    else:
        # 짧은 요약: 숫자가 포함된 문장 우선, 없으면 2번째 문장
        for s in sentences[1:5]:
            if any(c.isdigit() for c in s):  # 숫자 포함 문장 우선
                return s[:80] + ('.' if len(s) <= 80 else '...')
        # 숫자 없으면 2번째 문장 사용
        if len(sentences) > 1:
            return sentences[1][:80] + ('.' if len(sentences[1]) <= 80 else '...')
        return title[:80] if title else ''


class NewsletterHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/newsletter_input.html'
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/fetch-article':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            url = data.get('url', '')
            summary_type = data.get('summary_type', 'short')  # 'short' or 'long'

            if not url:
                self.send_json({'success': False, 'error': 'URL required'})
                return

            # 기사 가져오기
            result = fetch_article(url)

            if result['success']:
                # 요약 생성
                summary = summarize_article(
                    result['content'],
                    result['title'],
                    summary_type
                )
                result['summary'] = summary

            self.send_json(result)
            return

        self.send_error(404)

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    with socketserver.TCPServer(("", PORT), NewsletterHandler) as httpd:
        print("=" * 50)
        print("WeeklyON 뉴스레터 생성 서버")
        print("=" * 50)
        print(f"\n브라우저에서 열기: http://localhost:{PORT}\n")

        # API 키 확인
        if os.environ.get('OPENAI_API_KEY'):
            print("[OK] OpenAI API 연결됨")
        elif os.environ.get('ANTHROPIC_API_KEY'):
            print("[OK] Anthropic API 연결됨")
        else:
            print("[!] AI API 키 없음 - 기본 요약 사용")
            print("    (OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 환경변수 설정)")

        print("\n서버 실행 중... (Ctrl+C로 종료)")
        print("-" * 50)

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n서버 종료")


if __name__ == "__main__":
    main()
