# AI 뉴스 수집기 - 이메일 자동 전송 설정 가이드

## 목차
1. [이메일 설정](#1-이메일-설정)
2. [수동 테스트](#2-수동-테스트)
3. [자동 스케줄링 설정](#3-자동-스케줄링-설정)
4. [문제 해결](#4-문제-해결)

---

## 1. 이메일 설정

### Gmail 사용 (추천)

#### 1.1 Gmail 앱 비밀번호 생성

1. Google 계정 보안 페이지 접속
   - https://myaccount.google.com/security

2. 2단계 인증 활성화
   - "2단계 인증" 클릭
   - 안내에 따라 2단계 인증 설정

3. 앱 비밀번호 생성
   - https://myaccount.google.com/apppasswords 접속
   - 앱 선택: "메일"
   - 기기 선택: "Windows 컴퓨터"
   - "생성" 클릭
   - **16자리 비밀번호 복사** (예: `abcd efgh ijkl mnop`)

#### 1.2 email_config.py 파일 수정

`c:\GitHub\AI-driven-work\scraping\email_config.py` 파일을 열어서 다음을 수정:

```python
# Gmail 설정
GMAIL_EMAIL = "jack@popupstudio.ai"  # 본인의 Gmail 주소
GMAIL_PASSWORD = "abcd efgh ijkl mnop"  # 생성한 앱 비밀번호 (공백 포함 가능)
```

---

### Outlook 사용 (대안)

#### 1.1 email_config.py 파일 수정

```python
# Outlook 설정
OUTLOOK_EMAIL = "jack@popupstudio.ai"
OUTLOOK_PASSWORD = "본인의_Outlook_비밀번호"
```

**참고**: Outlook은 일반 계정 비밀번호를 사용합니다 (앱 비밀번호 불필요).

---

## 2. 수동 테스트

이메일 설정이 제대로 되었는지 확인하기 위해 수동으로 테스트합니다.

### 2.1 Gmail로 테스트

```bash
cd c:\GitHub\AI-driven-work\scraping
python ai_startup_news.py --email --email-service gmail --to jack@popupstudio.ai
```

### 2.2 Outlook으로 테스트

```bash
cd c:\GitHub\AI-driven-work\scraping
python ai_startup_news.py --email --email-service outlook --to jack@popupstudio.ai
```

### 2.3 결과 확인

- 성공: "이메일 전송 완료: jack@popupstudio.ai" 메시지 표시
- 실패: 오류 메시지 확인 (아래 [문제 해결](#4-문제-해결) 참고)

이메일 받은편지함에서 다음을 확인:
- 제목: "AI & 스타트업 뉴스 TOP 10 - 2025년 12월 18일"
- 보낸사람: "POPUP STUDIO News <본인이메일>"
- 내용: 상위 10개 뉴스가 예쁘게 포맷된 HTML 이메일

---

## 3. 자동 스케줄링 설정

매일 오전 9시에 자동으로 이메일을 받으려면 Windows 작업 스케줄러를 사용합니다.

### 방법 1: 배치 파일 사용 (간편)

1. **관리자 권한**으로 Git Bash 또는 명령 프롬프트 실행
2. 다음 명령어 실행:
   ```bash
   cd c:\GitHub\AI-driven-work\scraping
   setup_scheduler.bat
   ```
3. 안내에 따라 입력:
   - 받는 사람 이메일: `jack@popupstudio.ai`
   - 이메일 서비스: `1` (Gmail) 또는 `2` (Outlook)

### 방법 2: 수동 설정

1. 작업 스케줄러 열기
   - Windows 검색에서 "작업 스케줄러" 입력

2. 새 작업 만들기
   - 왼쪽 패널: "작업 스케줄러 라이브러리" 우클릭
   - "기본 작업 만들기" 클릭

3. 작업 설정
   - 이름: `PopupStudio_DailyNews`
   - 설명: `매일 오전 9시 AI 뉴스 이메일 전송`
   - 트리거: "매일", 시작 시간: `09:00`
   - 동작: "프로그램 시작"
   - 프로그램: `python`
   - 인수: `"c:\GitHub\AI-driven-work\scraping\ai_startup_news.py" --email --email-service gmail --to jack@popupstudio.ai --silent`
   - 시작 위치: `c:\GitHub\AI-driven-work\scraping`

4. 저장 및 확인
   - "마침" 클릭
   - 작업 스케줄러 라이브러리에서 `PopupStudio_DailyNews` 확인

### 스케줄러 작업 관리

#### 작업 실행 테스트
```bash
schtasks /run /tn "PopupStudio_DailyNews"
```

#### 작업 확인
```bash
schtasks /query /tn "PopupStudio_DailyNews" /v /fo list
```

#### 작업 삭제
```bash
schtasks /delete /tn "PopupStudio_DailyNews" /f
```

---

## 4. 문제 해결

### 문제 1: "이메일 전송 실패" 오류

**원인**: SMTP 인증 실패

**해결방법**:
1. `email_config.py`에 올바른 이메일과 비밀번호 입력했는지 확인
2. Gmail 사용자:
   - 2단계 인증이 활성화되어 있는지 확인
   - 앱 비밀번호를 올바르게 복사했는지 확인 (공백 포함 가능)
   - 일반 비밀번호가 아닌 **앱 비밀번호** 사용
3. Outlook 사용자:
   - 계정 비밀번호가 정확한지 확인

### 문제 2: "SMTPAuthenticationError: 535-5.7.8 Username and Password not accepted"

**원인**: Gmail에서 일반 비밀번호 사용

**해결방법**:
- Gmail 앱 비밀번호를 생성하고 사용 ([1.1 참고](#11-gmail-앱-비밀번호-생성))

### 문제 3: "ModuleNotFoundError: No module named 'email_config'"

**원인**: `email_config.py` 파일이 없거나 경로가 잘못됨

**해결방법**:
```bash
cd c:\GitHub\AI-driven-work\scraping
ls email_config.py  # 파일 존재 확인
```

### 문제 4: 스케줄러 작업이 실행되지 않음

**원인**: Python 경로가 잘못되었거나 권한 문제

**해결방법**:
1. Python 경로 확인:
   ```bash
   where python
   ```
2. 작업 스케줄러에서 작업 수정:
   - 프로그램을 절대 경로로 변경 (예: `C:\Users\zephi\AppData\Local\Programs\Python\Python311\python.exe`)
3. "가장 높은 수준의 권한으로 실행" 체크

### 문제 5: 이메일이 스팸함으로 감

**해결방법**:
1. 이메일을 받은편지함으로 이동
2. "스팸 아님" 표시
3. 발신자를 연락처에 추가

---

## 5. 명령줄 옵션

### 기본 사용 (콘솔 출력만)
```bash
python ai_startup_news.py
```

### 이메일 전송
```bash
python ai_startup_news.py --email --to jack@popupstudio.ai
```

### Gmail 사용
```bash
python ai_startup_news.py --email --email-service gmail --to jack@popupstudio.ai
```

### Outlook 사용
```bash
python ai_startup_news.py --email --email-service outlook --to jack@popupstudio.ai
```

### 자동 실행 모드 (출력 최소화)
```bash
python ai_startup_news.py --email --email-service gmail --to jack@popupstudio.ai --silent
```

---

## 6. 파일 구조

```
scraping/
├── ai_startup_news.py          # 메인 스크립트
├── email_sender.py              # 이메일 전송 모듈
├── email_config.py              # 이메일 계정 설정 (수정 필요)
├── setup_scheduler.bat          # 스케줄러 자동 설정 스크립트
├── README_EMAIL_SETUP.md        # 이 파일
└── naver_news_simple.py         # 간단한 예제
```

---

## 7. 다음 단계

1. ✅ 이메일 설정 완료 ([1단계](#1-이메일-설정))
2. ✅ 수동 테스트 성공 ([2단계](#2-수동-테스트))
3. ✅ 자동 스케줄러 설정 ([3단계](#3-자동-스케줄링-설정))
4. 🎉 매일 오전 9시에 자동으로 뉴스 수신!

---

**문의사항이 있으면 jack@popupstudio.ai로 연락주세요.**
