---
name: toggle-mode
description: Wechselt den DEV_MODE in .env zwischen true (Formular nur prüfen, nicht absenden) und false (Produktionsbetrieb, manuell absenden).
allowed-tools: Read, Edit
---

1. Lese `.env` unter `c:\Users\stayg\Documents\Claude Workspace\Code-Test\.env`
2. Erkenne den aktuellen Wert von `DEV_MODE`
3. Setze ihn auf den jeweils anderen Wert:
   - `DEV_MODE=true` → `DEV_MODE=false` (Produktionsmodus — Formular wird abgesendet)
   - `DEV_MODE=false` → `DEV_MODE=true` (Dev-Modus — nur prüfen, nicht absenden)
4. Bestätige den neuen Modus in deiner Antwort.
