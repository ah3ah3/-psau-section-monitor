import time
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

def select_dropdown(page, text_match):
    option = page.locator(f"option:has-text('{text_match}')").first
    option.wait_for(state="attached", timeout=15000)
    val = option.get_attribute("value")
    select_elem = page.locator("select").filter(has=option).first
    select_elem.select_option(value=val)
    select_elem.dispatch_event("change")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 1. فتح الموقع...")
        page.goto(URL, wait_until="networkidle", timeout=60000)

        # 1. المقر
        print("🔘 2. اختيار الخرج (طلاب)...")
        select_dropdown(page, "الخرج (طلاب)")

        # 2. الدرجة
        print("🔘 3. اختيار بكالوريوس...")
        select_dropdown(page, "بكالوريوس")

        # 3. فتح مجلد التمريض
        print("📂 4. فتح مجلد التمريض بالخرج...")
        page.get_by_text("التمريض بالخرج", exact=False).first.click()
        page.wait_for_timeout(2000)

        # 4. الضغط على تخصص علوم التمريض المحدد
        print("📄 5. الضغط على تخصص علوم التمريض...")
        page.get_by_text("علوم التمريض", exact=True).first.click()
        
        # انتظار تحميل جدول المقررات
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        print("\n========== محتوى جدول المواد المستخرج ==========\n")
        body_text = page.locator("body").inner_text()
        print(body_text)
        print("\n================================================\n")

        browser.close()

if __name__ == "__main__":
    main()
