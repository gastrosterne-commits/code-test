"""
Form Explorer — öffnet das EV-Bewerbungsformular und gibt alle Felder aus.
Einmalig ausführen, um die Formularstruktur zu verstehen.
"""
import json
from playwright.sync_api import sync_playwright

URL = "https://www.engelvoelkers.com/de/de/immobilienmakler-werden/immobilienmakler-bewerbung-sea"

def explore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()

        print(f"Öffne {URL} ...")
        page.goto(URL, wait_until="networkidle", timeout=60000)

        # Cookie-Banner wegklicken falls vorhanden
        for selector in [
            "button[id*='accept']", "button[id*='cookie']",
            "[class*='cookie'] button", "[id*='consent'] button",
            "button:has-text('Alle akzeptieren')", "button:has-text('Accept')",
            "button:has-text('Akzeptieren')", "button:has-text('Zustimmen')"
        ]:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f"  Cookie-Banner geschlossen via: {selector}")
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        page.wait_for_timeout(3000)

        # Alle Formularfelder sammeln
        fields = page.evaluate("""() => {
            const results = [];
            const inputs = document.querySelectorAll('input, textarea, select, [role="combobox"], [role="listbox"]');
            inputs.forEach(el => {
                results.push({
                    tag: el.tagName,
                    type: el.type || '',
                    id: el.id || '',
                    name: el.name || '',
                    placeholder: el.placeholder || '',
                    label: el.labels && el.labels[0] ? el.labels[0].innerText.trim() : '',
                    required: el.required,
                    ariaLabel: el.getAttribute('aria-label') || '',
                    dataTestId: el.getAttribute('data-testid') || '',
                    className: el.className || '',
                    value: el.value || ''
                });
            });
            return results;
        }""")

        print(f"\n=== {len(fields)} Felder gefunden ===\n")
        for i, f in enumerate(fields):
            print(f"[{i}] {f['tag']} type={f['type']!r} id={f['id']!r} name={f['name']!r}")
            print(f"     placeholder={f['placeholder']!r} label={f['label']!r}")
            print(f"     ariaLabel={f['ariaLabel']!r} required={f['required']}")
            print(f"     class={f['className'][:80]!r}")
            print()

        # Upload-Felder extra ausgeben
        uploads = [f for f in fields if f['type'] == 'file']
        print(f"\n=== {len(uploads)} Upload-Felder ===")
        for u in uploads:
            print(f"  id={u['id']!r} name={u['name']!r} class={u['className']!r}")

        # JSON speichern
        with open("form_fields.json", "w", encoding="utf-8") as fh:
            json.dump(fields, fh, indent=2, ensure_ascii=False)
        print("\nGespeichert als form_fields.json")

        print("\nDrücke ENTER um Browser zu schließen...")
        input()
        browser.close()

if __name__ == "__main__":
    explore()
