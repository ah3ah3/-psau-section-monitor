import time
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

# بيانات التيليجرام الخاصة بك
TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

# الشعب والمواد المستهدفة
TARGETS = [
    {"code": "3104", "section": "2481", "name": "3104 تمرض"},
    {"code": "3101", "section": "2512", "name": "3101 تمرض"},
    {"code": "3201", "section": "2494", "name": "3201 تمرض"},
]

def send_telegram(message):
    """إرسال إشعار فوري إلى حسابك في تيليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
        print("📲 تم إرسال إشعار تيليجرام بنجاح!")
    except Exception as e:
        print(f"⚠️ فشل إرسال إشعار تيليجرام: {e}")

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
    page.wait_for_timeout(2500)

def search_course(page, course_code):
    """البحث المباشر برمز المقرر لتصفية الشعب بسرعة"""
    try:
        inputs = page.locator("input[type='text']")
        if inputs.count() > 0:
            inputs.first.fill(course_code)
            search_btn = page.locator("input[type='submit'][value*='إبحث'], button:has-text('إبحث'), a:has-text('إبحث')").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
    except Exception as e:
        print(f"تخطي البحث المباشر للمقرر {course_code}: {e}")

def main():
    print("🚀 بدء الفحص...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 1. فتح موقع الجامعة...")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        # 1. المقر والدرجة
        select_by_text(page, 0, "الخرج (طلاب)")
        select_by_text(page, 1, "بكالوريوس")

        # 2. الانتقال إلى شجرة علوم التمريض
        page.locator("text=المقررات المطروحة").last.click()
        page.wait_for_timeout(2500)
        page.locator("text=التمريض بالخرج").first.click()
        page.wait_for_timeout(2500)
        page.locator("text=علوم التمريض").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        print("\n🔍 2. فحص الشعب المستهدفة...\n")

        for item in TARGETS:
            code = item["code"]
            sec = item["section"]
            course = item["name"]

            # تصفية المقررات بالبحث
            search_course(page, code)
            page_text = page.locator("body").inner_text()

            # التحقق من وجود الشعبة وحالتها
            if sec in page_text:
                # فحص حالة الشعبة
                rows = page.locator("tr").all()
                found = False
                for row in rows:
                    row_text = row.inner_text()
                    if sec in row_text:
                        found = True
                        if "مفتوحة" in row_text:
                            print(f"🎉 الشعبة {sec} ({course}) مفتوحة!")
                            send_telegram(f"🚨 *تنبيه: شعبة مفتوحة الآن!*\n\n📚 *المادة:* {course}\n🔢 *الشعبة:* {sec}\n🟢 *الحالة:* مفتوحة\n\nادخل على البوابة وسجل فوراً!")
                        else:
                            print(f"🔒 الشعبة {sec} ({course}) ما زالت مغلقة.")
                        break
                if not found:
                    print(f"🔒 الشعبة {sec} ({course}) مغلقة حالياً.")
            else:
                print(f"⚠️ الشعبة {sec} ({course}) لم تظهر في الجدول.")

        browser.close()

if __name__ == "__main__":
    main()
