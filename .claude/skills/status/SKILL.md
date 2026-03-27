---
name: status
description: Zeigt den aktuellen Status der Bewerbungs-Automatisierung: DEV/PROD-Modus, Anzahl verarbeiteter E-Mails, Dateien im Download-Ordner.
allowed-tools: Bash, Read
---

Zeige den aktuellen Status der Automatisierung.

1. Lese `.env` für den aktuellen DEV_MODE-Wert
2. Lese `processed_emails.json` und zähle die verarbeiteten IDs
3. Zähle Dateien in `downloads/`

Gib eine übersichtliche Zusammenfassung aus:
- Modus (DEV oder PROD)
- Anzahl bereits verarbeiteter E-Mails
- Anzahl Dateien in downloads/
