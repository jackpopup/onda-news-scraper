# 빠른 시작 가이드 - 5분 안에 설정하기

## Step 1: Gmail 앱 비밀번호 생성 (2분)

1. https://myaccount.google.com/apppasswords 접속
2. "앱 비밀번호" 생성 (2단계 인증 필요)
3. 16자리 비밀번호 복사 (예: `abcd efgh ijkl mnop`)

## Step 2: 이메일 설정 파일 수정 (1분)

`email_config.py` 파일 열고 수정:

```python
GMAIL_EMAIL = "jack@popupstudio.ai"       # 본인 Gmail
GMAIL_PASSWORD = "abcd efgh ijkl mnop"     # 생성한 앱 비밀번호
```

## Step 3: 테스트 (1분)

```bash
cd c:\GitHub\AI-driven-work\scraping
python ai_startup_news.py --email --to jack@popupstudio.ai
```

이메일 받은편지함 확인!

## Step 4: 매일 오전 9시 자동 전송 설정 (1분)

**관리자 권한**으로 실행:

```bash
cd c:\GitHub\AI-driven-work\scraping
setup_scheduler.bat
```

안내에 따라 입력:
- 이메일: `jack@popupstudio.ai`
- 서비스: `1` (Gmail)

완료! 🎉

---

**문제가 있나요?** → [전체 가이드](README_EMAIL_SETUP.md) 확인
