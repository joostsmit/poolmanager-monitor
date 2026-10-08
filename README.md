# Poolmanager monitor

Kijkt elke 5 minuten in je Poolmanager-kalender en stuurt een pushmelding naar je telefoon als er een **nieuwe open opdracht** bij komt.

- **Gele** items (open opdrachten) → hierover krijg je een melding.
- **Groene** items (al ingeschreven) en grijze items (je beschikbaarheid) → worden genegeerd.
- Er wordt 3 maanden vooruit gekeken.
- Om **12:00 en 18:00** krijg je een overzicht: hoe vaak er sinds het vorige overzicht is gecontroleerd, hoeveel nieuwe opdrachten er zijn gevonden en hoeveel er nu open staan.
  Andere tijden? Pas `SUMMARY_HOURS` aan in `monitor.py` en de tweede `cron`-regel in `.github/workflows/monitor.yml` (die staat in UTC: zomertijd = NL-tijd min 2 uur, wintertijd = min 1 uur).
- Wat al gezien is staat in `seen.json`. De eerste keer worden alle bestaande opdrachten alleen opgeslagen, zonder melding.

## 1. ntfy-app instellen

1. Installeer de app **ntfy** (App Store of Google Play).
2. Bedenk een topic-naam die niemand kan raden, bijv. `joost-pool-8f3k2q9x`.
   Let op: iedereen die deze naam kent, kan je meldingen lezen. Zie het als een wachtwoord.
3. Open de app, tik op **+** (Subscribe to topic), vul je topic-naam in en tik op **Subscribe**.
4. Testen: open `https://ntfy.sh/<jouw-topic>` in je browser en verstuur een testbericht. Dat moet binnenkomen op je telefoon.

## 2. GitHub Secrets toevoegen

1. Ga in GitHub naar deze repository → **Settings** → **Secrets and variables** → **Actions**.
2. Klik op **New repository secret** en voeg deze drie toe:

| Name                   | Secret                         |
|------------------------|--------------------------------|
| `POOLMANAGER_USERNAME` | je Poolmanager-gebruikersnaam  |
| `POOLMANAGER_PASSWORD` | je Poolmanager-wachtwoord      |
| `NTFY_TOPIC`           | je topic-naam uit stap 1       |

## 3. Starten en testen

1. Ga naar het tabblad **Actions** → **Poolmanager monitor** → **Run workflow**.
2. De eerste keer zie je in het log iets als `Eerste keer: 2 opdracht(en) opgeslagen, geen melding.`
3. Daarna draait hij vanzelf elke 5 minuten (GitHub start soms een paar minuten later).

Overzicht testen? Zet bij **Run workflow** het vinkje **Ook het overzicht versturen** aan.

Testmelding forceren? Haal een id weg uit `seen.json`, commit dat, en start de workflow handmatig.

## Lokaal draaien

```bash
pip install -r requirements.txt
export POOLMANAGER_USERNAME=... POOLMANAGER_PASSWORD=... NTFY_TOPIC=...
python monitor.py
```
