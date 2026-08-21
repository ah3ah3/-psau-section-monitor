import time
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

def select_option_by_text(page, text):
    print(f"🔘 جاري اختيار: {text}...")
    # العثور على الخيار وقراءة قيمته
    option = page.locator(f"option:has-text('{text}')").first
    option.wait_for(state="attached", timeout=15000)
    val = option.get_attribute("value")
    
    # اختيار القيمة من القائمة المنسدلة التابعة له
    select_elem = page.locator("select").filter(has=option).first
    select_elem.select_option(value=val)
    
    # انتظار تحميل البيانات التلقائية للموقع
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 فتح موقع الجامعة...")
        page.goto(URL, wait_until="networkidle", timeout=60000)

        # 1. اختيار المقر
        select_option_by_text(page, "الخرج (طلاب)")

        # 2. اختيار الدرجة العلمية
        select_option_by_text(page, "بكالوريوس")

        # 3. اختيار الكلية
        select_option_by_text(page, "التمريض بالخرج")

        # 4. اختيار التخصص
        select_option_by_text(page, "علوم التمريض")

        print("\n========== محتوى صفحة الشعب ==========\n")
        text = page.locator("body").inner_text()
        print(text[:15000])
        print("\n======================================\n")

        browser.close()

if __name__ == "__main__":
    main()
