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

TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

CHECK_INTERVAL_MINUTES = 3
browser_lock = threading.Lock()
data_lock = threading.Lock()

user_states = {}

DEFAULT_TARGETS = [
    {"code": "3104", "section": "2481", "active": True},
    {"code": "3101", "section": "2512", "active": True},
    {"code": "3201", "section": "2494", "active": True},
]

def load_targets():
    with data_lock:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    targets = json.load(f)
                    for t in targets:
                        if "active" not in t:
                            t["active"] = True
                    return targets
            except Exception:
                pass
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_TARGETS, f, ensure_ascii=False, indent=2)
        return DEFAULT_TARGETS

def save_targets(targets):
    with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(targets, f, ensure_ascii=False, indent=2)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"PSAU Monitor Active 24/7 with Interactive Menu")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def send_telegram(message, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ فشل الإرسال: {e}")

def answer_callback(callback_query_id, text=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def edit_telegram_message(message_id, text, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "text": text
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠️ فشل تعديل الرسالة: {e}")

def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "⚙️ إدارة الشعب المراقبة"}, {"text": "🔍 فحص فوري"}],
            [{"text": "➕ إضافة شعبة جديدة"}, {"text": "ℹ️ المساعدة"}]
        ],
        "resize_keyboard": True
    }

def get_manage_keyboard():
    targets = load_targets()
    inline_keyboard = []

    if not targets:
        text = "📭 لا توجد شعب مضافة للمراقبة حالياً.\nاضغط على الزر بالأسفل لإضافة مادة وشعبة جديدة."
    else:
        text = "📋 *قائمة الشعب المراقبة:*\nاضغط على الأزرار لتفعيل/إيقاف التنبيه أو الحذف المباشر:"
        for t in targets:
            sec = t["section"]
            code = t["code"]
            is_active = t.get("active", True)

            status_btn_text = f"🔔 مادة {code} (شعبة {sec})" if is_active else f"🔕 مادة {code} (شعبة {sec}) - موقف"
            toggle_action = f"toggle_{sec}"
            delete_action = f"del_{sec}"

            inline_keyboard.append([
                {"text": status_btn_text, "callback_data": toggle_action},
                {"text": "🗑️ حذف", "callback_data": delete_action}
            ])

    inline_keyboard.append([
        {"text": "➕ إضافة مادة جديدة", "callback_data": "btn_add"},
        {"text": "🔍 فحص فوري الآن", "callback_data": "btn_check"}
    ])

    return text, {"inline_keyboard": inline_keyboard}

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
                is_active = item.get("active", True)

                # إذا كان فحص تلقائي والشعبة موقف تنبيهها نتخطاها
                if is_auto and not is_active:
                    continue

                # إدخال رمز المادة
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
                        pause_tag = " (التنبيه موقّف 🔕)" if not is_active else ""
                        report.append(f"{icon} *{r['title']}*{pause_tag}\n• الرمز: {r['code']} | الشعبة: {r['section']}\n• الحالة: {r['status']}")

                        if is_open and is_auto and is_active:
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
        "🤖 أهلاً بك! تم تحديث نظام المراقبة.\n"
        "يمكنك الآن التحكم بالشعب وإيقاف/تفعيل التنبيهات من خلال الأزرار التفاعلية.",
        reply_markup=get_main_keyboard()
    )

    initial_updates = get_updates()
    last_update_id = initial_updates[-1]["update_id"] + 1 if initial_updates else None

    while True:
        updates = get_updates(last_update_id)
        for update in updates:
            last_update_id = update["update_id"] + 1

            # 1. معالجة الضغط على أزرار القوائم (Callback Queries)
            if "callback_query" in update:
                cq = update["callback_query"]
                cq_id = cq["id"]
                data = cq.get("data", "")
                msg = cq.get("message", {})
                msg_id = msg.get("message_id")

                # تفعيل أو إيقاف التنبيه لشعبة
                if data.startswith("toggle_"):
                    sec_to_toggle = data.replace("toggle_", "")
                    targets = load_targets()
                    for t in targets:
                        if t["section"] == sec_to_toggle:
                            t["active"] = not t.get("active", True)
                            state_txt = "تم تفعيل التنبيه 🔔" if t["active"] else "تم إيقاف التنبيه مؤقتاً 🔕"
                            answer_callback(cq_id, f"{state_txt} للشعبة {sec_to_toggle}")
                            break
                    save_targets(targets)
                    txt, kb = get_manage_keyboard()
                    edit_telegram_message(msg_id, txt, kb)

                # حذف شعبة
                elif data.startswith("del_"):
                    sec_to_del = data.replace("del_", "")
                    targets = load_targets()
                    new_targets = [t for t in targets if t["section"] != sec_to_del]
                    save_targets(new_targets)
                    answer_callback(cq_id, f"🗑️ تم حذف الشعبة {sec_to_del}")
                    txt, kb = get_manage_keyboard()
                    edit_telegram_message(msg_id, txt, kb)

                # زر إضافة مادة
                elif data == "btn_add":
                    user_states[TELEGRAM_CHAT_ID] = "WAITING_ADD"
                    answer_callback(cq_id)
                    send_telegram("✏️ أرسل الآن **رمز المقرر** متبوعاً بـ **رقم الشعبة** (بينهما مسافة):\n\nمثال:\n`3104 2481`")

                # زر فحص فوري
                elif data == "btn_check":
                    answer_callback(cq_id, "⏳ جاري الفحص...")
                    send_telegram("⏳ جاري فحص الشعب من بوابة الجامعة...")
                    try:
                        res = scrape_sections(is_auto=False)
                        send_telegram(f"📊 تقرير حالة الشعب:\n\n{res}")
                    except Exception as e:
                        send_telegram(f"⚠️ حدث خطأ: {e}")

                continue

            # 2. معالجة الرسائل النصية العادية
            if "message" in update:
                message = update["message"]
                sender_id = str(message.get("from", {}).get("id", ""))
                text = message.get("text", "").strip()

                if sender_id != TELEGRAM_CHAT_ID:
                    continue

                # حالة انتظار إدخال مادة جديدة
                if user_states.get(sender_id) == "WAITING_ADD":
                    user_states[sender_id] = None
                    parts = text.split()
                    if len(parts) >= 2:
                        c_code = parts[0]
                        s_num = parts[1]
                        targets = load_targets()
                        if any(t["section"] == s_num for t in targets):
                            send_telegram(f"⚠️ الشعبة {s_num} موجودة مسبقاً في القائمة!", reply_markup=get_main_keyboard())
                        else:
                            targets.append({"code": c_code, "section": s_num, "active": True})
                            save_targets(targets)
                            send_telegram(f"✅ تمت إضافة المقرر `{c_code}` والشعبة `{s_num}` بنجاح!")
                            txt, kb = get_manage_keyboard()
                            send_telegram(txt, reply_markup=kb)
                    else:
                        send_telegram("⚠️ إدخال غير صحيح. تم إلغاء الإضافة. اضغط '➕ إضافة شعبة جديدة' للمحاولة مرة أخرى.", reply_markup=get_main_keyboard())
                    continue

                # فتح قائمة إدارة الشعب
                if text in ["⚙️ إدارة الشعب المراقبة", "📋 الشعب المراقبة", "/list"]:
                    txt, kb = get_manage_keyboard()
                    send_telegram(txt, reply_markup=kb)

                # طلب فحص فوري
                elif text in ["🔍 فحص فوري", "🔍 فحص الشعب", "/check"]:
                    send_telegram("⏳ جاري فحص الشعب من بوابة الجامعة...")
                    try:
                        res = scrape_sections(is_auto=False)
                        send_telegram(f"📊 تقرير حالة الشعب:\n\n{res}", reply_markup=get_main_keyboard())
                    except Exception as e:
                        send_telegram(f"⚠️ حدث خطأ: {e}", reply_markup=get_main_keyboard())

                # إضافة شعبة
                elif text in ["➕ إضافة شعبة جديدة", "/add"]:
                    user_states[sender_id] = "WAITING_ADD"
                    send_telegram("✏️ أرسل الآن **رمز المقرر** و **رقم الشعبة** (بينهما مسافة):\n\nمثال:\n`3104 2481`")

                # المساعدة
                elif text in ["ℹ️ المساعدة", "/help", "/start"]:
                    help_txt = (
                        "🤖 *طريقة استخدام لوحة المراقبة:*\n\n"
                        "1️⃣ اضغط على *⚙️ إدارة الشعب المراقبة* لعرض كل الشعب بأزرار تحكم تفاعلية.\n"
                        "2️⃣ اضغط على اسم الشعبة للتبديل بين (🔔 مفعل) و (🔕 معطل).\n"
                        "3️⃣ اضغط على زر *🗑️ حذف* لحذف الشعبة نهائياً.\n"
                        "4️⃣ اضغط على *➕ إضافة شعبة جديدة* لإدخال أي مادة إضافية مباشرة."
                    )
                    send_telegram(help_txt, reply_markup=get_main_keyboard())

        time.sleep(2)

if __name__ == "__main__":
    main()
