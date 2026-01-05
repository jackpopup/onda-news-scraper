"""
이메일 전송 모듈
뉴스 수집 결과를 이메일로 전송
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

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
            <p>POPUP STUDIO - {datetime.now(timezone(timedelta(hours=9))).strftime('%Y년 %m월 %d일')}</p>
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

def create_onda_html_email(articles):
    """
    ONDA 뉴스 브리핑용 HTML 이메일 생성
    TOP 3는 상세하게, 4~10위는 카드 형식, 11~20위는 테이블 형식
    """
    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .header {{
                background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%);
                color: white;
                padding: 25px;
                border-radius: 10px;
                margin-bottom: 25px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .header p {{
                margin: 8px 0 0 0;
                opacity: 0.9;
                font-size: 13px;
            }}
            .section-title {{
                background: #1a237e;
                color: white;
                padding: 8px 16px;
                border-radius: 5px;
                margin: 20px 0 12px 0;
                font-size: 14px;
                font-weight: bold;
            }}
            .top-article {{
                background: white;
                border-left: 5px solid #ff6f00;
                padding: 16px;
                margin-bottom: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            }}
            .rank {{
                display: inline-block;
                background: #ff6f00;
                color: white;
                padding: 2px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            .category {{
                display: inline-block;
                background: #e3f2fd;
                color: #1a237e;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                margin-left: 8px;
            }}
            .title {{
                font-size: 16px;
                font-weight: bold;
                color: #1a237e;
                margin: 10px 0 6px 0;
                line-height: 1.4;
            }}
            .summary {{
                color: #555;
                margin: 10px 0;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 5px;
                font-size: 13px;
                line-height: 1.6;
            }}
            .meta {{
                color: #888;
                font-size: 11px;
                margin-top: 8px;
            }}
            .link {{
                display: inline-block;
                background: #1a237e;
                color: white;
                padding: 6px 14px;
                text-decoration: none;
                border-radius: 4px;
                font-size: 12px;
                margin-top: 8px;
            }}
            /* 4~10위: 테이블 기반 2열 그리드 (이메일 호환) */
            .grid-table {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 8px;
            }}
            .grid-cell {{
                width: 50%;
                background: white;
                border-left: 3px solid #1a237e;
                padding: 12px;
                border-radius: 5px;
                vertical-align: top;
            }}
            .grid-rank {{
                display: inline-block;
                background: #1a237e;
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }}
            .grid-title {{
                font-size: 13px;
                font-weight: bold;
                color: #333;
                margin: 8px 0 4px 0;
                line-height: 1.4;
            }}
            .grid-title a {{
                color: #1a237e;
                text-decoration: none;
            }}
            .grid-meta {{
                color: #888;
                font-size: 10px;
            }}
            /* 11~20위: 테이블 형식 */
            .news-table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 5px;
                overflow: hidden;
                font-size: 12px;
            }}
            .news-table th {{
                background: #e8eaf6;
                color: #1a237e;
                padding: 8px 10px;
                text-align: left;
                font-weight: bold;
                font-size: 11px;
            }}
            .news-table td {{
                padding: 8px 10px;
                border-bottom: 1px solid #eee;
                vertical-align: middle;
            }}
            .news-table tr:last-child td {{
                border-bottom: none;
            }}
            .news-table tr:hover {{
                background: #f8f9fa;
            }}
            .table-rank {{
                background: #e8eaf6;
                color: #1a237e;
                padding: 2px 6px;
                border-radius: 8px;
                font-size: 10px;
                font-weight: bold;
                white-space: nowrap;
            }}
            .table-title {{
                color: #333;
                font-weight: 500;
            }}
            .table-title a {{
                color: #1a237e;
                text-decoration: none;
            }}
            .table-source {{
                color: #888;
                font-size: 10px;
                white-space: nowrap;
            }}
            .footer {{
                text-align: center;
                margin-top: 25px;
                padding: 15px;
                background: white;
                border-radius: 5px;
                color: #666;
                font-size: 11px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>ONDA 뉴스 브리핑</h1>
            <p>B2B Hospitality Tech | {datetime.now(timezone(timedelta(hours=9))).strftime('%Y년 %m월 %d일')} | TOP 20</p>
        </div>

        <div class="section-title">TOP 3 주요 뉴스</div>
    """

    # TOP 3 상세 출력
    for idx, article in enumerate(articles[:3], 1):
        summary = article.get('detailed_summary', article.get('summary', ''))
        if len(summary) > 180:
            summary = summary[:177] + "..."

        html += f"""
        <div class="top-article">
            <span class="rank">{idx}위</span>
            <span class="category">{article.get('category', '기타')}</span>
            <div class="title">{article['title']}</div>
            <div class="summary">{summary if summary else '(요약 없음)'}</div>
            <div class="meta">출처: {article.get('source', '알 수 없음')} | 점수: {article.get('score', 0)}점</div>
            <a href="{article['link']}" class="link">기사 읽기 →</a>
        </div>
        """

    # 4~10위: 테이블 기반 2열 그리드 (이메일 호환)
    if len(articles) > 3:
        html += '<div class="section-title">4~10위 뉴스</div>'
        html += '<table class="grid-table"><tbody>'

        articles_4_10 = list(enumerate(articles[3:10], 4))
        for i in range(0, len(articles_4_10), 2):
            html += '<tr>'
            # 첫 번째 셀
            idx, article = articles_4_10[i]
            title = article['title']
            if len(title) > 45:
                title = title[:42] + "..."
            html += f'''
                <td class="grid-cell">
                    <span class="grid-rank">{idx}위</span>
                    <span class="category">{article.get('category', '기타')}</span>
                    <div class="grid-title"><a href="{article['link']}">{title}</a></div>
                    <div class="grid-meta">{article.get('source', '알 수 없음')} | {article.get('score', 0)}점</div>
                </td>
            '''
            # 두 번째 셀 (있으면)
            if i + 1 < len(articles_4_10):
                idx2, article2 = articles_4_10[i + 1]
                title2 = article2['title']
                if len(title2) > 45:
                    title2 = title2[:42] + "..."
                html += f'''
                    <td class="grid-cell">
                        <span class="grid-rank">{idx2}위</span>
                        <span class="category">{article2.get('category', '기타')}</span>
                        <div class="grid-title"><a href="{article2['link']}">{title2}</a></div>
                        <div class="grid-meta">{article2.get('source', '알 수 없음')} | {article2.get('score', 0)}점</div>
                    </td>
                '''
            else:
                html += '<td class="grid-cell" style="background:transparent;border:none;"></td>'
            html += '</tr>'

        html += '</tbody></table>'

    # 11~20위: 테이블 형식
    if len(articles) > 10:
        html += '<div class="section-title">11~20위 뉴스</div>'
        html += '''
        <table class="news-table">
            <tr>
                <th style="width:40px;">순위</th>
                <th>제목</th>
                <th style="width:70px;">출처</th>
                <th style="width:50px;">점수</th>
            </tr>
        '''

        for idx, article in enumerate(articles[10:20], 11):
            title = article['title']
            if len(title) > 45:
                title = title[:42] + "..."
            source = article.get('source', '알 수 없음')
            if len(source) > 8:
                source = source[:7] + ".."
            html += f"""
            <tr>
                <td><span class="table-rank">{idx}위</span></td>
                <td class="table-title"><a href="{article['link']}">{title}</a></td>
                <td class="table-source">{source}</td>
                <td class="table-source">{article.get('score', 0)}점</td>
            </tr>
            """

        html += '</table>'

    html += """
        <div class="footer">
            <p>이 이메일은 ONDA 뉴스 수집 시스템에서 자동으로 발송되었습니다.</p>
            <p>Powered by AI News Scraper</p>
        </div>
    </body>
    </html>
    """

    return html


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
