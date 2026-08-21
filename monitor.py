import time
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

# بيانات التيليجرام
TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

# الشعب والمواد المستهدفة
TARGETS = [
    {"code": "3104", "section": "2481"},
    {"code": "3101", "section": "2512"},
    {"code": "3201", "section": "2494"},
]

def send_telegram(message):
    """إرسال تنبيه مباشر للتيليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
        print("📲 تم إرسال إشعار تيليجرام بنجاح!")
    except Exception as e:
        print(f"⚠️ فشل إرسال التيليجرام: {e}")

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

def search_and_check(page, course_code, section_number):
    print(f"\n🔎 جاري البحث عن المادة [{course_code}] والشعبة [{section_number}]...")

    # 1. كتابة رمز المقرر
    page.evaluate(f'''() => {{
        const inputs = document.querySelectorAll("input[type='text']");
        if (inputs.length > 0) {{
            inputs[0].value = "{course_code}";
            inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
            inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}''')
    page.wait_for_timeout(1000)

    # 2. الضغط على العدسة المكبرة
    search_clicked = page.evaluate('''() => {
        const imgs = Array.from(document.querySelectorAll("img, input[type='image'], a"));
        for (let el of imgs) {
            if ((el.src && (el.src.includes('search') || el.src.includes('find') || el.src.includes('lens'))) || 
                (el.onclick && el.onclick.toString().includes('search')) ||
                (el.getAttribute('onclick') && el.getAttribute('onclick').includes('search'))) {
                el.click();
                return true;
            }
        }
        const firstImg = document.querySelector("input[type='text'] ~ img, tr img");
        if (firstImg) {
            firstImg.click();
            return true;
        }
        return false;
    }''')

    if not search_clicked:
        page.locator("input[type='text']").first.press("Enter")

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)

    # 3. قراءة صفوف وأعمدة الجدول واستخراج اسم المادة
    rows = page.locator("tr").all()
    section_found = False

    for row in rows:
        cells = row.locator("td").all()
        # التأكد أن الصف يحتوي على أعمدة الجدول كاملة
        if len(cells) >= 6:
            code_text = cells[0].inner_text().strip()
            course_title = cells[1].inner_text().strip()
            sec_text = cells[2].inner_text().strip()
            status_text = cells[6].inner_text().strip() if len(cells) > 6 else row.inner_text()

            if section_number in sec_text or section_number in row.inner_text():
                section_found = True
                if "مفتوحة" in status_text or "مفتوحة" in row.inner_text():
                    print(f"🎉 شعبة مفتوحة: {course_title} ({section_number})")
                    msg = (
                        f"🚨 تنبيه: شعبة مفتوحة الآن!\n\n"
                        f"📚 اسم المقرر: {course_title}\n"
                        f"🏷️ رمز المقرر: {code_text}\n"
                        f"🔢 رقم الشعبة: {section_number}\n"
                        f"🟢 الحالة: مفتوحة\n\n"
                        f"ادخل على البوابة وسجل فوراً!"
                    )
                    send_telegram(msg)
                else:
                    print(f"🔒 المادة: {course_title} | الشعبة: {section_number} | الحالة: مغلقة.")
                break

    if not section_found:
        print(f"⚠️ الشعبة {section_number} لم تظهر في نتائج البحث.")

def main():
    print("🚀 بدء الفحص المباشر...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 1. فتح الموقع واختيار المقر والدرجة...")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        select_by_text(page, 0, "الخرج (طلاب)")
        select_by_text(page, 1, "بكالوريوس")

        print("📂 2. الدخول لصفحة علوم التمريض...")
        page.locator("text=المقررات المطروحة").last.click()
        page.wait_for_timeout(2000)
        page.locator("text=التمريض بالخرج").first.click()
        page.wait_for_timeout(2000)
        page.locator("text=علوم التمريض").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)

        print("\n================== نتائج الفحص ==================")
        for item in TARGETS:
            search_and_check(page, item["code"], item["section"])
        print("=================================================\n")

        browser.close()

if __name__ == "__main__":
    main()
