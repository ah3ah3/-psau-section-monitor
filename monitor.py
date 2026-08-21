import time
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

# بيانات التيليجرام الخاصة بك
TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

# الشعب والمواد المستهدفة بدقة
TARGETS = [
    {"code": "3104", "section": "2481"},
    {"code": "3101", "section": "2512"},
    {"code": "3201", "section": "2494"},
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

def search_and_check(page, course_code, target_section):
    """البحث برمز المادة وفحص الشعبة المحددة فقط"""
    print(f"\n🔎 جاري البحث عن المادة [{course_code}] للشعبة المطلوبة [{target_section}]...")

    # 1. إدخال رمز المقرر
    page.evaluate(f'''() => {{
        const inputs = document.querySelectorAll("input[type='text']");
        if (inputs.length > 0) {{
            inputs[0].value = "{course_code}";
            inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
            inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}''')
    page.wait_for_timeout(1000)

    # 2. الضغط على أيقونة العدسة المكبرة
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
    page.wait_for_timeout(4000)

    # 3. قراءة صفوف الجدول بدقة وفصل كل شعبة
    rows_data = page.evaluate('''() => {
        const list = [];
        const trs = document.querySelectorAll("tr");
        trs.forEach(tr => {
            const tds = Array.from(tr.children).filter(c => c.tagName.toLowerCase() === 'td');
            // التأكد أن الصف هو صف مادة وليس جدول رئيسي أو ترويسة
            if (tds.length >= 7 && !tr.querySelector('table')) {
                const code = tds[0].innerText.trim();
                const title = tds[1].innerText.trim();
                const section = tds[2].innerText.trim();
                const status = tds[6].innerText.trim();
                if (section && /^\\d+$/.test(section)) {
                    list.push({ code, title, section, status });
                }
            }
        });
        return list;
    }''')

    # 4. مطابقة الشعبة المستهدفة وحالتها
    target_found = False
    for item in rows_data:
        if item["section"] == str(target_section):
            target_found = True
            is_open = "مفتوحة" in item["status"]
            print(f"📌 المادة: {item['title']} | الرمز: {item['code']} | الشعبة: {item['section']} | الحالة: {item['status']}")

            if is_open:
                print(f"🎉 شعبة مفتوحة: {item['title']} ({target_section})")
                msg = (
                    f"🚨 تنبيه: شعبة مفتوحة الآن!\n\n"
                    f"📚 اسم المقرر: {item['title']}\n"
                    f"🏷️ رمز المقرر: {item['code']}\n"
                    f"🔢 رقم الشعبة: {item['section']}\n"
                    f"🟢 الحالة: مفتوحة\n\n"
                    f"ادخل على البوابة وسجل فوراً!"
                )
                send_telegram(msg)
            else:
                print(f"🔒 الشعبة {target_section} لا تزال مغلقة.")
            break

    if not target_found:
        print(f"⚠️ الشعبة {target_section} لم تظهر في نتائج البحث.")

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
