"""
Bewerbungs-Automatisierung: E-Mail → Engel & Völkers Formular
"""
import imaplib
import email
import email.header
import io
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.policy import default as email_default_policy
from pathlib import Path

import requests
from dotenv import load_dotenv
from fpdf import FPDF
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Config laden ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
FILTERS_FILE = BASE_DIR / "filters.json"
PROCESSED_DB = BASE_DIR / "processed_emails.json"
DOWNLOAD_DIR = BASE_DIR / "downloads"
LOG_FILE = BASE_DIR / "automation.log"

load_dotenv(BASE_DIR / ".env")

with open(CONFIG_FILE, encoding="utf-8") as f:
    CFG = json.load(f)

with open(FILTERS_FILE, encoding="utf-8") as f:
    _filters_cfg = json.load(f)
_active_profile = _filters_cfg["active"]
FILTER = _filters_cfg["profiles"][_active_profile]

# .env überschreibt config.json für IMAP-Zugangsdaten
if os.getenv("IMAP_SERVER"):
    CFG["imap"]["server"] = os.getenv("IMAP_SERVER")
if os.getenv("IMAP_PORT"):
    CFG["imap"]["port"] = int(os.getenv("IMAP_PORT"))
if os.getenv("IMAP_USE_SSL"):
    CFG["imap"]["use_ssl"] = os.getenv("IMAP_USE_SSL", "true").lower() == "true"
if os.getenv("IMAP_USERNAME"):
    CFG["imap"]["username"] = os.getenv("IMAP_USERNAME")
if os.getenv("IMAP_PASSWORD"):
    CFG["imap"]["password"] = os.getenv("IMAP_PASSWORD")
if os.getenv("IMAP_MAILBOX"):
    CFG["imap"]["mailbox"] = os.getenv("IMAP_MAILBOX")

DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

DOWNLOAD_DIR.mkdir(exist_ok=True)

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")),
    ],
)
log = logging.getLogger(__name__)

# ── Processed-E-Mails-DB ────────────────────────────────────────────────────

def load_processed() -> set:
    if PROCESSED_DB.exists():
        with open(PROCESSED_DB, encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_processed(ids: set):
    with open(PROCESSED_DB, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)

# ── IMAP ────────────────────────────────────────────────────────────────────

def fetch_new_emails() -> list[dict]:
    """Holt neue Bewerbungs-E-Mails vom IMAP-Server."""
    cfg = CFG["imap"]
    log.info(f"Verbinde mit IMAP {cfg['server']}:{cfg['port']} ...")

    if cfg["use_ssl"]:
        conn = imaplib.IMAP4_SSL(cfg["server"], cfg["port"])
    else:
        conn = imaplib.IMAP4(cfg["server"], cfg["port"])

    conn.login(cfg["username"], cfg["password"])
    conn.select(cfg["mailbox"])

    # Aktiven Filter aus filters.json laden
    keywords    = FILTER.get("subject_keywords", [])
    date_after  = FILTER.get("date_after", "")
    batch_size  = FILTER.get("batch_size", 10)

    # IMAP-Suche: alle keywords müssen im Betreff vorkommen (AND)
    search_criteria = " ".join(f'SUBJECT "{kw}"' for kw in keywords)
    if date_after:
        # IMAP erwartet Datum als DD-Mon-YYYY (z.B. 27-Mar-2026)
        from datetime import datetime as dt
        d = dt.strptime(date_after, "%Y-%m-%d")
        imap_date = d.strftime("%d-%b-%Y")
        search_criteria += f' SINCE "{imap_date}"'

    _, data = conn.search(None, search_criteria)
    msg_ids = data[0].split()
    log.info(f"{len(msg_ids)} E-Mail(s) gefunden (Profil: '{_active_profile}', Filter: {keywords}{', ab: ' + date_after if date_after else ''}).")

    processed = load_processed()
    results = []

    for mid in msg_ids:
        uid = mid.decode()
        if uid in processed:
            continue

        if len(results) >= batch_size:
            log.info(f"  Batch-Limit erreicht ({batch_size}) — restliche E-Mails beim nächsten Lauf.")
            break

        _, msg_data = conn.fetch(mid, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw, policy=email_default_policy)

        subject = decode_header_str(msg.get("Subject", ""))
        sender  = msg.get("From", "")
        date    = msg.get("Date", "")

        body = extract_body(msg)

        results.append({
            "uid":     uid,
            "subject": subject,
            "sender":  sender,
            "date":    date,
            "body":    body,
        })
        log.info(f"  [{uid}] Neu: {subject[:80]}")

    conn.logout()
    return results

def decode_header_str(value: str) -> str:
    parts = email.header.decode_header(value)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return "".join(decoded)

def extract_body(msg) -> str:
    """Extrahiert den Plaintext-Body einer E-Mail."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                return part.get_content()
    else:
        if msg.get_content_type() == "text/plain":
            return msg.get_content()
        # Fallback HTML → Text
        return re.sub(r"<[^>]+>", "", msg.get_content())
    return ""

# ── E-Mail parsen ────────────────────────────────────────────────────────────

FIELD_PATTERNS = {
    "name":       r"(?:Name|Bewerber)[:\s]+([^\n\r]+)",
    "email":      r"E[-\s]?Mail[:\s]+([^\n\r\s]+@[^\n\r\s]+)",
    "phone":      r"(?:Telefon|Tel\.?|Phone)[:\s]+([^\n\r]+)",
    "zip":        r"(?:Postleitzahl|PLZ)[:\s]+([^\n\r]+)",
    "motivation": r"(?:Motivationstext|Motivation|Nachricht|Anschreiben)[:\s]+([\s\S]+?)(?=\n(?:Hochgeladener|Name|E-Mail|Telefon|Postleitzahl|Mit freundlichen|SocialTalents)|\Z)",
    "cv_url":     r"(?:Hochgeladener Lebenslauf|Lebenslauf)[^\n]*?(?:Hier ansehen|hier ansehen|ansehen)\s*[:<\s]*([https?://][^\s>\"]+)",
}

def parse_email(subject: str, body: str) -> dict:
    """Extrahiert strukturierte Bewerbungsdaten aus Betreff + Body."""
    data = {}

    # Name aus Betreff: "Bewerbung von Max Mustermann via SocialTalents als ..."
    m = re.search(r"Bewerbung von (.+?) via SocialTalents", subject)
    if m:
        full_name = m.group(1).strip()
        parts = full_name.split()
        data["first_name"] = parts[0]
        data["last_name"]  = " ".join(parts[1:]) if len(parts) > 1 else ""
    else:
        data["first_name"] = ""
        data["last_name"]  = ""

    # Position/Ort aus Betreff
    m = re.search(r"als (.+?)(?:\s*\(|$)", subject)
    data["position"] = m.group(1).strip() if m else ""

    # Felder aus Body
    for key, pattern in FIELD_PATTERNS.items():
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Falls Name im Body steht und wir noch keinen haben
            if key == "name" and not data.get("first_name"):
                parts = val.split()
                data["first_name"] = parts[0]
                data["last_name"]  = " ".join(parts[1:]) if len(parts) > 1 else ""
            else:
                data[key] = val
        elif key not in data:
            data[key] = ""

    # E-Mail auch direkt per Regex suchen
    if not data.get("email"):
        m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", body)
        data["email"] = m.group(0) if m else ""

    # CV-Link: einfacher URL-Scan als Fallback
    if not data.get("cv_url"):
        urls = re.findall(r"https?://[^\s<>\"']+", body)
        for url in urls:
            if any(kw in url.lower() for kw in ["lebenslauf", "cv", "resume", "file", "upload", "download"]):
                data["cv_url"] = url
                break
        if not data.get("cv_url") and urls:
            data["cv_url"] = urls[-1]  # letzter URL als Fallback

    # Telefon-Prefix ermitteln
    phone_raw = data.get("phone", "")
    if phone_raw.startswith("+49") or phone_raw.startswith("0049"):
        data["dial_code"] = "+49"
        data["phone_number"] = re.sub(r"^\+49|^0049", "", phone_raw).strip()
    elif phone_raw.startswith("+43"):
        data["dial_code"] = "+43"
        data["phone_number"] = re.sub(r"^\+43", "", phone_raw).strip()
    elif phone_raw.startswith("+41"):
        data["dial_code"] = "+41"
        data["phone_number"] = re.sub(r"^\+41", "", phone_raw).strip()
    else:
        data["dial_code"] = "+49"
        data["phone_number"] = phone_raw

    log.info(f"  Geparste Daten: {json.dumps({k:v for k,v in data.items() if k != 'motivation'}, ensure_ascii=False)}")
    return data

# ── Datei-Download ───────────────────────────────────────────────────────────

def download_cv(cv_url: str, applicant_name: str) -> Path | None:
    """Folgt Weiterleitungen und lädt den Lebenslauf herunter."""
    if not cv_url:
        log.warning("Kein CV-Link vorhanden.")
        return None

    safe_name = re.sub(r"[^\w\-]", "_", applicant_name)
    log.info(f"Lade CV von: {cv_url}")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(cv_url, headers=headers, allow_redirects=True, timeout=30)
        resp.raise_for_status()

        # Dateiendung ermitteln
        ct = resp.headers.get("Content-Type", "")
        ext = ".pdf"
        if "pdf" in ct:
            ext = ".pdf"
        elif "word" in ct or "docx" in ct:
            ext = ".docx"
        elif "doc" in ct:
            ext = ".doc"
        elif "png" in ct:
            ext = ".png"
        elif "jpeg" in ct or "jpg" in ct:
            ext = ".jpg"
        else:
            # Aus URL ermitteln
            url_path = cv_url.split("?")[0]
            if "." in url_path.split("/")[-1]:
                ext = "." + url_path.split(".")[-1][:5]

        out_path = DOWNLOAD_DIR / f"CV_{safe_name}{ext}"
        with open(out_path, "wb") as f:
            f.write(resp.content)
        log.info(f"  CV gespeichert: {out_path} ({len(resp.content)//1024} KB)")
        return out_path

    except Exception as e:
        log.error(f"CV-Download fehlgeschlagen: {e}")
        return None

# ── PDF-Erstellung ───────────────────────────────────────────────────────────

def create_email_pdf(subject: str, body: str, data: dict, applicant_name: str) -> Path:
    """Erstellt eine PDF-Datei aus dem E-Mail-Inhalt."""
    safe_name = re.sub(r"[^\w\-]", "_", applicant_name)
    out_path = DOWNLOAD_DIR / f"Bewerbung_{safe_name}.pdf"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Titel
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Bewerbungsunterlagen", ln=True, align="C")
    pdf.ln(5)

    # Metadaten
    pdf.set_font("Helvetica", "", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 6, f"Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, fill=True)
    pdf.ln(5)

    # Betreff
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Betreff:", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, subject)
    pdf.ln(3)

    # Strukturierte Daten
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Bewerberdaten:", ln=True)
    pdf.set_font("Helvetica", "", 11)

    fields = [
        ("Name",         f"{data.get('first_name','')} {data.get('last_name','')}".strip()),
        ("E-Mail",        data.get("email", "")),
        ("Telefon",       data.get("phone", "")),
        ("Postleitzahl",  data.get("zip", "")),
        ("Position",      data.get("position", "")),
        ("CV-Link",       data.get("cv_url", "")),
    ]
    for label, value in fields:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, f"{label}:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        safe_val = (value or "(leer)").encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 6, safe_val)
        pdf.ln(1)

    pdf.ln(5)

    # Motivationstext
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Motivationstext / E-Mail-Body:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    # Sonderzeichen bereinigen für FPDF
    clean_body = body.encode("latin-1", errors="replace").decode("latin-1")
    pdf.multi_cell(0, 5, clean_body)

    pdf.output(str(out_path))
    log.info(f"  E-Mail-PDF erstellt: {out_path}")
    return out_path

# ── Formular befüllen ────────────────────────────────────────────────────────

FORM_URL = CFG["form"]["url"]

def fill_form(data: dict, cv_file: Path | None, email_pdf: Path):
    """Öffnet das EV-Formular, befüllt alle Felder und lädt Dateien hoch."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=CFG["form"].get("headless", False),
            slow_mo=CFG["form"].get("slow_mo_ms", 50),
        )
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        timeout = CFG["browser"]["timeout_ms"]

        log.info(f"Öffne Formular: {FORM_URL}")
        page.goto(FORM_URL, wait_until="networkidle", timeout=60000)

        # Cookie-Banner
        for sel in [
            "button:has-text('Zustimmen')",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Accept all')",
            "button[id*='accept']",
            "[class*='cookie'] button",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(1500)
                    log.info(f"  Cookie-Banner geschlossen.")
                    break
            except Exception:
                pass

        page.wait_for_timeout(2000)

        def fill(selector: str, value: str, label: str = ""):
            if not value:
                log.info(f"  {label or selector}: (leer) — übersprungen")
                return
            try:
                el = page.locator(selector).first
                el.wait_for(state="visible", timeout=timeout)
                el.scroll_into_view_if_needed()
                el.fill(value)
                log.info(f"  {label or selector}: {value[:60]!r}")
            except PWTimeout:
                log.warning(f"  {label or selector}: Timeout — Feld nicht gefunden")
            except Exception as e:
                log.warning(f"  {label or selector}: Fehler — {e}")

        # ── Felder befüllen ──────────────────────────────────────────────────
        fill("#firstName",   data.get("first_name", ""),  "Vorname")
        fill("#lastName",    data.get("last_name", ""),   "Nachname")
        fill("#email",       data.get("email", ""),       "E-Mail")

        # Vorwahl (Dropdown)
        try:
            dial_country = dial_code_to_country(data.get("dial_code", "+49"))
            page.locator("select[name='dialCode']").select_option(label=dial_country)
            log.info(f"  Vorwahl: {dial_country}")
        except Exception as e:
            log.warning(f"  Vorwahl-Dropdown: {e}")

        fill("#phoneNumber",  data.get("phone_number", ""), "Telefon")

        # Postleitzahl-Feld (langer dynamischer Name)
        fill(
            "input[name*='Postleitzahl']",
            data.get("zip", ""),
            "Postleitzahl"
        )

        # Nachricht / Motivationstext — bevorzuge geparsten Text, Fallback: ganzer Body
        motivation = (data.get("motivation") or "").strip()
        if not motivation:
            motivation = (data.get("body_text") or "").strip()
        try:
            el = page.locator("#message").first
            el.wait_for(state="visible", timeout=timeout)
            el.scroll_into_view_if_needed()
            el.fill(motivation[:3000] if motivation else "(leer)")
            log.info(f"  Nachricht: {len(motivation)} Zeichen")
        except Exception as e:
            log.warning(f"  Nachricht-Feld: {e}")

        # ── Datei-Upload ─────────────────────────────────────────────────────
        upload_files = []
        if cv_file and cv_file.exists():
            upload_files.append(str(cv_file))
        upload_files.append(str(email_pdf))

        try:
            file_input = page.locator("input[type='file']").first
            file_input.wait_for(state="attached", timeout=timeout)
            file_input.set_input_files(upload_files)
            log.info(f"  Dateien hochgeladen: {[Path(f).name for f in upload_files]}")
        except Exception as e:
            log.warning(f"  Datei-Upload fehlgeschlagen: {e}")
            # Fallback: einzeln hochladen
            for fp in upload_files:
                try:
                    page.locator("input[type='file']").first.set_input_files(fp)
                    page.wait_for_timeout(1000)
                    log.info(f"    {Path(fp).name} hochgeladen (Einzelupload)")
                except Exception as e2:
                    log.warning(f"    {Path(fp).name}: {e2}")

        page.wait_for_timeout(1000)

        log.info("\n" + "="*60)
        if DEV_MODE:
            log.info("DEV-MODUS — Formular befüllt, NICHT absenden!")
            log.info("Prüfe die Felder, dann ENTER drücken um zu schließen.")
        else:
            log.info("PROD-MODUS — Formular prüfen, manuell absenden,")
            log.info("dann ENTER drücken um zur nächsten Bewerbung zu gehen.")
        log.info("="*60)

        try:
            prompt = "\n>>> [DEV] Felder prüfen, ENTER zum Schließen: " if DEV_MODE else "\n>>> [PROD] Absenden, dann ENTER für nächste Bewerbung: "
            input(prompt)
        except EOFError:
            log.info("  (Nicht-interaktiver Modus — Browser bleibt 10s offen)")
            page.wait_for_timeout(10000)

        browser.close()

def dial_code_to_country(dial_code: str) -> str:
    mapping = {
        "+49": "Deutschland",
        "+43": "Österreich",
        "+41": "Schweiz",
        "+1":  "Vereinigte Staaten",
        "+44": "Vereinigtes Königreich",
    }
    return mapping.get(dial_code, "Deutschland")

# ── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Bewerbungs-Automatisierung gestartet")
    log.info(f"Zeitstempel: {datetime.now(timezone.utc).isoformat()}")
    log.info(f"Modus:   {'DEV (kein Absenden)' if DEV_MODE else 'PROD (manuelles Absenden)'}")
    log.info(f"Filter:  '{_active_profile}' — {FILTER.get('description', '')} (batch: {FILTER.get('batch_size', 10)})")
    log.info("=" * 60)

    # Zugangsdaten prüfen
    if not CFG["imap"]["server"] or not CFG["imap"]["username"]:
        log.error("IMAP-Zugangsdaten fehlen in config.json!")
        sys.exit(1)

    emails = fetch_new_emails()
    if not emails:
        log.info("Keine neuen Bewerbungs-E-Mails gefunden.")
        return

    log.info(f"\n{len(emails)} neue Bewerbung(en) zu verarbeiten.\n")
    processed = load_processed()

    for i, mail in enumerate(emails, 1):
        log.info(f"\n{'='*60}")
        log.info(f"Bewerbung {i}/{len(emails)}: {mail['subject'][:80]}")
        log.info(f"{'='*60}")

        # Parsen
        data = parse_email(mail["subject"], mail["body"])
        data["body_text"] = mail["body"]

        applicant_name = f"{data.get('first_name','')} {data.get('last_name','')}".strip() or "Unbekannt"
        log.info(f"Bewerber: {applicant_name}")

        # CV herunterladen
        cv_file = download_cv(data.get("cv_url", ""), applicant_name)

        # E-Mail-PDF erstellen
        email_pdf = create_email_pdf(mail["subject"], mail["body"], data, applicant_name)

        # Formular befüllen
        fill_form(data, cv_file, email_pdf)

        # Als verarbeitet markieren
        processed.add(mail["uid"])
        save_processed(processed)
        log.info(f"E-Mail [{mail['uid']}] als verarbeitet gespeichert.")

    log.info("\nAlle Bewerbungen verarbeitet.")

if __name__ == "__main__":
    main()
