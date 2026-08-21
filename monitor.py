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
    {"code": "3104", "section": "2481", "name": "3104 تمرض"},
    {"code": "3101", "section": "2512", "name": "3101 تمرض"},
    {"code": "3201", "section": "2494", "name": "3201 تمرض"},
]

def send_telegram(message):
    """إرسال إشعار فوري للتيليجرام"""
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
        print(f"⚠️ فشل إرسال التيليجرام: {e}")

def select_by_text(page, select_index, text_match):
    """اختيار القيمة من القائمة المنسدلة"""
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

def search_and_check(page, course_code, section_number, course_name):
    """كتابة رمز المادة، الضغط على المكبر، وفحص حالة الشعبة"""
    print(f"\n🔎 جاري البحث عن المادة [{course_code}] والشعبة [{section_number}]...")

    # 1. العثور على خانة رمز المقرر وكتابة الرقم فيها
    page.evaluate(f'''() => {{
        const inputs = document.querySelectorAll("input[type='text']");
        if (inputs.length > 0) {{
            // مسح أي نص قديم وكتابة رمز المادة في الخانة الأولى
            inputs[0].value = "{course_code}";
            inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
            inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}''')
    page.wait_for_timeout(1000)

    # 2. الضغط على أيقونة العدسة المكبرة
    search_clicked = page.evaluate('''() => {
        // البحث عن صورة المكبر أو الزر المرتبط بالبحث
        const imgs = Array.from(document.querySelectorAll("img, input[type='image'], a"));
        for (let el of imgs) {
            if ((el.src && (el.src.includes('search') || el.src.includes('find') || el.src.includes('lens'))) || 
                (el.onclick && el.onclick.toString().includes('search')) ||
                (el.getAttribute('onclick') && el.getAttribute('onclick').includes('search'))) {
                el.click();
                return true;
            }
        }
        // خيار احتياطي: الضغط على أول صورة بجانب خانات الإدخال
        const firstImg = document.querySelector("input[type='text'] ~ img, tr img");
        if (firstImg) {
            firstImg.click();
            return true;
        }
        return false;
    }''')

    if not search_clicked:
        # محاولة الضغط عبر لوحة المفاتيح في حال لم يُعثر على المعرف
        page.locator("input[type='text']").first.press("Enter")

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)

    # 3. قراءة بيانات الجدول بعد الفلترة
    table_rows = page.locator("tr").all()
    section_found = False

    for row in table_rows:
        row_text = row.inner_text()
        if section_number in row_text:
            section_found = True
            if "مفتوحة" in row_text:
                print(f"🎉 الشعبة {section_number} ({course_name}) مفتوحة الآن!")
                send_telegram(f"🚨 تنبيه: شعبة مفتوحة الآن!\n\n📚 المادة: {course_name}\n🔢 الشعبة: {section_number}\n🟢 الحالة: مفتوحة\n\nادخل على البوابة وسجل فوراً!")
            else:
                print(f"🔒 الشعبة {section_number} ({course_name}) موجودة ولكن حالتها (مغلقة).")
            break

    if not section_found:
        print(f"⚠️ الشعبة {section_number} ({course_name}) لم تظهر في نتائج البحث.")

def main():
    print("🚀 بدء الفحص المباشر...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 1. فتح الموقع واختيار المقر والدرجة...")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        # اختيار المقر والدرجة
        select_by_text(page, 0, "الخرج (طلاب)")
        select_by_text(page, 1, "بكالوريوس")

        # الوصول لعلوم التمريض
        print("📂 2. الدخول لصفحة علوم التمريض...")
        page.locator("text=المقررات المطروحة").last.click()
        page.wait_for_timeout(2000)
        page.locator("text=التمريض بالخرج").first.click()
        page.wait_for_timeout(2000)
        page.locator("text=علوم التمريض").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)

        # 3. فحص المواد الثلاث بالبحث المباشر
        print("\n================== نتائج الفحص ==================")
        for item in TARGETS:
            search_and_check(page, item["code"], item["section"], item["name"])
        print("=================================================\n")

        browser.close()

if __name__ == "__main__":
    main()
