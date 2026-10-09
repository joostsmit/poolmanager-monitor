# Poolmanager monitor

Kijkt elke 5 minuten (gestart via cron-job.org, zie stap 4) in je Poolmanager-kalender en stuurt een pushmelding naar je telefoon als er een **nieuwe open opdracht** bij komt.

- **Gele** items (open opdrachten) → hierover krijg je een melding.
- **Groene** items (al ingeschreven) en grijze items (je beschikbaarheid) → worden genegeerd.
- Er wordt 3 maanden vooruit gekeken.
- Om **12:00 en 18:00** krijg je een overzicht: hoe vaak er sinds het vorige overzicht is gecontroleerd, hoeveel nieuwe opdrachten er zijn gevonden en hoeveel er nu open staan.
  Andere tijden? Pas `SUMMARY_HOURS` aan in `monitor.py`.
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

## 4. Elke 5 minuten starten via cron-job.org

GitHub start geplande workflows niet betrouwbaar (soms maar een paar keer per nacht).
Daarom start de gratis dienst cron-job.org de workflow elke 5 minuten. Het GitHub-schema blijft als reserve aan.

**A. Sleutel (token) maken in GitHub**

1. Profielfoto rechtsboven → **Settings** → helemaal onderaan links **Developer settings**.
2. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
3. Vul in:
   - **Token name:** `poolmanager-cron`
   - **Expiration:** de langste termijn die je kunt kiezen. Zet in je agenda wanneer hij verloopt.
   - **Repository access:** *Only select repositories* → `poolmanager-monitor`
   - **Permissions** → **Repository permissions** → **Actions:** *Read and write*
4. Klik op **Generate token** en kopieer de token (je ziet hem maar één keer).

De token kan alleen deze workflow starten, verder niets.

**B. Taak maken op cron-job.org**

1. Maak een gratis account op https://cron-job.org en klik op **Create cronjob**.
2. Tabblad **Common**:
   - **Title:** `Poolmanager monitor`
   - **URL:** `https://api.github.com/repos/joostsmit/poolmanager-monitor/actions/workflows/monitor.yml/dispatches`
   - **Execution schedule:** *Every 5 minutes*
3. Tabblad **Advanced**:
   - **Request method:** `POST`
   - **Headers** (3 regels):

     | Key             | Value                         |
     |-----------------|-------------------------------|
     | `Authorization` | `Bearer <jouw token>`         |
     | `Accept`        | `application/vnd.github+json` |
     | `Content-Type`  | `application/json`            |

   - **Request body:** `{"ref":"main"}`
4. Klik op **Test run**. Status **204** = goed. Klik daarna op **Create**.
5. Kijk na een paar minuten in **Actions**: daar verschijnen runs met *"Manually run by joostsmit"*.

## Lokaal draaien

```bash
pip install -r requirements.txt
export POOLMANAGER_USERNAME=... POOLMANAGER_PASSWORD=... NTFY_TOPIC=...
python monitor.py
```
