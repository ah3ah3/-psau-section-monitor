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

        print("📄 عنوان الصفحة:", page.title())

        # نطبع النص الموجود في الصفحة حتى نعرف كيف يتعامل الموقع
        text = page.locator("body").inner_text()

        print("\n========== محتوى الصفحة ==========\n")
        print(text[:12000])
        print("\n==================================\n")

        browser.close()


if __name__ == "__main__":
    main()
