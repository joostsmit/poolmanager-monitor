# Poolmanager monitor

Kijkt doordeweeks overdag elke 4 minuten en verder elke 30 minuten (gestart via cron-job.org, zie stap 4) in je Poolmanager-kalender en stuurt een pushmelding naar je telefoon als er een **nieuwe open opdracht** bij komt.

- **Gele** items (open opdrachten) → hierover krijg je een melding. Ook als een opdracht die al weg was **weer open** komt (bijv. teruggegeven door een collega).
- **Groene** items (al ingeschreven) en grijze items (je beschikbaarheid) → worden genegeerd.
- Meldingen gaan naar **Pushover** (hoofdkanaal) en, als je dat ook instelt, naar **ntfy** (reserve).
- Tik op de link in de melding (bij één opdracht) of op een knop **Open …** (ntfy) om meteen naar de opdracht te gaan, met de knop *Zelfroosteren*. Ben je op je telefoon niet ingelogd bij Poolmanager, dan log je eerst in en kom je daarna op de opdracht.
- Er wordt 3 maanden vooruit gekeken.
- Om **12:00 en 18:00** krijg je een overzicht: hoe vaak er sinds het vorige overzicht is gecontroleerd, hoeveel nieuwe opdrachten er zijn gevonden en hoeveel er nu open staan.
  Andere tijden? Pas `SUMMARY_HOURS` aan in `monitor.py`.
- Wat al gezien is staat in `seen.json`. De eerste keer worden alle bestaande opdrachten alleen opgeslagen, zonder melding.
  Opdrachten worden 7 dagen na hun datum automatisch opgeruimd, zodat het bestand niet blijft groeien.

## 1. Pushover instellen (hoofdkanaal)

1. Installeer de app **Pushover** (App Store of Google Play) en maak een account. Na 30 dagen proberen kost de app eenmalig ongeveer $5.
2. Log in op https://pushover.net. Rechtsboven staat **Your User Key**: kopieer die (dit is `PUSHOVER_USER_KEY`).
3. Klik onderaan op **Create an Application/API Token**. Naam: `Poolmanager`. Vink de voorwaarden aan en klik op **Create Application**.
   Kopieer de **API Token/Key** (dit is `PUSHOVER_APP_TOKEN`).
4. **Focus en Niet storen:** zet Pushover bij elk focusprofiel dat je gebruikt (Werk, Slapen, Niet storen, …) op de lijst met toegestane apps:
   *Instellingen → Focus → [profiel] → Apps → Voeg toe → Pushover*.
5. **Apple Watch:** open de Watch-app op je iPhone → *Meldingen* → *Pushover* → *Spiegel iPhone-meldingen*.
   De Watch toont meldingen als je iPhone op slot staat.
6. **Testen:** GitHub → **Actions** → **Poolmanager monitor** → **Run workflow** → vink **Testmelding versturen** aan.
   Test met je iPhone op slot, je focusprofiel aan en je Watch om.

**Hoe hard komt een nieuwe opdracht binnen?**
- Standaard: **hoge prioriteit**, één melding.
- Wil je dat de melding ook door stil en focus heen komt: zet in de Pushover-app bij *Settings* **Critical Alerts** aan voor *High priority*.
- Wil je een **noodmelding** die elke minuut opnieuw afgaat (max. 30 minuten) tot je hem in de app bevestigt:
  GitHub → **Settings** → **Secrets and variables** → **Actions** → tabblad **Variables** → **New repository variable**:
  name `PUSHOVER_EMERGENCY`, value `true`. Terugzetten: verwijder de variable.

## 1b. ntfy instellen (optioneel, reserve)

Wil je naast Pushover ook ntfy houden, zodat er altijd een tweede kanaal is: volg deze stappen en vul `NTFY_TOPIC` in.
Wil je alleen Pushover: verwijder het Secret `NTFY_TOPIC`.


1. Installeer de app **ntfy** (App Store of Google Play).
2. Bedenk een topic-naam die niemand kan raden, bijv. `joost-pool-8f3k2q9x`.
   Let op: iedereen die deze naam kent, kan je meldingen lezen. Zie het als een wachtwoord.
3. Open de app, tik op **+** (Subscribe to topic), vul je topic-naam in en tik op **Subscribe**.
4. Meldingen over nieuwe opdrachten komen met **maximale prioriteit** (hard geluid). Wil je dat ze ook door *Niet storen* heen komen:
   - **Android:** Instellingen → Apps → ntfy → Meldingen → kanaal *Max priority* → zet *Niet storen negeren* aan.
   - **iPhone:** Instellingen → ntfy → Meldingen → zet *Tijdgevoelige meldingen* aan (als die optie er staat).
5. Testen: open `https://ntfy.sh/<jouw-topic>` in je browser en verstuur een testbericht. Dat moet binnenkomen op je telefoon.

## 2. GitHub Secrets toevoegen

1. Ga in GitHub naar deze repository → **Settings** → **Secrets and variables** → **Actions**.
2. Klik op **New repository secret** en voeg deze toe:

| Name                   | Secret                         |
|------------------------|--------------------------------|
| `POOLMANAGER_USERNAME` | je Poolmanager-gebruikersnaam  |
| `POOLMANAGER_PASSWORD` | je Poolmanager-wachtwoord      |
| `PUSHOVER_USER_KEY`    | je User Key uit stap 1         |
| `PUSHOVER_APP_TOKEN`   | je API Token uit stap 1        |
| `NTFY_TOPIC`           | (optioneel) je ntfy-topic uit stap 1b |

## 3. Starten en testen

1. Ga naar het tabblad **Actions** → **Poolmanager monitor** → **Run workflow**.
2. De eerste keer zie je in het log iets als `Eerste keer: 2 opdracht(en) opgeslagen, geen melding.`
3. Daarna draait hij vanzelf volgens het rooster (via cron-job.org, zie stap 4).

Overzicht testen? Zet bij **Run workflow** het vinkje **Ook het overzicht versturen** aan.

Testmelding forceren? Haal een id weg uit `seen.json`, commit dat, en start de workflow handmatig.

## 4. Starten via cron-job.org

GitHub start geplande workflows niet betrouwbaar (soms maar een paar keer per nacht).
Daarom start de gratis dienst cron-job.org de workflow, volgens dit rooster:

| Wanneer | Hoe vaak | Taak in cron-job.org |
|---|---|---|
| Ma–vr 07:00–19:59 | elke 4 minuten | *Poolmanager druk* |
| Ma–vr 00:00–06:59 en 20:00–23:59 | elke 30 minuten | *Poolmanager rustig doordeweeks* |
| Za en zo, hele dag | elke 30 minuten | *Poolmanager rustig weekend* |

De drie taken overlappen nergens, dus er wordt nooit dubbel gecontroleerd.

Het GitHub-schema blijft als reserve aan.
Pas je het rooster aan? Zet dan ook `BUSY_DAYS`, `BUSY_HOURS`, `BUSY_MINUTES` en `QUIET_MINUTES` in `monitor.py` goed,
anders klopt de waarschuwing *"minder controles dan verwacht"* niet.

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

**B. Drie taken maken op cron-job.org**

Maak een gratis account op https://cron-job.org. Maak dan drie taken (**Create cronjob**). Ze zijn gelijk, alleen de titel en het schema verschillen.

1. Tabblad **Common**:
   - **Title:** `Poolmanager druk`, `Poolmanager rustig doordeweeks` en `Poolmanager rustig weekend`
   - **URL:** `https://api.github.com/repos/joostsmit/poolmanager-monitor/actions/workflows/monitor.yml/dispatches`
   - **Execution schedule:** kies **Custom** en vink aan:

     | | druk | rustig doordeweeks | rustig weekend |
     |---|---|---|---|
     | Days of month | alle | alle | alle |
     | Days of week | Monday t/m Friday | Monday t/m Friday | Saturday en Sunday |
     | Months | alle | alle | alle |
     | Hours | 7 t/m 19 | 0 t/m 6 en 20 t/m 23 | alle |
     | Minutes | 0, 4, 8, 12, … 56 | 0 en 30 | 0 en 30 |

2. Tabblad **Advanced**:
   - **Time zone:** `Europe/Amsterdam` (staat dit er niet, zet het dan bij je accountinstellingen)
   - **Request method:** `POST`
   - **Headers** (3 regels):

     | Key             | Value                         |
     |-----------------|-------------------------------|
     | `Authorization` | `Bearer <jouw token>`         |
     | `Accept`        | `application/vnd.github+json` |
     | `Content-Type`  | `application/json`            |

   - **Request body:** `{"ref":"main"}`
3. Klik op **Test run**. Status **204** = goed. Klik daarna op **Create** (of **Save**).
4. Kijk na een paar minuten in **Actions**: daar verschijnen runs met *"Manually run by joostsmit"*.

Tip: heb je al een taak? Gebruik die als *Poolmanager druk* (pas titel en schema aan) en maak met **Clone** de andere twee.

## 5. Als er iets misgaat

De monitor waarschuwt je zelf als hij zijn werk niet kan doen:

- **"Poolmanager monitor werkt NIET"** (pushmelding): inloggen mislukt, de website is veranderd, of een andere fout.
  Je krijgt de melding bij de eerste fout en daarna elk uur zolang het misgaat. In het bericht staat de oorzaak.
- **"Poolmanager monitor werkt weer"**: alles is hersteld.
- **In het overzicht van 12:00/18:00**: *"minder controles dan verwacht"* betekent dat cron-job.org de monitor niet (vaak genoeg) start. Kijk dan bij cron-job.org of de token verlopen is.
- **Geen overzicht om 12:00 of 18:00 gekregen?** Dan draait de monitor helemaal niet. Kijk in GitHub bij **Actions** en bij cron-job.org.

Extra vangnet: zet bij cron-job.org in je taak (tabblad **Notifications**) aan dat je een e-mail krijgt als de taak mislukt. Dat gebeurt bijvoorbeeld als de GitHub-token verlopen is.

## 6. Onderhoud: dingen die op termijn verlopen

| Wat | Wanneer | Wat te doen |
|---|---|---|
| **GitHub-token voor cron-job.org** | Na de looptijd die je koos (max. 1 jaar) | Zet de vervaldatum als variable, dan waarschuwt het overzicht 14 dagen vooraf: GitHub → **Settings** → **Secrets and variables** → **Actions** → **Variables** → `CRON_TOKEN_EXPIRES` = `JJJJ-MM-DD`. Nieuwe token maken (stap 4A), in alle cron-job.org-taken vervangen, en de datum bijwerken. |
| **Pushover-proefperiode** | 30 dagen na installatie | Koop de app (eenmalig) in de Pushover-app, anders stoppen de meldingen. |
| **cron-job.org zet een taak uit** | Na veel mislukte starts op rij (bijv. storing bij GitHub) | Zet per taak bij **Notifications** de e-mail bij mislukken aan. Controleer of de taken nog *enabled* zijn als het overzicht "minder controles dan verwacht" meldt. |
| **Poolmanager-wachtwoord** | Als je het wijzigt | Werk het Secret `POOLMANAGER_PASSWORD` bij (je krijgt anders de melding "werkt NIET"). |

## Lokaal draaien

```bash
pip install -r requirements.txt
export POOLMANAGER_USERNAME=... POOLMANAGER_PASSWORD=... PUSHOVER_USER_KEY=... PUSHOVER_APP_TOKEN=...
python monitor.py
```
