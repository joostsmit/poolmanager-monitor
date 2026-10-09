"""Poolmanager monitor: meldt nieuwe open opdrachten via ntfy.

Leest de maandkalender (EmployeeAgenda.aspx). Er is geen JSON-API; de
kalender wordt als HTML door de server gemaakt.
- Gele items (class 'SelfSchedulingItem') = open opdrachten -> deze volgen we.
- Groene items (class 'final') = al ingeschreven -> overslaan.
- Grijze items (class 'availability') = eigen beschikbaarheid -> overslaan.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://cpzzp.poolmanager.mobi"
LOGIN_URL = BASE + "/Account/Login.aspx"
AGENDA_URL = BASE + "/uiweb/emp/EmployeeAgenda.aspx"
NEXT_BUTTON = "ctl00$ctl00$MasterContentPlaceHolder$ContentPlaceHolder1$MonthCalendar$btnNext"
MONTHS = int(os.environ.get("MONTHS_AHEAD", "3"))  # aantal maanden om te bekijken
SEEN_FILE = "seen.json"
SUMMARY_FILE = "last_summary.txt"  # moment van het laatst verstuurde overzicht
TZ = ZoneInfo("Europe/Amsterdam")
SUMMARY_HOURS = (12, 18)  # tijden van het dagelijkse overzicht


def form_fields(soup, form_id):
    """Alle verborgen velden (viewstate e.d.) van een ASP.NET-formulier."""
    form = soup.find("form", id=form_id)
    return {i["name"]: i.get("value", "") for i in form.find_all("input", type="hidden") if i.get("name")}


def login(session):
    soup = BeautifulSoup(session.get(LOGIN_URL).text, "html.parser")
    data = form_fields(soup, "loginForm")
    data.update({
        "Email": os.environ["POOLMANAGER_USERNAME"],
        "Password": os.environ["POOLMANAGER_PASSWORD"],
        "__EVENTTARGET": "submitLogin",
        "__EVENTARGUMENT": "",
    })
    r = session.post(LOGIN_URL, data=data)
    if "Login.aspx" in r.url:
        sys.exit("Inloggen mislukt: controleer gebruikersnaam en wachtwoord.")


def parse_month(soup):
    """Geeft (maandnaam, lijst met open opdrachten) terug."""
    month = soup.select_one("div[onclick*='showquicknavigation']")
    month = month.get_text(strip=True) if month else "?"
    items = []
    for item in soup.select("div.SelfSchedulingItem"):
        m = re.search(r"OpenNewAppointment',\s*'([^']+)'", item.get("onclick", ""))
        if not m:
            continue
        header = item.find_previous("div", class_="day_header")
        date = header.get_text(strip=True).split("|")[0].strip() if header else "?"

        def text(cls):
            el = item.find(class_=cls)
            return el.get_text(" ", strip=True) if el else ""

        items.append({
            "id": m.group(1),
            "datum": f"{date} {month}",
            "titel": text("dayitem_title"),
            "tijd": text("dayitem_timespan"),
            "info": text("dayitem_description"),
        })
    return month, items


def fetch_items(session):
    all_items = {}
    r = session.get(AGENDA_URL)
    for i in range(MONTHS):
        soup = BeautifulSoup(r.text, "html.parser")
        month, items = parse_month(soup)
        print(f"{month}: {len(items)} open opdracht(en)")
        for item in items:
            all_items[item["id"]] = item
        if i < MONTHS - 1:
            data = form_fields(soup, "aspnetForm")
            data.update({"__EVENTTARGET": NEXT_BUTTON, "__EVENTARGUMENT": ""})
            r = session.post(AGENDA_URL, data=data)
    return all_items


def send(title, body):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print(f"Geen NTFY_TOPIC ingesteld, niet verstuurd: {title}\n{body}")
        return
    requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={"Title": title, "Click": AGENDA_URL, "Tags": "swimmer"},
        timeout=30,
    ).raise_for_status()
    print("Melding verstuurd:", title)


def notify(items):
    lines = [f"{i['datum']} {i['tijd']} - {i['titel']} ({i['info']})" for i in items]
    send(f"{len(items)} nieuwe opdracht(en) in Poolmanager", "\n".join(lines))


def count_runs(since):
    """Aantal geslaagde en mislukte runs van deze workflow sinds 'since' (via GitHub API)."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None, None
    url = f"https://api.github.com/repos/{repo}/actions/workflows/monitor.yml/runs"
    counts = []
    for status in ("success", "failure"):
        r = requests.get(url, timeout=30, headers={"Authorization": f"Bearer {token}"}, params={
            "created": ">=" + since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status, "per_page": 1,
        })
        r.raise_for_status()
        counts.append(r.json()["total_count"])
    return counts


def summary(seen, open_count, forced):
    """Overzicht sinds het vorige overzichtsmoment."""
    now = datetime.now(TZ)
    current = current_slot(now)
    since = current if forced else max(t for t in slots(now) if t < current)
    found = sum(1 for t in seen.values() if t and datetime.fromisoformat(t) >= since)
    ok, failed = count_runs(since)
    checks = "?" if ok is None else ok + 1  # +1 voor deze run
    lines = [
        f"Sinds {since:%H:%M} ({'vandaag' if since.date() == now.date() else 'gisteren'}):",
        f"- {checks}x gecontroleerd",
        f"- {found} nieuwe opdracht(en) gevonden",
        "",
        f"Je kunt je nu nog inschrijven op {open_count} opdracht(en) (komende {MONTHS} maanden).",
    ]
    if failed:
        lines.append(f"Let op: {failed} controle(s) mislukt")
    send(f"Poolmanager overzicht {now:%H:%M}", "\n".join(lines))


def slots(now):
    """Overzichtsmomenten van gisteren en vandaag."""
    return [
        (now - timedelta(days=d)).replace(hour=h, minute=0, second=0, microsecond=0)
        for d in (1, 0) for h in SUMMARY_HOURS
    ]


def current_slot(now):
    return max(t for t in slots(now) if t <= now)


def summary_due():
    """True als het overzicht van het laatste overzichtsmoment nog niet verstuurd is (max. 3 uur te laat)."""
    slot = current_slot(datetime.now(TZ))
    last = open(SUMMARY_FILE).read().strip() if os.path.exists(SUMMARY_FILE) else ""
    if last == slot.isoformat() or datetime.now(TZ) - slot > timedelta(hours=3):
        return False
    with open(SUMMARY_FILE, "w") as f:
        f.write(slot.isoformat() + "\n")
    return True


def main():
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (poolmanager-monitor)"
    login(session)
    items = fetch_items(session)

    first_run = not os.path.exists(SEEN_FILE)
    seen = {} if first_run else json.load(open(SEEN_FILE))
    if isinstance(seen, list):  # oud formaat: alleen id's
        seen = {k: "" for k in seen}
    new = [i for k, i in items.items() if k not in seen]

    if first_run:
        print(f"Eerste keer: {len(items)} opdracht(en) opgeslagen, geen melding.")
    elif new:
        notify(new)
    else:
        print("Geen nieuwe opdrachten.")

    # Bewaar alles wat ooit gezien is, met het moment van vinden (laatste 1000).
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for k in items:
        seen.setdefault(k, "" if first_run else now)
    seen = dict(list(seen.items())[-1000:])
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=1)

    forced = os.environ.get("FORCE_SUMMARY") == "true"
    if forced or summary_due():
        summary(seen, len(items), forced)


if __name__ == "__main__":
    main()
