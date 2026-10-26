"""Log into CTSV locally and export a browser session for a GitHub Action secret.

Keep .auth/ files secret: they can let other people use your signed-in session.
"""
import base64
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://ctsv.hust.edu.vn/dat-ve"
OUT_DIR = Path('.auth')


def main():
    OUT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(locale='vi-VN')
        page = context.new_page()
        page.goto(URL, wait_until='domcontentloaded', timeout=60000)
        print('1) Dang nhap CTSV trong cua so Chromium vua mo.')
        print('2) Mo trang Dat ve, doi danh sach su kien hien len.')
        input('3) Khi trang dat ve da hien va da dang nhap, nhan Enter tai day... ')
        if 'ctsv.hust.edu.vn' not in page.url:
            print('Canh bao: tab hien tai khong o ctsv.hust.edu.vn.')
            browser.close()
            return
        body = page.locator('body').inner_text(timeout=20000)
        if 'Đăng ký tham gia sự kiện' not in body and 'Sự kiện sắp tới' not in body:
            print('Chua tim thay trang su kien. Hay thu lai, khong xuat phien.')
            browser.close()
            return
        state = context.storage_state(indexed_db=True)
        session_data = page.evaluate('() => Object.fromEntries(Object.entries(sessionStorage))')
        payload = {'storage_state': state, 'session_storage': session_data}
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        output = base64.b64encode(raw).decode('ascii')
        (OUT_DIR / 'auth.b64').write_text(output, encoding='ascii')
        print('DA LUU: .auth/auth.b64')
        print('Khong chia se, khong commit file nay, khong gui noi dung vao chat.')
        print('Nhap Get-Content -Raw .auth\\auth.b64 | Set-Clipboard trong PowerShell de copy.')
        browser.close()


if __name__ == '__main__':
    main()
