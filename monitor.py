import time
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

TARGETS = {
    "3104": "2481",
    "3101": "2512",
    "3201": "2494",
}

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🌐 فتح موقع الجامعة...")
        page.goto(URL, wait_until="networkidle", timeout=60000)

        print("🔘 1. اختيار المقر: الخرج (طلاب)...")
        page.get_by_text("الخرج (طلاب)", exact=False).first.click()
        page.wait_for_timeout(2000)

        print("🔘 2. اختيار الدرجة: بكالوريوس...")
        page.get_by_text("بكالوريوس", exact=False).first.click()
        page.wait_for_timeout(2000)

        print("🔘 3. اختيار الكلية: التمريض بالخرج...")
        page.get_by_text("التمريض بالخرج", exact=False).first.click()
        page.wait_for_timeout(2000)

        print("🔘 4. اختيار التخصص: علوم التمريض...")
        page.get_by_text("علوم التمريض", exact=False).first.click()
        page.wait_for_timeout(4000)

        print("\n========== محتوى صفحة الشعب ==========\n")
        text = page.locator("body").inner_text()
        print(text[:15000])
        print("\n======================================\n")

        browser.close()

if __name__ == "__main__":
    main()
