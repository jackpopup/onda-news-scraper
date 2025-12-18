"""
네이버 뉴스 IT 섹션에서 최신 기사 제목 1개 가져오기
- 초보자를 위한 간단한 버전
"""

import requests
from bs4 import BeautifulSoup

# 1. 네이버 뉴스 IT 섹션 URL
url = "https://news.naver.com/section/105"

print("[네이버 뉴스] IT 섹션에서 기사를 가져오는 중...")

# 2. 웹페이지 다운로드
response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})

# 3. HTML 파싱 (분석)
soup = BeautifulSoup(response.text, 'html.parser')

# 4. 기사 제목 찾기
# 네이버 뉴스는 'sa_text_strong' 클래스에 제목이 있습니다
article_title = soup.find('strong', class_='sa_text_strong')

# 5. 결과 출력
if article_title:
    print("\n[성공] 첫 번째 기사 제목:")
    print(f"   {article_title.text}")
else:
    print("\n[실패] 기사를 찾지 못했습니다.")

print("\n완료!")
