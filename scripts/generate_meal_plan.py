"""
Ugentlig madplan-generator til GitHub Actions.
Kalder Claude API, gemmer madplanen og opretter en Google Calendar invitation.
"""

import anthropic
import requests
import os
import re
from datetime import datetime, timedelta


# ── Hjælpefunktioner ──────────────────────────────────────────────────────────

def get_week_number():
    return datetime.now().isocalendar()[1]

def get_next_sunday():
    today = datetime.now()
    days = (6 - today.weekday()) % 7
    return today + timedelta(days=days if days > 0 else 7)

def get_google_access_token():
    """Henter et frisk Google access token via refresh token."""
    r = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id':     os.environ['GOOGLE_CLIENT_ID'],
        'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
        'refresh_token': os.environ['GOOGLE_REFRESH_TOKEN'],
        'grant_type':    'refresh_token',
    })
    r.raise_for_status()
    return r.json()['access_token']

def fetch_offers():
    """Forsøger at hente aktuelle tilbud fra etilbudsavis.dk."""
    results = []
    endpoints = [
        ('halloumi', 'https://etilbudsavis.dk/soeg/halloumi'),
        ('feta',     'https://etilbudsavis.dk/soeg/feta'),
        ('tofu',     'https://etilbudsavis.dk/soeg/tofu'),
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; MealPlanBot/1.0)'}
    for name, url in endpoints:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.text) > 500:
                # Udtræk kun tekst-indhold (fjern HTML-tags)
                text = re.sub(r'<[^>]+>', ' ', r.text)
                text = re.sub(r'\s+', ' ', text)[:1500]
                results.append(f"[{name}]: {text}")
        except Exception:
            pass
    return '\n'.join(results) if results else 'Kunne ikke hente tilbud automatisk.'


# ── Madplan-generering via Claude API ─────────────────────────────────────────

def generate_meal_plan(week_number: int, today: datetime, offers_info: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    week_end = today + timedelta(days=6)
    date_range = f"{today.strftime('%d.')}-{week_end.strftime('%d. %B %Y')}"

    prompt = f"""Du er en madplanassistent for et dansk vegetarisk par (2 personer).
I dag er det {today.strftime('%A %d. %B %Y')}, uge {week_number}.

TILBUDSINFORMATION DENNE UGE:
{offers_info}

Din opgave er at lave en komplet ugentlig madplan. Brug tilbuddene til at vælge retter.

KRAV:
- Altid for 2 personer
- 5 hverdagsmiddage (man–fre) + valgfrit weekendforslag
- Ingen protein mere end 2 gange per uge (proteiner: halloumi, tofu, feta, æg, laks, bælgfrugter)
- Alt vegetarisk (lejlighedsvist fisk/laks OK)
- Hverdagsretter under 45 min
- Indkøb i Føtex ELLER SuperBrugsen — vælg ét supermarked
- Budget: 700–900 DKK/uge. Flaget hvis over 900 DKK.
- Output på dansk

YNDLINGSRETTER (vælg varieret):
Onepotpasta (vegetar), Pitabrød med fyld, Omelet, Wok med halloumi/tofu,
Tikka Masala med halloumi, Vegetartærte, Vegetarlasagne,
Rugbrød med avocado og kartoffel (eller laks), Madpandekager,
Vietnamesiske forårsruller med peanutbutterdip,
Kartoffelpizza med mascarpone og burrata, Pasta med feta og salat, Risotto

OPSKRIFTSKILDER — henvis til:
- https://valdemarsro.dk
- https://gourministeriet.dk

OUTPUTFORMAT (markdown — følg præcis denne struktur):

# 🗓️ Ugens madplan — Uge {week_number} ({date_range})

> **Supermarked denne uge:** [Føtex eller SuperBrugsen]
> **Budget:** 700–900 DKK/uge for to personer
> Automatisk genereret: {today.strftime('%A %d. %B %Y')}

---

## 🗓️ Ugens madplan

| Dag | Ret | Opskriftskilde |
|-----|-----|----------------|
| Mandag | ... | [link] |
| Tirsdag | ... | [link] |
| Onsdag | ... | [link] |
| Torsdag | ... | [link] |
| Fredag | ... | [link] |
| Weekend (valgfri) | ... | — |

---

## 📋 Opskriftsoversigt

[For hver ret: navn, ingredienser for 2 personer, 5–8 trin på dansk, kilde-URL]

---

## 🛒 Indkøbsliste — [Supermarked]

**Grøntsager & frugt**
- ...

**Mejeri & æg**
- ...

**Tørvarer (pasta, ris, konserves)**
- ...

**Brød & bageri**
- ...

**Frys & køl**
- ...

**Diverse**
- ...

---

## 💰 Estimeret ugentlig pris

| Post | Estimeret pris (DKK) |
|------|----------------------|
| Grøntsager & frugt | ~ DKK |
| Mejeri & æg | ~ DKK |
| Tørvarer | ~ DKK |
| Brød & bageri | ~ DKK |
| Frys & køl | ~ DKK |
| Diverse | ~ DKK |
| **Total** | **~ DKK** |

---

## 🏷️ Ugens tilbud brugt

[Liste over tilbud der er udnyttet og estimeret besparelse]

---

*Madplan genereret automatisk · Uge {week_number} · {today.year} · For 2 personer · Vegetarisk*
"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text


# ── Google Calendar ───────────────────────────────────────────────────────────

def extract_meals(meal_plan_text: str) -> dict:
    """Udtrækker ugens middage fra madplan-teksten."""
    meals = {}
    days = ['Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag', 'Weekend']
    for line in meal_plan_text.split('\n'):
        for day in days:
            if f'| {day}' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    meal = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', parts[2])
                    meals[day] = meal.strip()
    return meals

def extract_supermarket(meal_plan_text: str) -> str:
    for line in meal_plan_text.split('\n'):
        if 'Supermarked' in line and ('Føtex' in line or 'SuperBrugsen' in line):
            return 'SuperBrugsen' if 'SuperBrugsen' in line else 'Føtex'
    return 'Føtex'

def extract_total_budget(meal_plan_text: str) -> str:
    for line in meal_plan_text.split('\n'):
        if '**Total**' in line:
            numbers = re.findall(r'\d+', line)
            if numbers:
                return numbers[-1]
    return '~800'

def build_calendar_description(meal_plan_text: str, week_number: int, today: datetime) -> str:
    meals = extract_meals(meal_plan_text)
    supermarket = extract_supermarket(meal_plan_text)
    budget = extract_total_budget(meal_plan_text)
    week_end = today + timedelta(days=6)
    date_range = f"{today.strftime('%d.')}-{week_end.strftime('%d. %B %Y')}"

    return f"""🗓️ Ugens middage ({date_range})

🛒 Supermarked: {supermarket} | 💰 Budget: ~{budget} DKK

━━━━━━━━━━━━━━━━━━━━━━
Mandag     → {meals.get('Mandag', '—')}
Tirsdag    → {meals.get('Tirsdag', '—')}
Onsdag     → {meals.get('Onsdag', '—')}
Torsdag    → {meals.get('Torsdag', '—')}
Fredag     → {meals.get('Fredag', '—')}
Weekend    → {meals.get('Weekend', '—')} (valgfri)
━━━━━━━━━━━━━━━━━━━━━━

📋 Se fuld opskriftsoversigt og indkøbsliste i GitHub-repoet (ugens-madplan.md)"""

def create_calendar_event(description: str, week_number: int, next_sunday: datetime):
    access_token = get_google_access_token()
    calendar_id  = os.environ.get('CALENDAR_ID', 'ai.mi.hammer@gmail.com')

    sunday_str = next_sunday.strftime('%Y-%m-%d')
    monday_str = (next_sunday + timedelta(days=1)).strftime('%Y-%m-%d')

    event = {
        'summary':     f'🍽️ Ugens Madplan — Uge {week_number}',
        'description': description,
        'colorId':     '10',
        'start':       {'date': sunday_str},
        'end':         {'date': monday_str},
        'attendees':   [
            {'email': 'ai.mi.hammer@gmail.com'},
            {'email': 'mikkel.lindberg.hammer@gmail.com'},
            {'email': 'mette.b.jeppesen@gmail.com'},
        ],
    }

    r = requests.post(
        f'https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events?sendUpdates=all',
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        json=event,
    )
    r.raise_for_status()
    return r.json()


# ── Hovedprogram ──────────────────────────────────────────────────────────────

def main():
    today       = datetime.now()
    week_number = get_week_number()
    next_sunday = get_next_sunday()

    print(f"🍽️  Genererer madplan for uge {week_number}...")

    # 1. Hent tilbud
    print("🔍 Henter tilbud fra etilbudsavis.dk...")
    offers = fetch_offers()

    # 2. Generér madplan via Claude
    print("🤖 Kalder Claude API...")
    meal_plan = generate_meal_plan(week_number, today, offers)
    print("✅ Madplan genereret")

    # 3. Gem til fil
    with open('ugens-madplan.md', 'w', encoding='utf-8') as f:
        f.write(meal_plan)
    print("✅ Gemt til ugens-madplan.md")

    # 4. Opret Google Calendar begivenhed
    print("📅 Opretter kalenderbegivenhed...")
    try:
        description = build_calendar_description(meal_plan, week_number, today)
        event = create_calendar_event(description, week_number, next_sunday)
        print(f"✅ Kalenderbegivenhed oprettet: {event.get('htmlLink', '—')}")
    except Exception as e:
        print(f"⚠️  Kalender fejlede (madplanen er stadig gemt): {e}")

    print("🎉 Færdig!")


if __name__ == '__main__':
    main()
