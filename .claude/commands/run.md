Starte die Bewerbungs-Automatisierung mit einem bestimmten Filter-Profil.

Argument: $ARGUMENTS (z.B. "hamburg", "frankfurt", "standard", "neu_seit_heute")

Gehe so vor:
1. Lese `filters.json` und zeige alle verfügbaren Profile mit Beschreibung
2. Falls ein Argument übergeben wurde: setze `"active"` in `filters.json` auf diesen Wert. Falls das Profil nicht existiert, liste die verfügbaren Profile auf und brich ab.
3. Falls kein Argument: frage welches Profil verwendet werden soll und setze es.
4. Zeige kurz was jetzt aktiv ist (Profil, Keywords, batch_size, date_after)
5. Starte dann:

```bash
cd "c:\Users\stayg\Documents\Claude Workspace\Code-Test" && venv/Scripts/python main.py
```

6. Zeige die Ausgabe und weise auf Fehler hin.
