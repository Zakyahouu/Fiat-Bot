"""
╔══════════════════════════════════════════════════════════════╗
║       FIAT PANDA ALGERIA — TELEGRAM MONITOR BOT              ║
║  Watches fiat.dz 24/7 · Alerts via Telegram · Auto-submits  ║
╚══════════════════════════════════════════════════════════════╝

HOW IT WORKS:
  - Every 30 seconds it checks 15+ URLs Fiat Algeria might use
    for the Panda inscription page
  - It also scans the fiat.dz homepage for any mention of "panda"
  - The moment it finds anything, it fires a Telegram alert
  - If AUTO_SUBMIT = True, it fills and submits the form for you

TELEGRAM COMMANDS:
  /start  → Get your Chat ID (required for setup) + confirm bot is alive
  /check  → Bot health: uptime, checks done, seconds until next check
  /panda  → View the last 3 scan reports
"""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import deque
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# ──────────────────────────────────────────────────────────────
#   STEP 1 — FILL IN YOUR DETAILS BEFORE RUNNING
# ──────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = "8711380327:AAEukOapJXvoRFXcdHXJNFI5qyfSICxxw_E"

# Add every Chat ID that should receive alerts.
# Each person sends /start to the bot — it replies with their ID.
# e.g. CHAT_IDS = [123456789, 987654321]
CHAT_IDS = [1088722186]

YOUR_INFO = {
    # ── Personal Info ─────────────────────────────────────────
    # Use French/Latin spelling — no Arabic script, the form won't accept it.
    # Note: the key names below (nom, prenom, etc.) must stay in French
    # because they are the actual HTML field names used by Fiat Algeria's forms.
    "nom":       "VOTRE_NOM",        # Family name in CAPS  (e.g. BENALI)
    "prenom":    "VotrePrenom",      # First name           (e.g. Mohamed)
    "email":     "votre@email.com",
    "telephone": "0555000000",       # Format: 05XXXXXXXX or 06XXXXXXXX or 07XXXXXXXX

    # Wilaya value must match EXACTLY one entry from the 58-wilaya list in README.md
    # Examples: "09 - Blida"  /  "16 - Alger"  /  "31 - Oran"
    "wilaya":    "09 - Blida",

    "ville":     "Blida",            # Free text city/town name

    # ── Client Type ───────────────────────────────────────────
    # "Particulier"    = private individual (most people use this)
    # "Professionnel"  = business / company
    "type_client": "Particulier",

    # ── Contact Consent ───────────────────────────────────────
    "contact_sms": True,
    "contact_tel": True,

    # ── Professional Fields ───────────────────────────────────
    # Only fill these if type_client = "Professionnel", otherwise leave empty
    "raison_sociale":    "",   # Company name
    "nif":               "",   # Tax ID number
    "registre_commerce": "",   # Business registration number
    "quantite":          "",   # Number of vehicles requested

    # ── Preferred Dealer ──────────────────────────────────────
    # Leave empty to use PA FIAT EL DJAZAIR as default,
    # or set one from the full dealer list in README.md
    "concessionnaire_preference": "PA FIAT EL DJAZAIR",
}

# ──────────────────────────────────────────────────────────────
#   STEP 2 — SETTINGS
# ──────────────────────────────────────────────────────────────

CHECK_INTERVAL_SECONDS = 30   # How often to check. Don't go below 15s.

AUTO_SUBMIT = True            # True  = detect + auto-fill + auto-submit the form
                              # False = detect + alert only (you fill it manually)

# ──────────────────────────────────────────────────────────────
#   URLS TO MONITOR
#   All patterns Fiat Algeria has used or is likely to use
# ──────────────────────────────────────────────────────────────

CANDIDATE_FORM_URLS = [
    "https://fiatdz.com/panda/",
    "https://fiatdz.com/fiat-panda/",
    "https://fiatdz.com/grande-panda/",
    "https://fiatdz.com/nouvelle-panda/",
    "https://fiatdz.com/new-panda/",
    "https://fiatdz.com/panda-inscription/",
    "https://fiatdz.com/inscrivez-vous-panda/",
    "https://fiatdz.com/inscrivez-vous-fiat-panda/",
    "https://fiatdz.com/inscrivez-vous-grande-panda/",
    "https://fiatdz.com/inscription-panda/",
    "https://fiatdz.com/reservation-panda/",
    "https://fiatdz.com/precommande-panda/",
    "https://www.fiat.dz/fr/models/panda",
    "https://www.fiat.dz/fr/models/grande-panda",
    "https://www.fiat.dz/fr/modeles/panda",
]

# Pages to scan for any mention of "panda"
PAGES_TO_SCAN = [
    "https://www.fiat.dz/fr",
    "https://fiatdz.com/",
]

PANDA_KEYWORDS = [
    "panda", "grande panda", "nouvelle panda",
    "new panda", "fiat panda",
]

# ──────────────────────────────────────────────────────────────
#   REFERENCE DATA
#   French values below are required by the actual Fiat DZ form —
#   they are exact dropdown values scraped from the live Doblo
#   inscription form. Do not translate them.
# ──────────────────────────────────────────────────────────────

# All 58 Algerian wilayas — exact values the form dropdown uses
ALL_WILAYAS = [
    "01 - Adrar", "02 - Chlef", "03 - Laghouat", "04 - Oum El Bouaghi",
    "05 - Batna", "06 - Béjaïa", "07 - Biskra", "08 - Béchar",
    "09 - Blida", "10 - Bouira", "11 - Tamanrasset", "12 - Tébessa",
    "13 - Tlemcen", "14 - Tiaret", "15 - Tizi Ouzou", "16 - Alger",
    "17 - Djelfa", "18 - Jijel", "19 - Sétif", "20 - Saïda",
    "21 - Skikda", "22 - Sidi Bel Abbès", "23 - Annaba", "24 - Guelma",
    "25 - Constantine", "26 - Médéa", "27 - Mostaganem", "28 - M'Sila",
    "29 - Mascara", "30 - Ouargla", "31 - Oran", "32 - El Bayadh",
    "33 - Illizi", "34 - Bordj Bou Arréridj", "35 - Boumerdès",
    "36 - El Tarf", "37 - Tindouf", "38 - Tissemsilt", "39 - El Oued",
    "40 - Khenchela", "41 - Souk Ahras", "42 - Tipaza", "43 - Mila",
    "44 - Aïn Defla", "45 - Naâma", "46 - Aïn Témouchent", "47 - Ghardaïa",
    "48 - Relizane", "49 - Timimoun", "50 - Bordj Badji Mokhtar",
    "51 - Ouled Djellal", "52 - Béni Abbès", "53 - In Salah",
    "54 - In Guezzam", "55 - Touggourt", "56 - Djanet",
    "57 - El M'Ghair", "58 - El Meniaa",
]

# All active Fiat Algeria dealers (scraped from live Doblo inscription form)
ALL_DEALERS = [
    "SARL ACC ALGERIAN CARS COMPANY", "SARL AGS AUTOMOBILES",
    "SARL ATLAS SPEED RACER AUTO", "SARL AUTO CITY",
    "SARL AUTO G", "EURL AUTOFIS CAR SERVICES", "SARL AUTOLYNA HOUSE",
    "SARL BARA AUTO CENTER", "SARL BENALIOUA SERVICE",
    "SARL BENFLIS MOTORS GROUP", "BENIA SERVICES AUTO",
    "EURL BENTOUATI CRAFT AUTO", "BOUDOUKHANA AUTO BIS",
    "SARL BOURBIA AUTOMOBILE", "SARL CEA HAMMOUCHE FRERES",
    "CENTER AUTOMOBILE TOUHAMI", "SARL CIRTA CARS",
    "SARL COMPTOIRE AUTOMOBILE", "SARL DOUADI AUTOMOTIVE",
    "Eurl EC AUTO", "SPA ELSECOM AUTOMOBILES", "SARL EQUINOX AUTO",
    "SARL ETIHAD AUTO", "GAMMA AUTO", "SARL GBM AUTO",
    "SARL GLOBAL AUTO VISION", "EURL GMS COMPANY", "SARL GROUPE NAOURI",
    "EURL GUICHENITI VEHICULES ET SERVICES", "EURL HAMMADI AUTO",
    "HALIL KOUBA", "HALIL KHAZROUN", "HALIL OULED YAICH", "EURL HERENCIA",
    "KECHKAR EL HADI", "SARL KHENIFI AUTO FOPC", "SARL KHERIF AUTO STAR",
    "EURL LAHCENE AUTOMOBILES", "SARL HALIL COMMERCE ET INDUSTRIE",
    "SARL MASCULA AUTO", "SARL MEDIUM AUTO", "SARL MOUSSOUS AUTO",
    "SARL ORLEANS AUTO", "EURL OULDLAKHDAR AUTOMOBILES",
    "EURL PCDM", "EURL SAIDA", "SARL SADAREP", "SARL SIADS",
    "SNC TAHER AUTO PIECES ABDELAZIZ", "SARL SOVAM AUTO",
    "SPA STELLANTIS EL DJAZAIR", "SARL TALHA AUTO EUCALYPTUS",
    "TAHER AUTO PIECES ABDELAZIZ", "SARL TRANS LOC MAIN",
    "EURL AUTO", "UNION KABOUYA", "EURL VYK MOTORS EXPRESS",
    "SARL VOLK AUTO", "SARL ZELMAT AUTOMOBILES", "PA FIAT EL DJAZAIR",
]

# ──────────────────────────────────────────────────────────────
#   INTERNAL STATE
# ──────────────────────────────────────────────────────────────

scan_reports   = deque(maxlen=3)
bot_start_time = datetime.now()
panda_found    = False
found_url      = None
check_count    = 0
last_check_ts  = None

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-DZ,fr;q=0.9,ar;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ──────────────────────────────────────────────────────────────
#   TELEGRAM HELPER
# ──────────────────────────────────────────────────────────────

async def tg_send(bot: Bot, text: str):
    if not CHAT_IDS:
        log.warning("CHAT_IDS is empty — Telegram message skipped.")
        return
    for cid in CHAT_IDS:
        try:
            await bot.send_message(chat_id=cid, text=text, parse_mode="HTML")
        except Exception as e:
            log.error(f"Telegram send to {cid} failed: {e}")

# ──────────────────────────────────────────────────────────────
#   TELEGRAM COMMANDS
# ──────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — replies with the user's Chat ID.
    Paste that ID into CHAT_ID above, then redeploy.
    """
    cid   = update.effective_chat.id
    uname = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"👋 Hey {uname}! The bot is online.\n\n"
        f"📋 Your <b>Chat ID</b> is:\n"
        f"<code>{cid}</code>\n\n"
        f"Copy that number and paste it into the script:\n"
        f"<code>CHAT_ID = {cid}</code>\n\n"
        f"Then redeploy and you're all set.\n\n"
        f"Commands:\n"
        f"/check — bot status and uptime\n"
        f"/panda — last 3 scan reports",
        parse_mode="HTML"
    )

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /check — shows bot health: uptime, checks done, last check time, next check ETA.
    """
    uptime   = str(datetime.now() - bot_start_time).split(".")[0]
    last_chk = last_check_ts.strftime("%H:%M:%S") if last_check_ts else "not yet"
    secs_ago = int((datetime.now() - last_check_ts).total_seconds()) if last_check_ts else 0
    next_chk = max(0, CHECK_INTERVAL_SECONDS - secs_ago)

    status = f"🎉 PANDA FOUND!\n🔗 {found_url}" if panda_found else "🔍 Monitoring active — nothing found yet."

    await update.message.reply_text(
        f"📊 <b>Bot Status</b>\n\n"
        f"⏱ Uptime:         <b>{uptime}</b>\n"
        f"🔄 Total checks:  <b>{check_count}</b>\n"
        f"🕐 Last check:    <b>{last_chk}</b>\n"
        f"⏳ Next check in: <b>~{next_chk}s</b>\n"
        f"📡 Interval:      <b>{CHECK_INTERVAL_SECONDS}s</b>\n\n"
        f"📌 <b>Status:</b>\n{status}",
        parse_mode="HTML"
    )

async def cmd_panda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /panda — shows the last 3 scan reports.
    """
    if not scan_reports:
        await update.message.reply_text("📂 No reports yet — bot just started.", parse_mode="HTML")
        return

    text = "📋 <b>Last 3 Scan Reports</b>\n\n"
    for i, report in enumerate(reversed(scan_reports), 1):
        text += f"━━━ Report #{i} ━━━\n{report}\n\n"

    await update.message.reply_text(text, parse_mode="HTML")

# ──────────────────────────────────────────────────────────────
#   FORM SUBMISSION
#   Fiat DZ uses WordPress Contact Form 7 (CF7) — confirmed on
#   the live Doblo inscription page at fiatdz.com.
# ──────────────────────────────────────────────────────────────

def extract_cf7_fields(page_html: str):
    """
    Parse the inscription page to find CF7's hidden system fields
    and the names of all visible form inputs.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    cf7_id = unit_tag = container_post = ""

    for inp in soup.find_all("input", {"type": "hidden"}):
        name = inp.get("name", "")
        val  = inp.get("value", "")
        if   name == "_wpcf7":                cf7_id = val
        elif name == "_wpcf7_unit_tag":        unit_tag = val
        elif name == "_wpcf7_container_post":  container_post = val

    field_names = {
        tag.get("name", "")
        for tag in soup.find_all(["input", "select", "textarea"])
        if tag.get("name", "") and not tag.get("name", "").startswith("_wpcf7")
    }

    return cf7_id, unit_tag, container_post, field_names


def build_form_payload(cf7_id, unit_tag, container_post, field_names):
    """
    Build the POST payload.
    The field names and dropdown values below are in French because
    they are the actual HTML field names and option values used by
    Fiat Algeria's forms — changing them would break submission.
    """
    info   = YOUR_INFO
    dealer = info.get("concessionnaire_preference", "") or ALL_DEALERS[-1]

    # Contact consent values — must match the form's option text exactly
    contact_options = []
    if info.get("contact_sms"): contact_options.append("Par SMS")
    if info.get("contact_tel"): contact_options.append("Par telephone")

    # We send all known field name variants.
    # CF7 silently ignores fields it doesn't recognise, so this is safe.
    base = {
        # CF7 system fields — required, never change these
        "_wpcf7":                str(cf7_id),
        "_wpcf7_version":        "5.9",
        "_wpcf7_locale":         "fr_FR",
        "_wpcf7_unit_tag":       str(unit_tag),
        "_wpcf7_container_post": str(container_post),

        # Personal info — multiple field name variants to cover all form layouts
        "your-type":             info["type_client"],
        "type":                  info["type_client"],
        "your-nom":              info["nom"],
        "nom":                   info["nom"],
        "your-prenom":           info["prenom"],
        "prenom":                info["prenom"],
        "your-email":            info["email"],
        "email":                 info["email"],
        "your-phone":            info["telephone"],
        "your-telephone":        info["telephone"],
        "telephone":             info["telephone"],
        "phone":                 info["telephone"],
        "your-ville":            info["ville"],
        "ville":                 info["ville"],
        "your-wilaya":           info["wilaya"],
        "wilaya":                info["wilaya"],
        "your-modele":           "FIAT GRANDE PANDA",
        "modele":                "FIAT GRANDE PANDA",
        "your-concessionnaire":  dealer,
        "concessionnaire":       dealer,

        # Contact consent checkboxes
        "your-contact":          contact_options,
        "contact":               contact_options,
        "autorisation":          ["Par SMS", "Par telephone"],

        # Professional fields (empty strings are harmless for Particulier)
        "raison-sociale":        info.get("raison_sociale", ""),
        "raison_sociale":        info.get("raison_sociale", ""),
        "nif":                   info.get("nif", ""),
        "your-nif":              info.get("nif", ""),
        "registre-commerce":     info.get("registre_commerce", ""),
        "quantite":              info.get("quantite", ""),

        # Consent checkbox — covered under multiple possible field names
        "acceptance":            "on",
        "your-acceptance":       "on",
        "rgpd":                  "on",
        "consentement":          "on",
    }

    # Filter to only fields that actually exist on this form (if we could read them)
    if field_names:
        filtered = {k: v for k, v in base.items() if k in field_names}
        for key in ["_wpcf7", "_wpcf7_version", "_wpcf7_locale",
                    "_wpcf7_unit_tag", "_wpcf7_container_post"]:
            filtered[key] = base[key]
        return filtered

    return base


def try_submit_form(url: str, page_html: str) -> tuple[bool, str]:
    """
    Submit the form via HTTP POST.
    Tries the CF7 REST API first, then falls back to a direct POST.
    Returns (success: bool, message: str).
    """
    try:
        cf7_id, unit_tag, container_post, field_names = extract_cf7_fields(page_html)
        log.info(f"CF7 form — ID: {cf7_id} | Fields detected: {field_names}")

        payload = build_form_payload(cf7_id, unit_tag, container_post, field_names)

        submit_headers = {
            **HEADERS,
            "Content-Type":      "application/x-www-form-urlencoded",
            "Referer":           url,
            "Origin":            "https://" + url.split("/")[2],
            "X-Requested-With":  "XMLHttpRequest",
        }

        # Attempt 1 — CF7 REST API (cleaner, works on CF7 v5+)
        if cf7_id:
            rest_url = f"https://{url.split('/')[2]}/wp-json/contact-form-7/v1/contact-forms/{cf7_id}/feedback"
            try:
                r    = requests.post(rest_url, data=payload, headers=submit_headers, timeout=15)
                data = r.json()
                if data.get("status") == "mail_sent":
                    return True, f"Submitted successfully via REST API.\nServer: {data.get('message', '')}"
            except Exception as e:
                log.warning(f"REST API attempt failed: {e}")

        # Attempt 2 — Direct POST to the page URL
        r          = requests.post(url, data=payload, headers=submit_headers, timeout=15)
        page_lower = r.text.lower()

        # These success strings come from the real Fiat DZ confirmation page
        # (scraped from the live Doblo form — kept as-is for matching)
        success_signals = [
            "votre demande a bien",
            "طلبكم مسجل بنجاح",
            "enregistrée",
            "mail_sent",
        ]
        if any(sig in page_lower for sig in success_signals):
            return True, "Registration submitted successfully! Check your email for confirmation."
        else:
            return False, f"Form sent but response was unclear (HTTP {r.status_code}). Please verify manually."

    except Exception as e:
        return False, f"Submission error: {e}"

# ──────────────────────────────────────────────────────────────
#   DETECTION LOGIC
# ──────────────────────────────────────────────────────────────

def check_url_for_form(url: str) -> tuple[bool, str | None]:
    """
    Check if a URL is a live inscription page (has a form + relevant content).
    Returns (is_live, page_html or None).
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return False, None
        text         = r.text.lower()
        has_form     = "<form" in text
        has_content  = any(kw in text for kw in [
            "inscri", "panda", "envoyer ma demande", "contact form", "commander"
        ])
        return (True, r.text) if (has_form and has_content) else (False, None)
    except Exception:
        return False, None


def scan_page_for_panda(url: str) -> tuple[bool, list, str]:
    """
    Scan a page for any mention of 'panda' in visible text and extract related links.
    <script>/<style> blocks are stripped first to avoid false positives from static
    JS model lists (e.g. "FIAT PANDA MY 03" in the brands object) and data-* tracking
    attributes (e.g. data-adobe-linktype="content-range:showroom:panda" on other cars).
    Returns (keyword_found, panda_links, summary_string).
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return False, [], f"HTTP {r.status_code}"

        soup = BeautifulSoup(r.text, "html.parser")

        # Remove script and style tags before any text search — panda references
        # inside JS/CSS are static site infrastructure, not registration signals.
        for tag in soup(["script", "style"]):
            tag.decompose()

        visible_text   = soup.get_text(" ", strip=True).lower()
        found_keywords = [kw for kw in PANDA_KEYWORDS if kw in visible_text]

        # Only collect links whose actual href URL contains "panda" —
        # ignores data-* tracking attributes that may mention "panda" for other pages.
        panda_links = []
        if found_keywords:
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "panda" in href.lower():
                    full = href if href.startswith("http") else "https://www.fiat.dz" + href
                    panda_links.append(full)

        summary = f"Keywords found: {found_keywords}" if found_keywords else "Nothing found"
        return bool(found_keywords), panda_links, summary

    except Exception as e:
        return False, [], f"Error: {e}"

# ──────────────────────────────────────────────────────────────
#   ON PANDA FOUND
# ──────────────────────────────────────────────────────────────

async def on_panda_found(bot: Bot, url: str, page_html: str):
    global panda_found, found_url
    panda_found = True
    found_url   = url
    ts = datetime.now().strftime("%H:%M:%S — %d/%m/%Y")

    log.info(f"PANDA FOUND at {url}")

    await tg_send(bot,
        f"🚨🚨🚨 <b>FIAT PANDA REGISTRATION IS OPEN!</b> 🚨🚨🚨\n\n"
        f"⏰ Detected at: <b>{ts}</b>\n"
        f"🔗 URL: {url}\n\n"
        f"{'🤖 Auto-submitting your registration now...' if AUTO_SUBMIT else '⚡ Open the link and register NOW!'}"
    )

    if AUTO_SUBMIT:
        success, result = try_submit_form(url, page_html)
        await tg_send(bot,
            f"{'✅' if success else '⚠️'} <b>Submission Result:</b>\n\n"
            f"{result}\n\n"
            f"🔗 Direct link: {url}\n\n"
            f"<b>Info used:</b>\n"
            f"👤 {YOUR_INFO['prenom']} {YOUR_INFO['nom']}\n"
            f"📧 {YOUR_INFO['email']}\n"
            f"📞 {YOUR_INFO['telephone']}\n"
            f"📍 {YOUR_INFO['wilaya']} — {YOUR_INFO['ville']}"
        )
        if not success:
            await tg_send(bot, f"⚡ Auto-submit failed. Register manually RIGHT NOW:\n{url}")
    else:
        await tg_send(bot,
            f"📋 <b>Your info ready to paste:</b>\n\n"
            f"Family name: <code>{YOUR_INFO['nom']}</code>\n"
            f"First name:  <code>{YOUR_INFO['prenom']}</code>\n"
            f"Email:       <code>{YOUR_INFO['email']}</code>\n"
            f"Phone:       <code>{YOUR_INFO['telephone']}</code>\n"
            f"Wilaya:      <code>{YOUR_INFO['wilaya']}</code>\n"
            f"City:        <code>{YOUR_INFO['ville']}</code>\n\n"
            f"🔗 {url}"
        )

# ──────────────────────────────────────────────────────────────
#   MONITORING JOB
# ──────────────────────────────────────────────────────────────

async def monitoring_job(context: ContextTypes.DEFAULT_TYPE):
    global check_count, last_check_ts

    if panda_found:
        return

    check_count  += 1
    last_check_ts = datetime.now()
    ts            = last_check_ts.strftime("%H:%M:%S")
    report        = [f"Check #{check_count} — {ts}"]
    spotted       = False

    # Step 1: Probe all candidate inscription URLs directly
    for url in CANDIDATE_FORM_URLS:
        is_live, html = check_url_for_form(url)
        if is_live:
            report.append(f"LIVE FORM: {url}")
            scan_reports.append("\n".join(report))
            await on_panda_found(context.bot, url, html)
            return

    # Step 2: Scan main pages for keyword mentions
    for page_url in PAGES_TO_SCAN:
        found, links, summary = scan_page_for_panda(page_url)
        domain = page_url.split("/")[2]

        if found:
            spotted = True
            report.append(f"⚠️ Panda mentioned on {domain}")
            report.append(f"   {summary}")
            if links:
                report.append(f"   Links: {', '.join(links[:3])}")
                for link in links:
                    is_live, html = check_url_for_form(link)
                    if is_live:
                        scan_reports.append("\n".join(report))
                        await on_panda_found(context.bot, link, html)
                        return
        else:
            report.append(f"✅ {domain} — nothing found")

    if spotted:
        report.append("No form yet — but something appeared. Staying alert.")
        await tg_send(
            context.bot,
            "👀 <b>Panda keyword appeared on fiat.dz!</b>\n\n" + "\n".join(report[1:])
        )
    else:
        report.append("All clear.")

    scan_reports.append("\n".join(report))
    log.info(f"Check #{check_count} done — {'KEYWORD SPOTTED' if spotted else 'nothing'}")

# ──────────────────────────────────────────────────────────────
#   STARTUP
# ──────────────────────────────────────────────────────────────

async def post_init(application: Application):
    if CHAT_IDS:
        await tg_send(
            application.bot,
            f"🚀 <b>Bot is online!</b>\n\n"
            f"📡 Checking every <b>{CHECK_INTERVAL_SECONDS}s</b>\n"
            f"🎯 Mode: <b>{'Auto-submit ON' if AUTO_SUBMIT else 'Alert only'}</b>\n"
            f"👤 Registered for: <b>{YOUR_INFO['prenom']} {YOUR_INFO['nom']}</b>\n"
            f"📍 <b>{YOUR_INFO['wilaya']}</b>\n\n"
            f"Commands: /check · /panda"
        )

# ──────────────────────────────────────────────────────────────
#   MAIN
# ──────────────────────────────────────────────────────────────

def main():
    log.info("Starting Fiat Panda Algeria Bot...")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("panda", cmd_panda))

    app.job_queue.run_repeating(
        monitoring_job,
        interval=CHECK_INTERVAL_SECONDS,
        first=5,
    )

    log.info(f"Running — checking every {CHECK_INTERVAL_SECONDS}s")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
