"""
이메일 전송 모듈
뉴스 수집 결과를 이메일로 전송
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def create_html_email(articles):
    """
    뉴스 기사들을 HTML 이메일 형식으로 변환
    """
    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
            }}
            .header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
            }}
            .article {{
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 5px;
            }}
            .article-rank {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .article-title {{
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
                margin: 10px 0;
            }}
            .article-summary {{
                color: #555;
                margin: 15px 0;
                padding: 10px;
                background: white;
                border-radius: 5px;
            }}
            .article-link {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 10px;
            }}
            .article-link:hover {{
                background: #764ba2;
            }}
            .score {{
                color: #667eea;
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 5px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 AI & 스타트업 뉴스 TOP 10</h1>
            <p>POPUP STUDIO - {datetime.now().strftime('%Y년 %m월 %d일')}</p>
        </div>
    """

    for idx, article in enumerate(articles, 1):
        summary = article['summary'].strip()
        if len(summary) > 150:
            summary = summary[:150] + "..."

        html += f"""
        <div class="article">
            <span class="article-rank">{idx}위</span>
            <span class="score">중요도: {article['score']}점</span>
            <div class="article-title">{article['title']}</div>
            <div class="article-summary">{summary if summary else '(요약 없음)'}</div>
            <a href="{article['link']}" class="article-link">기사 읽기 →</a>
        </div>
        """

    html += """
        <div class="footer">
            <p>이 이메일은 AI 뉴스 수집 시스템에서 자동으로 발송되었습니다.</p>
            <p>POPUP STUDIO © 2025</p>
        </div>
    </body>
    </html>
    """

    return html

def send_email_gmail(to_email, subject, html_content):
    """
    Gmail SMTP를 통해 이메일 전송

    참고: Gmail 앱 비밀번호 필요
    1. Google 계정 → 보안 → 2단계 인증 활성화
    2. 앱 비밀번호 생성
    """
    try:
        from email_config import GMAIL_EMAIL, GMAIL_PASSWORD
    except ImportError:
        print("오류: email_config.py 파일이 없거나 설정이 누락되었습니다.")
        print("email_config.py 파일에 Gmail 계정 정보를 입력해주세요.")
        return False

    # Gmail 설정
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = GMAIL_EMAIL
    sender_password = GMAIL_PASSWORD

    # 이메일 구성
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"POPUP STUDIO News <{sender_email}>"
    message["To"] = to_email

    # HTML 본문 추가
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    try:
        # SMTP 서버 연결 및 전송
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # TLS 암호화
            server.login(sender_email, sender_password)
            server.send_message(message)

        print(f"[SUCCESS] 이메일 전송 성공: {to_email}")
        return True
    except Exception as e:
        print(f"[FAILED] 이메일 전송 실패: {e}")
        return False

def send_email_outlook(to_email, subject, html_content):
    """
    Outlook/Office365 SMTP를 통해 이메일 전송
    """
    try:
        from email_config import OUTLOOK_EMAIL, OUTLOOK_PASSWORD
    except ImportError:
        print("오류: email_config.py 파일이 없거나 설정이 누락되었습니다.")
        print("email_config.py 파일에 Outlook 계정 정보를 입력해주세요.")
        return False

    smtp_server = "smtp.office365.com"
    smtp_port = 587
    sender_email = OUTLOOK_EMAIL
    sender_password = OUTLOOK_PASSWORD

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"POPUP STUDIO News <{sender_email}>"
    message["To"] = to_email

    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)

        print(f"[SUCCESS] 이메일 전송 성공: {to_email}")
        return True
    except Exception as e:
        print(f"[FAILED] 이메일 전송 실패: {e}")
        return False
