import os
import time
import json
import base64
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

URL = "https://eserve.psau.edu.sa/ku/ui/guest/timetable/index/scheduleTreeCoursesIndex.faces"

# 1. بيانات GitHub للربط والتعديل التلقائي
GITHUB_TOKEN = "Ghp_coiiilKtBOgFyBUMryGMgqARsBMwDC1Waipz"
GITHUB_REPO = "ah3ah3/-psau-section-monitor"
GITHUB_FILE_PATH = "targets.json"

# 2. بيانات التيليجرام
TELEGRAM_BOT_TOKEN = "8888125988:AAHOC7yNdnsQx-gloVDsID33UvYCvs-qH1A"
TELEGRAM_CHAT_ID = "1163844992"

CHECK_INTERVAL_MINUTES = 3
browser_lock = threading.Lock()
data_lock = threading.Lock()
user_wizard = {}

DEFAULT_TARGETS = [
    {"code": "3104", "section": "2481", "active": True},
    {"code": "3101", "section": "2512", "active": True},
    {"code": "3201", "section": "2494", "active": True},
]

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"PSAU Monitor running with GitHub Sync")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def get_github_file():
    """جلب محتوى و SHA ملف targets.json من GitHub API"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PSAU-Monitor-Bot"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content), data["sha"]
    except Exception as e:
        print(f"⚠️ فشل القراءة من GitHub: {e}")
        return None, None

def load_targets():
    """قراءة الشعب من GitHub مباشرة"""
    with data_lock:
        targets, _ = get_github_file()
        if targets:
            return targets
        return DEFAULT_TARGETS

def save_targets(new_targets):
    """تعديل وحفظ الملف في GitHub مباشرة بعمل Commit"""
    with data_lock:
        _, sha = get_github_file()
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        
        json_str = json.dumps(new_targets, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        payload = {
            "message": "Auto-update targets from Telegram Bot",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "PSAU-Monitor-Bot",
                "Content-Type": "application/json"
            },
            method="PUT"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                print("✅ تم حفظ التعديلات في GitHub بنجاح!")
                return True
        except Exception as e:
            print(f"⚠️ فشل الحفظ في GitHub: {e}")
            return False

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
        payload = {"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id, "text": text}
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
        text = "📭 لا توجد أي شعب مضافة للمراقبة حالياً.\nاضغط على الزر بالأسفل لإضافة مادة."
    else:
        text = (
            "📋 *قائمة الشعب المسجلة في المراقبة:*\n\n"
            "• اضغط على اسم الشعبة للتبديل بين (🔔 مفعل) و (🔕 معطل).\n"
            "• اضغط على 🗑️ لحذف الشعبة نهائياً من GitHub:"
        )
        for t in targets:
            sec = t["section"]
            code = t["code"]
            is_active = t.get("active", True)
            status_btn = f"🔔 مادة {code} (شعبة {sec})" if is_active else f"🔕 مادة {code} (شعبة {sec}) - موقف"
            inline_keyboard.append([
                {"text": status_btn, "callback_data": f"toggle_{sec}"},
                {"text": f"🗑️ حذف {sec}", "callback_data": f"del_{sec}"}
            ])

    inline_keyboard.append([
        {"text": "➕ إضافة شعبة جديدة", "callback_data": "btn_add"},
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
                    report.append(f"⚠️ مادة {code} (شعبة {sec}) لم تظهر في نتائج البحث.")

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
        "🤖 البوت متصل الآن بنظام المزامنة المباشرة مع GitHub!\n"
        "جميع التعديلات (إضافة/حذف/إيقاف تنبيه) يتم حفظها تلقائياً داخل مستودعك في GitHub.",
        reply_markup=get_main_keyboard()
    )

    initial_updates = get_updates()
    last_update_id = initial_updates[-1]["update_id"] + 1 if initial_updates else None

    while True:
        updates = get_updates(last_update_id)
        for update in updates:
            last_update_id = update["update_id"] + 1

            if "callback_query" in update:
                cq = update["callback_query"]
                cq_id = cq["id"]
                data = cq.get("data", "")
                msg = cq.get("message", {})
                msg_id = msg.get("message_id")

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

                elif data.startswith("del_"):
                    sec_to_del = data.replace("del_", "")
                    targets = load_targets()
                    new_targets = [t for t in targets if t["section"] != sec_to_del]
                    save_targets(new_targets)
                    answer_callback(cq_id, f"🗑️ تم حذف الشعبة {sec_to_del}")
                    txt, kb = get_manage_keyboard()
                    edit_telegram_message(msg_id, txt, kb)

                elif data == "btn_add":
                    user_wizard[TELEGRAM_CHAT_ID] = {"step": "WAITING_CODE"}
                    answer_callback(cq_id)
                    send_telegram(
                        "📝 *الخطوة (1 من 2): رمز المقرر*\n\n"
                        "أرسل **رمز المادة** فقط (مثال: `3104` أو `3201`).\n\n"
                        "*(أرسل كلمة `إلغاء` في أي وقت للتراجع)*"
                    )

                elif data == "btn_check":
                    answer_callback(cq_id, "⏳ جاري الفحص...")
                    send_telegram("⏳ جاري فحص الشعب الآن من بوابة الجامعة...")
                    try:
                        res = scrape_sections(is_auto=False)
                        send_telegram(f"📊 تقرير حالة الشعب:\n\n{res}")
                    except Exception as e:
                        send_telegram(f"⚠️ حدث خطأ: {e}")
                continue

            if "message" in update:
                message = update["message"]
                sender_id = str(message.get("from", {}).get("id", ""))
                text = message.get("text", "").strip()

                if sender_id != TELEGRAM_CHAT_ID:
                    continue

                if text in ["إلغاء", "/cancel"]:
                    user_wizard[sender_id] = None
                    send_telegram("❌ تم إلغاء العملية.", reply_markup=get_main_keyboard())
                    continue

                wizard_state = user_wizard.get(sender_id)
                if wizard_state:
                    step = wizard_state.get("step")
                    if step == "WAITING_CODE":
                        code_entered = text.strip()
                        user_wizard[sender_id] = {"step": "WAITING_SECTION", "code": code_entered}
                        send_telegram(
                            f"✅ تم حفظ رمز المقرر: `{code_entered}`\n\n"
                            f"📝 *الخطوة (2 من 2): رقم الشعبة*\n\n"
                            f"الآن أرسل **رقم الشعبة** (مثال: `2481` أو `2512`)."
                        )
                        continue

                    elif step == "WAITING_SECTION":
                        sec_entered = text.strip()
                        code_entered = wizard_state.get("code")
                        user_wizard[sender_id] = None

                        targets = load_targets()
                        if any(t["section"] == sec_entered for t in targets):
                            send_telegram(f"⚠️ الشعبة `{sec_entered}` موجودة مسبقاً في القائمة!", reply_markup=get_main_keyboard())
                        else:
                            targets.append({"code": code_entered, "section": sec_entered, "active": True})
                            save_targets(targets)
                            send_telegram(
                                f"🎉 **تمت الإضافة وحفظها في GitHub بنجاح!**\n\n"
                                f"📚 المقرر: `{code_entered}`\n"
                                f"🔢 الشعبة: `{sec_entered}`\n"
                                f"🔔 التنبيه التلقائي: مفعل فوراً",
                                reply_markup=get_main_keyboard()
                            )
                            txt, kb = get_manage_keyboard()
                            send_telegram(txt, reply_markup=kb)
                        continue

                if text in ["⚙️ إدارة الشعب المراقبة", "📋 الشعب المراقبة", "/list"]:
                    txt, kb = get_manage_keyboard()
                    send_telegram(txt, reply_markup=kb)

                elif text in ["🔍 فحص فوري", "🔍 فحص الشعب", "/check"]:
                    send_telegram("⏳ جاري فحص الشعب الآن من بوابة الجامعة...")
                    try:
                        res = scrape_sections(is_auto=False)
                        send_telegram(f"📊 تقرير حالة الشعب:\n\n{res}", reply_markup=get_main_keyboard())
                    except Exception as e:
                        send_telegram(f"⚠️ حدث خطأ: {e}", reply_markup=get_main_keyboard())

                elif text in ["➕ إضافة شعبة جديدة", "/add"]:
                    user_wizard[sender_id] = {"step": "WAITING_CODE"}
                    send_telegram(
                        "📝 *الخطوة (1 من 2): رمز المقرر*\n\n"
                        "أرسل **رمز المادة** فقط (مثال: `3104` أو `3201`).\n\n"
                        "*(أرسل كلمة `إلغاء` في أي وقت للتراجع)*"
                    )

                elif text in ["ℹ️ المساعدة", "/help", "/start"]:
                    help_txt = (
                        "📌 *دليل استخدام البوت:*\n\n"
                        "1️⃣ **إدارة الشعب المراقبة:** للتحكم بالشعب والتبديل بين التفعيل والإيقاف أو الحذف بضغطة زر.\n"
                        "2️⃣ **إضافة شعبة جديدة:** يسألك البوت خطوة بخطوة عن رمز المادة ثم رقم الشعبة.\n"
                        "3️⃣ **فحص فوري:** لفحص حالة كافة المواد الآن.\n\n"
                        "💡 *ملاحظة:* جميع التعديلات تُحفظ فوراً في مستودع GitHub."
                    )
                    send_telegram(help_txt, reply_markup=get_main_keyboard())

        time.sleep(2)

if __name__ == "__main__":
    main()
