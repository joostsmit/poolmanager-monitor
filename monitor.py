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
# Maximale grootte van één pushbericht. ntfy noemt 4096 bytes, maar de pushdiensten van
# Google/Apple tellen titel en extra gegevens mee; een bericht van 3,7 KB kwam al niet aan.
# Daarom ruim eronder. Langere berichten worden in delen verstuurd (1/2, 2/2).
MAX_BYTES = 2000
MAX_PARTS = 5  # nooit meer dan 5 berichten tegelijk
MONTH_ABBR = {"januari": "jan", "februari": "feb", "maart": "mrt", "april": "apr", "mei": "mei", "juni": "jun",
              "juli": "jul", "augustus": "aug", "september": "sep", "oktober": "okt", "november": "nov", "december": "dec"}


class MonitorError(Exception):
    """Fout die betekent dat de monitor zijn werk niet kan doen."""


def form_fields(soup, form_id):
    """Alle verborgen velden (viewstate e.d.) van een ASP.NET-formulier."""
    form = soup.find("form", id=form_id)
    if form is None:
        raise MonitorError(f"Formulier '{form_id}' niet gevonden; is de website veranderd?")
    return {i["name"]: i.get("value", "") for i in form.find_all("input", type="hidden") if i.get("name")}


def login(session):
    r = session.get(LOGIN_URL, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    data = form_fields(soup, "loginForm")
    data.update({
        "Email": os.environ["POOLMANAGER_USERNAME"],
        "Password": os.environ["POOLMANAGER_PASSWORD"],
        "__EVENTTARGET": "submitLogin",
        "__EVENTARGUMENT": "",
    })
    r = session.post(LOGIN_URL, data=data, timeout=60)
    r.raise_for_status()
    if "Login.aspx" in r.url:
        raise MonitorError("Inloggen mislukt. Is het wachtwoord veranderd? Pas dan het GitHub Secret aan.")


def parse_month(soup):
    """Geeft (maandnaam, lijst met open opdrachten) terug."""
    month = soup.select_one("div[onclick*='showquicknavigation']")
    month = month.get_text(strip=True) if month else "?"
    days = soup.select("div.day_header")
    # Controle of de pagina er nog uitziet zoals verwacht. Anders zou een gewijzigde website
    # stilletjes "0 opdrachten" opleveren.
    if month.split()[0] not in MONTH_ABBR or len(days) < 28:
        raise MonitorError(f"Kalender ziet er anders uit dan verwacht (maand '{month}', {len(days)} dagen). "
                           "Is de website van Poolmanager veranderd?")
    blocks = soup.select("div.SelfSchedulingItem")
    items = []
    for item in blocks:
        m = re.search(r"OpenNewAppointment',\s*'([^']+)'", item.get("onclick", ""))
        # Dagen van de vorige/volgende maand staan grijs in het rooster; die komen op hun eigen maandpagina.
        if not m or item.find_parent(class_="othermonth"):
            continue
        header = item.find_previous("div", class_="day_header")
        day = " ".join(header.get_text(strip=True).split("|")[0].split()[:2]) if header else "?"

        def text(cls):
            el = item.find(class_=cls)
            return el.get_text(" ", strip=True) if el else ""

        items.append({
            "id": m.group(1),
            "datum": f"{day} {MONTH_ABBR.get(month.split()[0], month)}",
            "titel": text("dayitem_title"),
            "tijd": text("dayitem_timespan"),
            "info": text("dayitem_description").removeprefix("Inplanbaar").strip(),
        })
    if blocks and not any(re.search(r"OpenNewAppointment", b.get("onclick", "")) for b in blocks):
        raise MonitorError(f"{len(blocks)} open opdracht(en) gezien in {month}, maar niet kunnen uitlezen. "
                           "Is de website van Poolmanager veranderd?")
    return month, items


def fetch_items(session):
    all_items, months = {}, []
    r = session.get(AGENDA_URL, timeout=60)
    for i in range(MONTHS):
        r.raise_for_status()
        if "Login.aspx" in r.url:
            raise MonitorError("Uitgelogd tijdens het ophalen van de kalender.")
        soup = BeautifulSoup(r.text, "html.parser")
        month, items = parse_month(soup)
        if month in months:
            raise MonitorError(f"Volgende maand laden mislukt ({month} kwam twee keer).")
        months.append(month)
        print(f"{month}: {len(items)} open opdracht(en)")
        for item in items:
            all_items[item["id"]] = item
        if i < MONTHS - 1:
            data = form_fields(soup, "aspnetForm")
            data.update({"__EVENTTARGET": NEXT_BUTTON, "__EVENTARGUMENT": ""})
            r = session.post(AGENDA_URL, data=data, timeout=60)
    return all_items


def split(body):
    """Verdeel een bericht in delen van max. MAX_BYTES, zonder regels te breken."""
    parts, cur = [], []
    for line in body.split("\n"):
        line = line.encode()[:MAX_BYTES].decode(errors="ignore")  # extreem lange regel afkappen
        if cur and len("\n".join(cur + [line]).encode()) > MAX_BYTES:
            parts.append(cur)
            cur = []
        cur.append(line)
    parts.append(cur)
    if len(parts) > MAX_PARTS:
        parts, more = parts[:MAX_PARTS], "… en meer, zie Poolmanager"
        while len("\n".join(parts[-1] + [more]).encode()) > MAX_BYTES:
            parts[-1].pop()
        parts[-1].append(more)
    return ["\n".join(p) for p in parts]


def send(title, body, priority="default", tags="swimmer"):
    """Alle meldingen gaan via deze functie, zodat de groottegrens altijd geldt.

    priority: ntfy-prioriteit ("default" of "max"). "max" = hard geluid en kan door Niet storen heen.
    """
    topic = os.environ.get("NTFY_TOPIC")
    parts = split(body)
    for n, part in enumerate(parts, 1):
        part_title = title if len(parts) == 1 else f"{title} ({n}/{len(parts)})"
        assert len(part.encode()) <= MAX_BYTES
        if not topic:
            print(f"Geen NTFY_TOPIC ingesteld, niet verstuurd: {part_title}\n{part}")
            continue
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=part.encode("utf-8"),
            headers={"Title": part_title, "Click": AGENDA_URL, "Tags": tags, "Priority": priority},
            timeout=30,
        ).raise_for_status()
        print(f"Melding verstuurd: {part_title} ({len(part.encode())} bytes)")


def describe(item):
    return f"{item['datum']} {item['tijd']} {item['titel']} ({item['info']})"


def notify(items):
    lines = [f"  • {describe(i)}" for i in items]
    send(f"{len(items)} nieuwe opdracht(en) in Poolmanager", "\n".join(lines), priority="max")


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


def summary(seen, items, forced):
    """Overzicht sinds het vorige overzichtsmoment."""
    now = datetime.now(TZ)
    current = current_slot(now)
    since = current if forced else max(t for t in slots(now) if t < current)
    found = {k: v for k, v in seen.items() if v["gevonden"] and datetime.fromisoformat(v["gevonden"]) >= since}
    ok, failed = count_runs(since)
    checks = "?" if ok is None else ok + 1  # +1 voor deze run
    lines = [
        f"Sinds {since:%H:%M} ({'vandaag' if since.date() == now.date() else 'gisteren'}):",
        f"- {checks}x gecontroleerd",
        f"- {len(found)} nieuwe opdracht(en) gevonden" + (":" if found else ""),
    ]
    if failed:
        lines.insert(2, f"- Let op: {failed} controle(s) mislukt")
    expected = int((now - since).total_seconds() // 300)
    if ok is not None and ok + 1 < expected // 2:
        lines.insert(2, f"- Let op: minder controles dan verwacht (~{expected}). Werkt cron-job.org nog?")
    lines += [
        f"  • {v['tekst'] or 'onbekende opdracht'}" + ("" if k in items else " (al weg)")
        for k, v in found.items()
    ]
    lines += ["", f"Je kunt je nu nog inschrijven op {len(items)} opdracht(en) (komende {MONTHS} maanden)" + (":" if items else ".")]
    lines += [f"  • {describe(i)}" for i in items.values()]
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
    return last != slot.isoformat() and datetime.now(TZ) - slot <= timedelta(hours=3)


def mark_summary_sent():
    with open(SUMMARY_FILE, "w") as f:
        f.write(current_slot(datetime.now(TZ)).isoformat() + "\n")


def previous_failures():
    """Aantal mislukte runs direct vóór deze run (via GitHub API), of None als dat niet lukt."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/actions/workflows/monitor.yml/runs", timeout=30,
                         headers={"Authorization": f"Bearer {token}"}, params={"status": "completed", "per_page": 50})
        r.raise_for_status()
    except requests.RequestException:
        return None
    n = 0
    for run in r.json()["workflow_runs"]:
        if run["conclusion"] != "failure":
            break
        n += 1
    return n


def report_failure(error):
    """Waarschuw bij de eerste mislukte controle, daarna elk uur (12 runs) zolang het misgaat."""
    n = previous_failures()
    if n is not None and n % 12:
        print("Fout al eerder gemeld.")
        return
    try:
        send("Poolmanager monitor werkt NIET", f"{error}\n\nDe monitor probeert het elke 5 minuten opnieuw. "
             "Zolang het misgaat krijg je elk uur deze melding. Kijk in GitHub bij Actions voor details.",
             priority="high", tags="warning")
    except Exception as e:  # ntfy zelf onbereikbaar: de rode run in GitHub blijft over
        print("Waarschuwing versturen mislukt:", e)


def report_recovery():
    n = previous_failures()
    if n:
        send("Poolmanager monitor werkt weer", f"Na {n} mislukte controle(s) werkt alles weer.", tags="white_check_mark")


def main():
    try:
        check()
    except Exception as e:
        report_failure(e if isinstance(e, MonitorError) else f"Onverwachte fout: {type(e).__name__}: {e}")
        raise
    report_recovery()


def check():
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (poolmanager-monitor)"
    login(session)
    items = fetch_items(session)

    first_run = not os.path.exists(SEEN_FILE)
    seen = {} if first_run else json.load(open(SEEN_FILE))
    if isinstance(seen, list):  # oud formaat: alleen id's
        seen = {k: "" for k in seen}
    seen = {k: v if isinstance(v, dict) else {"gevonden": v, "tekst": ""} for k, v in seen.items()}
    new = [i for k, i in items.items() if k not in seen]

    if first_run:
        print(f"Eerste keer: {len(items)} opdracht(en) opgeslagen, geen melding.")
    elif new:
        notify(new)
    else:
        print("Geen nieuwe opdrachten.")

    # Bewaar alles wat ooit gezien is, met het moment van vinden en een omschrijving (laatste 1000).
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for k, item in items.items():
        seen.setdefault(k, {"gevonden": "" if first_run else now})["tekst"] = describe(item)
    seen = dict(list(seen.items())[-1000:])
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=1)

    forced = os.environ.get("FORCE_SUMMARY") == "true"
    if forced or summary_due():
        summary(seen, items, forced)
        if not forced:
            mark_summary_sent()


if __name__ == "__main__":
    main()
