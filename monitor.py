import os
import time
import json
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"
DATA_FILE = "targets.json"

# بيانات التيليجرام الخاصة بك
TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

CHECK_INTERVAL_MINUTES = 3
browser_lock = threading.Lock()
data_lock = threading.Lock()

# الشعب الافتراضية
DEFAULT_TARGETS = [
    {"code": "3104", "section": "2481"},
    {"code": "3101", "section": "2512"},
    {"code": "3201", "section": "2494"},
]

def load_targets():
    """تحميل قائمة الشعب من الملف"""
    with data_lock:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_TARGETS, f, ensure_ascii=False, indent=2)
        return DEFAULT_TARGETS

def save_targets(targets):
    """حفظ قائمة الشعب إلى الملف"""
    with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(targets, f, ensure_ascii=False, indent=2)

# خادم ويب لإبقاء Render مستقراً 24/7
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"PSAU Monitor Active with Dynamic Menu")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def send_telegram(message, reply_markup=None):
    """إرسال رسالة إلى التيليجرام مع دعم لوحة الأزرار"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ فشل الإرسال: {e}")

def get_main_keyboard():
    """لوحة التحكم بالأزرار في تيليجرام"""
    return {
        "keyboard": [
            [{"text": "🔍 فحص الشعب"}, {"text": "📋 الشعب المراقبة"}],
            [{"text": "ℹ️ تعليمات الإضافة والحذف"}]
        ],
        "resize_keyboard": True
    }

def get_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?timeout=15"
        if offset:
            url += f"&offset={offset}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("result", [])
    except Exception:
        return []

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
    page.wait_for_timeout(2000)

def scrape_sections(is_auto=False):
    targets = load_targets()
    if not targets:
        return "⚠️ لا توجد شعب مسجلة حالياً للمراقبة."

    report = []
    
    with browser_lock:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.goto(URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)

            # المقر والدرجة
            select_by_text(page, 0, "الخرج (طلاب)")
            select_by_text(page, 1, "بكالوريوس")

            # فتح الشجرة
            page.locator("text=المقررات المطروحة").last.click()
            page.wait_for_timeout(2000)
            page.locator("text=التمريض بالخرج").first.click()
            page.wait_for_timeout(2000)
            page.locator("text=علوم التمريض").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3500)

            for item in targets:
                code = item["code"]
                sec = item["section"]

                # إدخال رمز المقرر
                page.evaluate(f'''() => {{
                    const inputs = document.querySelectorAll("input[type='text']");
                    if (inputs.length > 0) {{
                        inputs[0].value = "{code}";
                        inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}''')
                page.wait_for_timeout(1000)

                # الضغط على العدسة
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
                page.wait_for_timeout(3500)

                rows_data = page.evaluate('''() => {
                    const list = [];
                    const trs = document.querySelectorAll("tr");
                    trs.forEach(tr => {
                        const tds = Array.from(tr.children).filter(c => c.tagName.toLowerCase() === 'td');
                        if (tds.length >= 7 && !tr.querySelector('table')) {
                            const c = tds[0].innerText.trim();
                            const t = tds[1].innerText.trim();
                            const s = tds[2].innerText.trim();
                            const st = tds[6].innerText.trim();
                            if (s && /^\\d+$/.test(s)) {
                                list.push({ code: c, title: t, section: s, status: st });
                            }
                        }
                    });
                    return list;
                }''')

                found = False
                for r in rows_data:
                    if r["section"] == sec:
                        found = True
                        is_open = "مفتوحة" in r["status"]
                        icon = "🟢" if is_open else "🔴"
                        report.append(f"{icon} *{r['title']}*\n• الرمز: {r['code']} | الشعبة: {r['section']}\n• الحالة: {r['status']}")

                        if is_open and is_auto:
                            alert_msg = (
                                f"🚨 تنبيه عاجل: شعبة مفتوحة الآن!\n\n"
                                f"📚 المقرر: {r['title']}\n"
                                f"🏷️ الرمز: {r['code']}\n"
                                f"🔢 الشعبة: {r['section']}\n"
                                f"🟢 الحالة: مفتوحة\n\n"
                                f"ادخل على البوابة وسجل فوراً!"
                            )
                            send_telegram(alert_msg)
                        break

                if not found:
                    report.append(f"⚠️ مادة {code} (شعبة {sec}) لم تظهر في البحث.")

            browser.close()

    return "\n\n".join(report)

def auto_check_loop():
    time.sleep(10)
    while True:
        try:
            scrape_sections(is_auto=True)
        except Exception as e:
            print(f"⚠️ خطأ في الفحص الدوري: {e}")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    threading.Thread(target=auto_check_loop, daemon=True).start()

    send_telegram(
        "🤖 أهلاً بك! لوحة التحكم بالشعب جاهزة الآن.\n\n"
        "استخدم الأزرار بالأسفل للتحكم أو الأوامر السريعة.",
        reply_markup=get_main_keyboard()
    )

    initial_updates = get_updates()
    last_update_id = initial_updates[-1]["update_id"] + 1 if initial_updates else None

    while True:
        updates = get_updates(last_update_id)
        for update in updates:
            last_update_id = update["update_id"] + 1
            message = update.get("message", {})
            sender_id = str(message.get("from", {}).get("id", ""))
            text = message.get("text", "").strip()

            if sender_id != TELEGRAM_CHAT_ID:
                continue

            # 1. فحص الشعب
            if text in ["/check", "🔍 فحص الشعب"]:
                send_telegram("⏳ جاري فحص الشعب من بوابة الجامعة...")
                try:
                    res = scrape_sections(is_auto=False)
                    send_telegram(f"📊 تقرير حالة الشعب:\n\n{res}", reply_markup=get_main_keyboard())
                except Exception as e:
                    send_telegram(f"⚠️ حدث خطأ: {e}", reply_markup=get_main_keyboard())

            # 2. عرض قائمة الشعب المراقبة
            elif text in ["/list", "📋 الشعب المراقبة"]:
                targets = load_targets()
                if not targets:
                    send_telegram("📭 لا توجد شعب مضافة للمراقبة حالياً.", reply_markup=get_main_keyboard())
                else:
                    msg = "📋 *الشعب المسجلة في المراقبة التلقائية:*\n\n"
                    for idx, t in enumerate(targets, 1):
                        msg += f"{idx}. رمز المادة: `{t['code']}` | الشعبة: `{t['section']}`\n"
                    msg += "\nلحذف أي شعبة أرسل: `/del رقم_الشعبة`"
                    send_telegram(msg, reply_markup=get_main_keyboard())

            # 3. إضافة شعبة جديدة
            elif text.startswith("/add") or text.startswith("/اضافة") or text.startswith("اضافة"):
                parts = text.split()
                if len(parts) >= 3:
                    c_code = parts[1]
                    s_num = parts[2]
                    targets = load_targets()
                    # التحقق من عدم التكرار
                    if any(t["section"] == s_num for t in targets):
                        send_telegram(f"⚠️ الشعبة {s_num} موجودة بالفعل في قائمة المراقبة!", reply_markup=get_main_keyboard())
                    else:
                        targets.append({"code": c_code, "section": s_num})
                        save_targets(targets)
                        send_telegram(f"✅ تمت إضافة المادة `{c_code}` والشعبة `{s_num}` بنجاح للمراقبة الدورية!", reply_markup=get_main_keyboard())
                else:
                    send_telegram("⚠️ طريقة الإضافة الصحيحة:\n`/add رمز_المادة رقم_الشعبة`\nمثال: `/add 3104 2481`", reply_markup=get_main_keyboard())

            # 4. حذف شعبة من المراقبة
            elif text.startswith("/del") or text.startswith("/حذف") or text.startswith("حذف"):
                parts = text.split()
                if len(parts) >= 2:
                    s_num = parts[1]
                    targets = load_targets()
                    new_targets = [t for t in targets if t["section"] != s_num]
                    if len(new_targets) < len(targets):
                        save_targets(new_targets)
                        send_telegram(f"🗑️ تم إيقاف المراقبة وحذف الشعبة `{s_num}` بنجاح.", reply_markup=get_main_keyboard())
                    else:
                        send_telegram(f"⚠️ الشعبة `{s_num}` غير موجودة في القائمة.", reply_markup=get_main_keyboard())
                else:
                    send_telegram("⚠️ طريقة الحذف الصحيحة:\n`/del رقم_الشعبة`\nمثال: `/del 2481`", reply_markup=get_main_keyboard())

            # 5. المساعدة والتعليمات
            elif text in ["/help", "/start", "ℹ️ تعليمات الإضافة والحذف"]:
                help_msg = (
                    "📌 *أوامر التحكم بالبوت:*\n\n"
                    "➕ *إضافة شعبة:* `/add رمز_المادة رقم_الشعبة`\n"
                    "مثال: `/add 3101 2512`\n\n"
                    "➖ *حذف شعبة:* `/del رقم_الشعبة`\n"
                    "مثال: `/del 2512`\n\n"
                    "📋 *عرض الشعب:* اضغط زر (📋 الشعب المراقبة)\n"
                    "🔍 *فحص فوري:* اضغط زر (🔍 فحص الشعب)"
                )
                send_telegram(help_msg, reply_markup=get_main_keyboard())

        time.sleep(2)

if __name__ == "__main__":
    main()
