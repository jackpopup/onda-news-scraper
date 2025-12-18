"""
AI 및 유니콘 스타트업 관련 뉴스 수집기
POPUP STUDIO 팀을 위한 맞춤 뉴스
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import argparse
from email_sender import create_html_email, send_email_gmail, send_email_outlook

def get_naver_it_news():
    """네이버 IT 뉴스에서 기사 수집"""
    url = "https://news.naver.com/section/105"
    headers = {'User-Agent': 'Mozilla/5.0'}

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    # 모든 기사 찾기
    articles = []
    article_elements = soup.find_all('div', class_='sa_text')

    for article in article_elements[:30]:  # 최대 30개 수집
        try:
            # 제목
            title_elem = article.find('strong', class_='sa_text_strong')
            if not title_elem:
                continue
            title = title_elem.text.strip()

            # 링크
            link_elem = article.find('a')
            link = link_elem['href'] if link_elem else ""

            # 요약
            summary_elem = article.find('div', class_='sa_text_lede')
            summary = summary_elem.text.strip() if summary_elem else ""

            articles.append({
                'title': title,
                'link': link,
                'summary': summary,
                'source': '네이버 IT'
            })
        except Exception as e:
            continue

    return articles

def calculate_similarity(title1, title2):
    """
    두 제목의 유사도를 계산 (0~1 사이 값)
    단어 기반 간단한 유사도 계산
    """
    # 제목을 단어로 분리
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())

    # 공통 단어 개수
    common_words = words1.intersection(words2)

    # 전체 단어 개수
    total_words = words1.union(words2)

    if len(total_words) == 0:
        return 0

    # 유사도 = 공통 단어 / 전체 단어
    similarity = len(common_words) / len(total_words)

    return similarity

def remove_duplicates(articles, similarity_threshold=0.6):
    """
    중복 기사 제거
    제목이 60% 이상 유사하면 중복으로 간주
    """
    unique_articles = []

    for article in articles:
        is_duplicate = False

        # 이미 추가된 기사들과 비교
        for unique_article in unique_articles:
            similarity = calculate_similarity(article['title'], unique_article['title'])

            # 유사도가 임계값 이상이면 중복
            if similarity >= similarity_threshold:
                is_duplicate = True
                # 점수가 더 높은 것을 유지
                if article['score'] > unique_article['score']:
                    unique_articles.remove(unique_article)
                    unique_articles.append(article)
                break

        if not is_duplicate:
            unique_articles.append(article)

    return unique_articles

def calculate_relevance_score(article):
    """
    회사 관심도에 따라 점수 계산
    AI, 스타트업, 유니콘, 투자 등 키워드 기반
    """
    text = (article['title'] + ' ' + article['summary']).lower()

    score = 0

    # 고관심 키워드 (각 10점)
    high_priority = ['ai', '인공지능', 'gpt', 'claude', '생성형', 'llm',
                     '유니콘', '스타트업', '벤처', '투자유치']
    for keyword in high_priority:
        if keyword in text:
            score += 10

    # 중관심 키워드 (각 5점)
    medium_priority = ['스타트업', '창업', '펀딩', '시리즈', 'vc',
                       '테크', '플랫폼', '서비스', 'saas']
    for keyword in medium_priority:
        if keyword in text:
            score += 5

    # 저관심 키워드 (각 2점)
    low_priority = ['기업', '비즈니스', '시장', '산업', '혁신']
    for keyword in low_priority:
        if keyword in text:
            score += 2

    return score

def main():
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='AI 및 유니콘 스타트업 뉴스 수집기')
    parser.add_argument('--email', action='store_true', help='이메일로 결과 전송')
    parser.add_argument('--email-service', choices=['gmail', 'outlook'], default='gmail',
                        help='이메일 서비스 선택 (gmail 또는 outlook)')
    parser.add_argument('--to', type=str, help='받는 사람 이메일 주소')
    parser.add_argument('--silent', action='store_true', help='콘솔 출력 최소화 (자동 실행용)')
    args = parser.parse_args()

    if not args.silent:
        print("=" * 80)
        print("AI & 유니콘 스타트업 뉴스 수집기 - POPUP STUDIO")
        print("=" * 80)
        print(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. 기사 수집
    if not args.silent:
        print("[1단계] 네이버 IT 뉴스 수집 중...")
    articles = get_naver_it_news()
    if not args.silent:
        print(f"   -> {len(articles)}개 기사 수집 완료\n")

    # 2. 관심도 점수 계산
    if not args.silent:
        print("[2단계] 관심도 분석 중...")
    for article in articles:
        article['score'] = calculate_relevance_score(article)
    if not args.silent:
        print(f"   -> 점수 계산 완료\n")

    # 3. 중복 기사 제거
    if not args.silent:
        print("[3단계] 중복 기사 제거 중...")
    before_count = len(articles)
    articles_unique = remove_duplicates(articles, similarity_threshold=0.6)
    removed_count = before_count - len(articles_unique)
    if not args.silent:
        print(f"   -> {removed_count}개의 중복 기사 제거 ({before_count}개 -> {len(articles_unique)}개)\n")

    # 4. 점수 순으로 정렬
    articles_sorted = sorted(articles_unique, key=lambda x: x['score'], reverse=True)

    # 5. 상위 10개만 선택
    top_articles = articles_sorted[:10]
    if not args.silent:
        print(f"   -> 상위 10개 선발 완료\n")

    # 6. 이메일 전송 (옵션)
    if args.email:
        if not args.to:
            print("오류: --to 옵션으로 받는 사람 이메일을 지정해주세요.")
            return

        if not args.silent:
            print("[4단계] 이메일 전송 중...")

        subject = f"AI & 스타트업 뉴스 TOP 10 - {datetime.now().strftime('%Y년 %m월 %d일')}"
        html_content = create_html_email(top_articles)

        if args.email_service == 'gmail':
            success = send_email_gmail(args.to, subject, html_content)
        else:
            success = send_email_outlook(args.to, subject, html_content)

        if success and not args.silent:
            print(f"   -> 이메일 전송 완료: {args.to}\n")
        elif not success:
            print(f"   -> 이메일 전송 실패\n")

        if args.silent:
            # 자동 실행 모드에서는 성공/실패만 출력
            if success:
                print(f"SUCCESS: Email sent to {args.to}")
            else:
                print(f"FAILED: Email sending failed")
        return

    # 7. 결과 출력 (보기 좋게!)
    print("=" * 80)
    print("TOP 10 - 우리 회사가 주목해야 할 뉴스")
    print("=" * 80)

    for idx, article in enumerate(top_articles, 1):
        print(f"\n[{idx}위] 중요도: {article['score']}점")
        print("-" * 80)
        print(f"제목: {article['title']}")
        print()

        # 요약을 2줄 정도로 정리
        summary = article['summary'].strip()
        if summary:
            # 요약이 너무 길면 150자로 제한
            if len(summary) > 150:
                summary = summary[:150] + "..."
            print(f"요약:")
            print(f"  {summary}")
        else:
            print(f"요약: (요약 없음)")

        print()
        print(f"링크: {article['link']}")
        print("=" * 80)

    print("\n완료! 위 기사들을 팀과 공유하세요.")

    # 8. 파일로 저장 (옵션)
    save_to_file = input("\n결과를 파일로 저장하시겠습니까? (y/n): ")
    if save_to_file.lower() == 'y':
        filename = f"ai_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("AI & 유니콘 스타트업 뉴스 TOP 10 - POPUP STUDIO\n")
            f.write("=" * 80 + "\n")
            f.write(f"수집 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for idx, article in enumerate(top_articles, 1):
                f.write(f"[{idx}위] 중요도: {article['score']}점\n")
                f.write("-" * 80 + "\n")
                f.write(f"제목: {article['title']}\n\n")

                summary = article['summary'].strip()
                if summary:
                    if len(summary) > 150:
                        summary = summary[:150] + "..."
                    f.write(f"요약:\n")
                    f.write(f"  {summary}\n")
                else:
                    f.write(f"요약: (요약 없음)\n")

                f.write(f"\n링크: {article['link']}\n")
                f.write("=" * 80 + "\n\n")

        print(f"\n파일 저장 완료: {filename}")

if __name__ == "__main__":
    main()
