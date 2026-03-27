"""
Test-Lauf mit synthetischen Musterdaten — kein IMAP-Zugang nötig.
Testet: E-Mail-Parsing, PDF-Erstellung, CV-Download, Formular-Befüllung.
"""
import sys
from pathlib import Path

# main.py-Funktionen importieren
sys.path.insert(0, str(Path(__file__).parent))
from main import parse_email, create_email_pdf, download_cv, fill_form, log

# ── Musterdaten ──────────────────────────────────────────────────────────────

SAMPLE_SUBJECT = (
    "Bewerbung von Max Mustermann via SocialTalents "
    "als Immobilienmakler Hamburg (Engel & Völkers GmbH)"
)

SAMPLE_BODY = """
Sehr geehrte Damen und Herren,

eine neue Bewerbung ist eingegangen:

Name: Max Mustermann
E-Mail: max.mustermann@example.com
Telefon: +49 170 1234567
Postleitzahl: 20095

Motivationstext:
Ich bewerbe mich hiermit als Immobilienmakler bei Engel & Völkers in Hamburg.
Mit meiner langjährigen Erfahrung im Vertrieb und meiner Leidenschaft für
Immobilien bin ich überzeugt, dass ich eine wertvolle Bereicherung für Ihr
Team darstellen würde. Ich freue mich auf ein persönliches Gespräch.

Hochgeladener Lebenslauf: Hier ansehen https://www.clickdimensions.com/links/TestPDFfile.pdf

Mit freundlichen Grüßen,
SocialTalents / appatini.at
"""

# ── Test durchführen ─────────────────────────────────────────────────────────

def run_test():
    log.info("=" * 60)
    log.info("TEST-LAUF mit Musterdaten")
    log.info("=" * 60)

    # 1. Parsen testen
    log.info("\n[1/4] E-Mail parsen ...")
    data = parse_email(SAMPLE_SUBJECT, SAMPLE_BODY)
    data["body_text"] = SAMPLE_BODY

    assert data["first_name"] == "Max", f"Vorname falsch: {data['first_name']!r}"
    assert data["last_name"]  == "Mustermann", f"Nachname falsch: {data['last_name']!r}"
    assert "mustermann" in data["email"].lower(), f"E-Mail falsch: {data['email']!r}"
    assert data["zip"], f"PLZ fehlt: {data['zip']!r}"
    assert data["cv_url"], f"CV-URL fehlt: {data['cv_url']!r}"
    log.info("  OK — Alle Pflichtfelder korrekt geparst.")

    applicant_name = "Max Mustermann"

    # 2. E-Mail-PDF erstellen
    log.info("\n[2/4] E-Mail-PDF erstellen ...")
    email_pdf = create_email_pdf(SAMPLE_SUBJECT, SAMPLE_BODY, data, applicant_name)
    assert email_pdf.exists(), "PDF wurde nicht erstellt!"
    log.info(f"  OK — {email_pdf.name} ({email_pdf.stat().st_size // 1024} KB)")

    # 3. CV herunterladen (öffentliches Test-PDF)
    log.info("\n[3/4] CV herunterladen ...")
    cv_file = download_cv(data["cv_url"], applicant_name)
    if cv_file and cv_file.exists():
        log.info(f"  OK — {cv_file.name} ({cv_file.stat().st_size // 1024} KB)")
    else:
        log.warning("  CV-Download fehlgeschlagen (kein Stopp — Formular-Test läuft trotzdem)")

    # 4. Formular befüllen
    log.info("\n[4/4] Formular befüllen ...")
    log.info("  Browser wird geöffnet — bitte Felder prüfen und ENTER drücken.")
    fill_form(data, cv_file, email_pdf)

    log.info("\n" + "=" * 60)
    log.info("TEST-LAUF ABGESCHLOSSEN — alle Schritte erfolgreich.")
    log.info("=" * 60)

if __name__ == "__main__":
    run_test()
