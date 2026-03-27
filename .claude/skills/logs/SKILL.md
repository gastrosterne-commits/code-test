---
name: logs
description: Zeigt die letzten Einträge aus automation.log der Bewerbungs-Automatisierung. Optionales Argument: Anzahl Zeilen.
allowed-tools: Bash, Read
argument-hint: [anzahl-zeilen]
---

Zeige die letzten Einträge aus dem Automation-Log und fasse zusammen ob Fehler aufgetreten sind.

Anzahl Zeilen: $ARGUMENTS (Standard: 50 falls leer)

Lese die Datei: `c:\Users\stayg\Documents\Claude Workspace\Code-Test\automation.log`

Fasse zusammen: Anzahl verarbeiteter Bewerbungen, Fehler, Warnungen.
