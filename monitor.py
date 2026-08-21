import time
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

def select_by_text(page, select_index, text_match):
    """اختيار القيمة من القائمة المنسدلة بناءً على رقمها في الصفحة"""
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

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 1. فتح موقع الجامعة...")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        # 1. اختيار المقر (القائمة الأولى 0)
        print("🔘 2. اختيار المقر: الخرج (طلاب)...")
        select_by_text(page, 0, "الخرج (طلاب)")

        # 2. اختيار الدرجة العلمية (القائمة الثانية 1)
        print("🔘 3. اختيار الدرجة: بكالوريوس...")
        select_by_text(page, 1, "بكالوريوس")

        # 3. فتح مجلد المقررات المطروحة
        print("📁 4. الضغط على أيقونة المقررات المطروحة...")
        page.locator("text=المقررات المطروحة").last.click()
        page.wait_for_timeout(2500)

        # 4. فتح مجلد التمريض بالخرج
        print("📂 5. الضغط على التمريض بالخرج...")
        page.locator("text=التمريض بالخرج").first.click()
        page.wait_for_timeout(2500)

        # 5. الضغط على علوم التمريض
        print("📄 6. الضغط على علوم التمريض...")
        page.locator("text=علوم التمريض").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        print("\n========== محتوى صفحة الشعب المستخرجة ==========\n")
        text = page.locator("body").inner_text()
        print(text)
        print("\n================================================\n")

        browser.close()

if __name__ == "__main__":
    main()
