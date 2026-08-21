import time
import re
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

TARGETS = [
    {"code": "3104", "section": "2481", "name": "3104 تمرض"},
    {"code": "3101", "section": "2512", "name": "3101 تمرض"},
    {"code": "3201", "section": "2494", "name": "3201 تمرض"},
]

def send_telegram(message):
    """إرسال تنبيه إلى التيليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
        print("📲 تم إرسال إشعار تيليجرام!")
    except Exception as e:
        print(f"⚠️ خطأ بإرسال التيليجرام: {e}")

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

def extract_all_table_data(page):
    """جمع بيانات الجدول من الصفحة الحالية وجميع صفحات الترقيم (1, 2, 3, 4...)"""
    full_text = page.locator("body").inner_text()
    
    # محاولة المرور على كل أرقام الصفحات
    page_numbers = ["2", "3", "4", "5"]
    for num in page_numbers:
        btn = page.locator(f"a:has-text('{num}'), span:has-text('{num}')").first
        if btn.is_visible():
            try:
                print(f"📄 جاري فحص الصفحة رقم {num}...")
                btn.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2500)
                full_text += "\n" + page.locator("body").inner_text()
            except Exception:
                pass
    return full_text

def main():
    print("🚀 بدء الفحص والمراقبة...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 1. فتح موقع الجامعة...")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        # 1. اختيار المقر والدرجة
        print("🔘 2. اختيار المقر والدرجة...")
        select_by_text(page, 0, "الخرج (طلاب)")
        select_by_text(page, 1, "بكالوريوس")

        # 2. فتح الشجرة والوصول للتخصص
        print("📂 3. الوصول لعلوم التمريض...")
        page.locator("text=المقررات المطروحة").last.click()
        page.wait_for_timeout(2000)
        page.locator("text=التمريض بالخرج").first.click()
        page.wait_for_timeout(2000)
        page.locator("text=علوم التمريض").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)

        print("🔍 4. مسح وقراءة جميع صفحات الشعب...")
        all_pages_data = extract_all_table_data(page)

        print("\n================== نتائج الفحص ==================")
        for item in TARGETS:
            sec = item["section"]
            course = item["name"]

            if sec in all_pages_data:
                # استخراج السطر الخاص بالشعبة لمعرفة حالتها
                lines = [l for l in all_pages_data.split("\n") if sec in l]
                section_line = lines[0] if lines else ""
                
                if "مفتوحة" in section_line or "مفتوحة" in all_pages_data:
                    print(f"🎉 الشعبة {sec} ({course}) مفتوحة!")
                    send_telegram(f"🚨 تنبيه: شعبة مفتوحة الآن!\n\n📚 المادة: {course}\n🔢 الشعبة: {sec}\n🟢 الحالة: مفتوحة\n\nادخل على البوابة وسجل فوراً!")
                else:
                    print(f"🔒 الشعبة {sec} ({course}) وُجدت في الجدول ولكنها (مغلقة).")
            else:
                print(f"⚠️ الشعبة {sec} ({course}) لم يتم العثور عليها.")
        print("=================================================\n")

        browser.close()

if __name__ == "__main__":
    main()
