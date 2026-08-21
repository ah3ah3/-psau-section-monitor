import time
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

TARGETS = [
    {"code": "3104", "section": "2481"},
    {"code": "3101", "section": "2512"},
    {"code": "3201", "section": "2494"},
]

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ فشل الإرسال: {e}")

def select_by_text(page, select_index, text_match):
    page.evaluate(f'''() => {{
        const selects = document.querySelectorAll('select');
        const select = selects[{select_index}];
        if (select) {{
            for (let opt of select.options) {{
                if (opt.text.includes("{text_match}")) {{
                    select.value = opt.value;
                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    break;
                }}
            }}
        }}
    }}''')
    page.wait_for_timeout(2000)

def main():
    print("🚀 بدء الفحص المجدول التلقائي...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        select_by_text(page, 0, "الخرج (طلاب)")
        select_by_text(page, 1, "بكالوريوس")

        page.locator("text=المقررات المطروحة").last.click()
        page.wait_for_timeout(2000)
        page.locator("text=التمريض بالخرج").first.click()
        page.wait_for_timeout(2000)
        page.locator("text=علوم التمريض").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3500)

        for item in TARGETS:
            code = item["code"]
            sec = item["section"]

            page.evaluate(f'''() => {{
                const inputs = document.querySelectorAll("input[type='text']");
                if (inputs.length > 0) {{
                    inputs[0].value = "{code}";
                    inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}''')
            page.wait_for_timeout(1000)

            page.evaluate('''() => {
                const imgs = Array.from(document.querySelectorAll("img, input[type='image'], a"));
                for (let el of imgs) {
                    if ((el.src && (el.src.includes('search') || el.src.includes('find') || el.src.includes('lens'))) || 
                        (el.onclick && el.onclick.toString().includes('search')) ||
                        (el.getAttribute('onclick') && el.getAttribute('onclick').includes('search'))) {
                        el.click();
                        return;
                    }
                }
                const firstImg = document.querySelector("input[type='text'] ~ img, tr img");
                if (firstImg) firstImg.click();
            }''')

            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3500)

            rows_data = page.evaluate('''() => {
                const list = [];
                const trs = document.querySelectorAll("tr");
                trs.forEach(tr => {
                    const tds = Array.from(tr.children).filter(c => c.tagName.toLowerCase() === 'td');
                    if (tds.length >= 7 && !tr.querySelector('table')) {
                        list.push({
                            code: tds[0].innerText.trim(),
                            title: tds[1].innerText.trim(),
                            section: tds[2].innerText.trim(),
                            status: tds[6].innerText.trim()
                        });
                    }
                });
                return list;
            }''')

            for r in rows_data:
                if r["section"] == sec and "مفتوحة" in r["status"]:
                    msg = f"🚨 تنبيه: شعبة مفتوحة الآن!\n\n📚 المادة: {r['title']}\n🏷️ الرمز: {r['code']}\n🔢 الشعبة: {r['section']}\n🟢 الحالة: مفتوحة\n\nادخل على البوابة وسجل فوراً!"
                    send_telegram(msg)
                    break

        browser.close()

if __name__ == "__main__":
    main()
