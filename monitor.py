import os
import time
import json
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

# بيانات التيليجرام الخاصة بك
TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

TARGETS = [
    {"code": "3104", "section": "2481"},
    {"code": "3101", "section": "2512"},
    {"code": "3201", "section": "2494"},
]

is_busy = False

# خادم وهمي خفيف لإبقاء Render مستقراً 24/7 دون إعادة تشغيل
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ فشل الإرسال: {e}")

def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?timeout=15"
        if offset:
            url += f"&offset={offset}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("result", [])
    except Exception:
        return []

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

def check_all_sections():
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        # 1. المقر والدرجة
        select_by_text(page, 0, "الخرج (طلاب)")
        select_by_text(page, 1, "بكالوريوس")

        # 2. الشجرة
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

            # إدخال رمز المادة
            page.evaluate(f'''() => {{
                const inputs = document.querySelectorAll("input[type='text']");
                if (inputs.length > 0) {{
                    inputs[0].value = "{code}";
                    inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}''')
            page.wait_for_timeout(1000)

            # الضغط على العدسة
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
                        const c = tds[0].innerText.trim();
                        const t = tds[1].innerText.trim();
                        const s = tds[2].innerText.trim();
                        const st = tds[6].innerText.trim();
                        if (s && /^\\d+$/.test(s)) {
                            list.push({ code: c, title: t, section: s, status: st });
                        }
                    }
                });
                return list;
            }''')

            found = False
            for r in rows_data:
                if r["section"] == sec:
                    found = True
                    icon = "🟢" if "مفتوحة" in r["status"] else "🔴"
                    report.append(f"{icon} *{r['title']}*\n• الرمز: {r['code']} | الشعبة: {r['section']}\n• الحالة: {r['status']}")
                    break

            if not found:
                report.append(f"⚠️ مادة {code} (شعبة {sec}) لم تظهر.")

        browser.close()

    return "\n\n".join(report)

def main():
    global is_busy
    # تشغيل خادم الويب الخلفي
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    print("🚀 البوت متصل ومستقر الآن...")
    send_telegram("🤖 البوت متصل الآن ومستقر!\n\nأرسل /check لفحص الشعب.")

    # مسح الرسائل القديمة المكدسة لتفادي الرد المتكرر
    initial_updates = get_updates()
    last_update_id = initial_updates[-1]["update_id"] + 1 if initial_updates else None

    while True:
        updates = get_updates(last_update_id)
        for update in updates:
            last_update_id = update["update_id"] + 1
            message = update.get("message", {})
            sender_id = str(message.get("from", {}).get("id", ""))
            text = message.get("text", "")

            if sender_id == TELEGRAM_CHAT_ID:
                if is_busy:
                    send_telegram("⏳ يوجد فحص جاري الآن، يرجى الانتظار بضع ثوانٍ...")
                    continue

                is_busy = True
                send_telegram("⏳ جاري فحص الشعب الآن من بوابة الجامعة...")
                try:
                    result = check_all_sections()
                    send_telegram(f"📊 تقرير حالة الشعب:\n\n{result}")
                except Exception as e:
                    send_telegram(f"⚠️ حدث خطأ أثناء الفحص: {e}")
                finally:
                    is_busy = False

        time.sleep(2)

if __name__ == "__main__":
    main()
