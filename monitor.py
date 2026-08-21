import time
import json
import urllib.request
import urllib.parse
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

def send_telegram(message):
    """إرسال رسالة إلى التيليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ خطأ بالإرسال: {e}")

def get_updates(offset=None):
    """قراءة الرسائل الواردة للبوت"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?timeout=20"
        if offset:
            url += f"&offset={offset}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=25) as response:
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
    """تشغيل الفحص وجلب تقرير كامل لجميع الشعب"""
    report = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        # المقر والدرجة
        select_by_text(page, 0, "الخرج (طلاب)")
        select_by_text(page, 1, "بكالوريوس")

        # فتح الشجرة
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

            # قراءة النتيجة
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

            found = False
            for r in rows_data:
                if r["section"] == sec:
                    found = True
                    icon = "🟢" if "مفتوحة" in r["status"] else "🔴"
                    report.append(f"{icon} *{r['title']}*\n• الرمز: {r['code']} | الشعبة: {r['section']}\n• الحالة: {r['status']}")
                    break
            
            if not found:
                report.append(f"⚠️ *مادة {code} (شعبة {sec})* لم تظهر في البحث.")

        browser.close()

    return "\n\n".join(report)

def main():
    print("🤖 البوت يعمل الآن وينتظر أوامرك من التيليجرام...")
    send_telegram("🤖 البوت جاهز ويعمل الآن!\n\nأرسل كلمة /check أو أي رسالة لبدء فحص الشعب.")
    
    last_update_id = None

    while True:
        updates = get_updates(last_update_id)
        for update in updates:
            last_update_id = update["update_id"] + 1
            message = update.get("message", {})
            sender_id = str(message.get("from", {}).get("id", ""))
            text = message.get("text", "")

            # التأكد أن الرسالة واردة من حسابك أنت فقط
            if sender_id == TELEGRAM_CHAT_ID:
                print(f"📩 تم استلام طلب فحص: {text}")
                send_telegram("⏳ جاري الدخول على بوابة الجامعة وفحص الشعب...")
                
                # تنفيذ الفحص وإرسال التقرير
                result_report = check_all_sections()
                send_telegram(f"📊 *تقرير حالة الشعب الحالي:*\n\n{result_report}")

        time.sleep(2)

if __name__ == "__main__":
    main()
