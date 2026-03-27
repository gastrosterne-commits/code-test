# Bewerbungs-Automatisierung — Engel & Völkers

Automatisiert den Prozess von eingehenden SocialTalents-Bewerbungs-E-Mails bis zum ausgefüllten Engel & Völkers Online-Formular.

## Architektur

```
main.py          – Hauptprogramm (IMAP → Parse → PDF → Download → Formular)
test_run.py      – Testlauf mit Musterdaten (kein IMAP nötig)
config.json      – Nicht-sensitive Einstellungen (URLs, Timeouts, Filter)
.env             – Sensitive Zugangsdaten (IMAP, DEV_MODE)
processed_emails.json – Bereits verarbeitete E-Mail-IDs (nicht neu verarbeiten)
downloads/       – Heruntergeladene CVs + generierte E-Mail-PDFs
automation.log   – Vollständiges Log aller Läufe
```

## Schlüssel-Funktionen in main.py

| Funktion | Aufgabe |
|---|---|
| `fetch_new_emails()` | IMAP-Verbindung, sucht neue Bewerbungs-Mails |
| `parse_email(subject, body)` | Regex-Extraktion: Name, E-Mail, Telefon, PLZ, Motivation, CV-URL |
| `download_cv(url, name)` | CV-Download mit Redirect-Folge, auto-Dateiendung |
| `create_email_pdf(...)` | FPDF2-PDF aus E-Mail-Inhalt |
| `fill_form(data, cv, pdf)` | Playwright: Formular öffnen, befüllen, Dateien hochladen |

## Modi

- **DEV_MODE=true** (`.env`): Formular befüllen, NICHT absenden — nur prüfen
- **DEV_MODE=false**: Produktionsbetrieb — manuell absenden, dann ENTER

## Starten

```bash
# Produktionslauf
venv/Scripts/python main.py

# Testlauf (keine IMAP-Zugangsdaten nötig)
venv/Scripts/python test_run.py
```

## Abhängigkeiten

- `playwright` — Browser-Automatisierung (Chromium)
- `fpdf2` — PDF-Generierung
- `requests` — CV-Download
- `python-dotenv` — `.env`-Laden

## Konventionen

- IMAP-Credentials kommen **immer** aus `.env`, nie aus `config.json`
- `.env` wird nie committet
- `processed_emails.json` enthält verarbeitete UIDs als String-Liste
- Sonderzeichen in PDFs: latin-1 encode mit `errors="replace"`
- Playwright-Selektoren: `#firstName`, `#lastName`, `#email`, `select[name='dialCode']`, `#phoneNumber`, `input[name*='Postleitzahl']`, `#message`, `input[type='file']`
