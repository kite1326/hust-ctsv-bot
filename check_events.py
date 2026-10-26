"""Monitor changes on the logged-in CTSV ticket page.

This tool NEVER submits tickets or clicks booking buttons. It only compares
visible page content. It intentionally does not print or commit page content,
account details, browser cookies, or local storage.
"""
import base64
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = 'https://ctsv.hust.edu.vn/dat-ve'
STATE_FILE = Path('state/last.json')


def read_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def write_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def notify(topic, title, message, priority='4'):
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', topic):
        raise ValueError('NTFY_TOPIC phai la ten chu de dai, khong co khoang trang.')
    req = Request(
        f'https://ntfy.sh/{topic}',
        data=message.encode('utf-8'),
        method='POST',
        headers={
            'Title': title, # HTTP headers are ASCII; Vietnamese message body is UTF-8
            'Priority': priority,
            'Click': URL,
            'Content-Type': 'text/plain; charset=utf-8',
        },
    )
    with urlopen(req, timeout=20) as res:
        if not 200 <= res.status < 300:
            raise RuntimeError('ntfy HTTP error')


def clean_lines(text):
    return [re.sub(r'\s+', ' ', s).strip() for s in text.splitlines() if s.strip()]


def extract_event_region(page_text):
    """Use visible table heading, not fragile hashed CSS class names."""
    lines = clean_lines(page_text)
    # The image shows: SỰ KIỆN | THỜI GIAN & ĐỊA ĐIỂM | CHỖ | VÉ CỦA TÔI
    # Search heading after tab navigation, not the earlier 'Vé của tôi' tab.
    index = -1
    for i, line in enumerate(lines):
        if line.casefold() == 'thời gian & địa điểm':
            index = i
    if index < 0:
        raise ValueError('Khong tim thay tieu de bang su kien: giao dien co the da doi.')
    # Move past seat/ticket headings.
    start = index + 1
    for _ in range(3):
        if start < len(lines) and lines[start].casefold() in ('chỗ', 'vé của tôi'):
            start += 1
    relevant = lines[start:]
    # Some pages render a footer; do not include it in the fingerprint.
    footer_markers = ('liên hệ', 'bản quyền', 'copyright', '© ')
    for i, line in enumerate(relevant):
        if any(line.casefold().startswith(marker) for marker in footer_markers):
            relevant = relevant[:i]
            break
    if not relevant:
        # "No upcoming events" is fine if it is visibly stated.
        raise ValueError('Bang su kien rong hoac chua tai xong.')
    return '\n'.join(relevant)


def fetch_snapshot(auth_data):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=auth_data['storage_state'], locale='vi-VN')
        ss = auth_data.get('session_storage', {})
        if ss:
            # Playwright Python add_init_script accepts a script string, not
            # JavaScript arguments. Serialize the keys/values into the script.
            ss_json = json.dumps(ss, ensure_ascii=True)
            ctx.add_init_script(f'''(() => {{
              if (location.hostname === "ctsv.hust.edu.vn") {{
                const entries = {ss_json};
                for (const [k, v] of Object.entries(entries)) sessionStorage.setItem(k, v);
              }}
            }})()''')
        page = ctx.new_page()
        page.goto(URL, wait_until='domcontentloaded', timeout=60000)
        try:
            page.get_by_text('Đăng ký tham gia sự kiện', exact=False).first.wait_for(timeout=25000)
        except PlaywrightTimeoutError:
            pass
        # React loading may continue after DOMContentLoaded.
        for _ in range(8):
            body = page.locator('body').inner_text(timeout=20000)
            if ('thời gian & địa điểm' in body.casefold() or
                'THỜI GIAN & ĐỊA ĐIỂM' in body):
                break
            time.sleep(1)
        url_now = page.url
        browser.close()
    if 'ctsv.hust.edu.vn' not in url_now or ('Đăng ký tham gia sự kiện' not in body):
        raise PermissionError('Da het phien dang nhap, hoac CTSV chuyen den trang login.')
    return extract_event_region(body)


def main():
    topic = os.environ.get('NTFY_TOPIC', '').strip()
    auth_secret = os.environ.get('HUST_AUTH_B64', '').strip()
    if not topic or not auth_secret:
        print('Thieu GitHub Secrets HUST_AUTH_B64 / NTFY_TOPIC.', file=sys.stderr)
        sys.exit(1)
    state = read_state()
    try:
        data = json.loads(base64.b64decode(auth_secret, validate=True))
        content = fetch_snapshot(data)
    except Exception as ex:
        # Never log exception objects: network errors can accidentally contain sensitive URLs.
        kind = 'auth_or_page_error'
        if state.get('status') != kind:
            notify(topic, 'HUST: Kiem tra bot',
                   'Bot không đọc được danh sách vé. Có thể phiên đăng nhập đã hết hạn '
                   'hoặc website đã thay đổi. Hãy kiểm tra GitHub Actions và tạo lại secret nếu cần.')
            state['status'] = kind
            write_state(state)
        print('Khong the doc CTSV. Kiem tra dang nhap/giao dien. Loai loi:', type(ex).__name__)
        return

    fingerprint = hashlib.sha256(content.encode('utf-8')).hexdigest()
    old_hash = state.get('hash')
    if old_hash is None:
        print('Da luu moc dau tien (khong gui canh bao).')
    elif old_hash != fingerprint:
        notify(topic, 'HUST: Ve su kien thay doi',
               'Danh sách sự kiện CTSV hoặc số chỗ đã thay đổi! '
               'Mở ngay https://ctsv.hust.edu.vn/dat-ve để kiểm tra và đăng ký.')
        print('Phat hien thay doi va da gui ntfy.')
    else:
        print('Danh sach khong thay doi.')
    if old_hash != fingerprint or state.get('status') != 'ok':
        write_state({'hash': fingerprint, 'status': 'ok'})


if __name__ == '__main__':
    main()
