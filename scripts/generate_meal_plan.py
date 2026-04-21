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
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"Google token fejl {r.status_code}: {detail}")
    return r.json()['access_token']

def fetch_offers():
    """
    Henter aktuelle tilbud fra Tjek-API'et (backendet bag etilbudsavis.dk).
    Søger på relevante produkter hos Føtex (dealer ID: bdf5A).
    Henter også Føtex-publikationens aktuelle produkter som madinspirationskilde.
    """
    FOETEX_DEALER_ID = 'bdf5A'
    TJEK_SEARCH      = 'https://squid-api.tjek.com/v2/offers/search'
    TJEK_FRONTS      = 'https://squid-api.tjek.com/v2/dealerfront'
    headers = {
        'Accept':     'application/json',
        'User-Agent': 'MealPlanBot/2.0',
    }
    results = []

    # ── 1. Hent aktuelle Føtex-tilbudsavis for madinspirations-produkter ──────
    try:
        r = requests.get(
            TJEK_FRONTS,
            params={'dealer_id': FOETEX_DEALER_ID, 'limit': 100},
            headers=headers, timeout=12,
        )
        if r.ok:
            data = r.json()
            # Udtræk produktnavne fra avisen som rå inspiration til Claude
            names = []
            for item in data if isinstance(data, list) else data.get('results', []):
                heading = item.get('heading') or item.get('name', '')
                price   = item.get('pricing', {}).get('price') or item.get('price', '')
                if heading:
                    names.append(f"{heading}" + (f" ({price} DKK)" if price else ''))
            if names:
                results.append("=== FØTEX TILBUDSAVIS (inspiration til retter) ===")
                results.extend(names[:60])
    except Exception:
        pass

    # ── 2. Søg på konkrete produkter vi altid vil kende prisen på ─────────────
    produkter = [
        'halloumi', 'feta', 'burrata', 'mascarpone', 'mozzarella',
        'tofu', 'kikærter', 'æg',
        'spinat', 'peberfrugt', 'avocado', 'kartofler', 'tomater', 'agurk',
        'pasta', 'ris', 'nudler', 'pitabrød',
        'kylling', 'laks', 'hakket oksekød',
        'mælk', 'smør', 'yoghurt', 'fløde',
    ]

    results.append("\n=== PRODUKTSØGNING HOS FØTEX ===")
    results.append("VIGTIGT: Priser mærket med 'TILBUDSPRIS' er faktiske priser fra tilbudsavisen.")
    results.append("Brug dem præcist på indkøbslisten (ingen 'ca.'). Estimér kun priser der IKKE er i tilbudsavisen.\n")

    for produkt in produkter:
        try:
            r = requests.get(
                TJEK_SEARCH,
                params={
                    'query':      produkt,
                    'dealer_ids': FOETEX_DEALER_ID,
                    'limit':      3,
                },
                headers=headers, timeout=10,
            )
            if r.ok:
                items = r.json() if isinstance(r.json(), list) else r.json().get('results', [])
                for item in items[:3]:
                    heading   = item.get('heading', '')
                    desc      = item.get('description', '')
                    pricing   = item.get('pricing') or {}
                    price     = pricing.get('price', '')
                    pre_price = pricing.get('pre_price', '')
                    store     = (item.get('branding') or {}).get('name', '')
                    if heading:
                        line = f"[{produkt}] {heading}"
                        if desc:      line += f" — {desc}"
                        if price:     line += f" → TILBUDSPRIS: {price} DKK"
                        if pre_price: line += f" (normalpris: {pre_price} DKK)"
                        if store:     line += f" ✅ {store}"
                        results.append(line)
        except Exception:
            pass

    if len(results) <= 4:
        return 'Kunne ikke hente tilbud fra Tjek-API — brug estimerede priser.'

    return '\n'.join(results)


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

PRISER PÅ INDKØBSLISTEN:
- Varer mærket "TILBUDSPRIS" i tilbudsinformationen har en faktisk pris fra tilbudsavisen.
  Brug denne pris præcist — INGEN "ca." foran tilbudspriser.
- Varer uden tilbudspris: estimér prisen og skriv "ca. XX DKK".
- Eksempel: "Halloumi 225g → 29 DKK" (tilbud) vs. "Pasta 500g — ca. 15 DKK" (estimat).

KRAV:
- Altid for 2 personer
- 5 hverdagsmiddage (man–fre) + valgfrit weekendforslag
- Præcis 1 køddagret per uge (kylling, oksekød, lam eller svinekød)
- Resten vegetarisk (fisk/laks tæller som vegetar her)
- Ingen protein mere end 2 gange per uge (proteiner: halloumi, tofu, feta, æg, laks, bælgfrugter, kylling, oksekød)
- Hverdagsretter under 45 min
- Indkøb i Føtex ELLER SuperBrugsen — vælg ét supermarked
- Budget: 700–900 DKK/uge. Flaget hvis over 900 DKK.
- Output på dansk

YNDLINGSRETTER (vælg varieret):
Vegetar: Onepotpasta, Pitabrød med fyld, Omelet, Wok med halloumi/tofu,
Tikka Masala med halloumi, Vegetartærte, Vegetarlasagne,
Rugbrød med avocado og kartoffel, Madpandekager,
Vietnamesiske forårsruller med peanutbutterdip,
Kartoffelpizza med mascarpone og burrata, Pasta med feta og salat, Risotto

Kød (vælg 1 per uge): Kyllingepasta, Kylling i ovn med rodfrugter,
Kødsovs med pasta, Wok med kylling, Tacos med hakket oksekød,
Kyllingesuppe, Laks med kartofler og grønt, Kylling tikka masala

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

def get_dated_filename(today: datetime, week_number: int) -> str:
    """Genererer filnavn med uge og datointerval, fx ugens-madplan-uge17-21apr-27apr2026.md"""
    week_end = today + timedelta(days=6)
    start = today.strftime('%d%b').lower()
    end   = week_end.strftime('%d%b%Y').lower()
    # Dansk månedsforkortelse
    danish_months = {
        'jan': 'jan', 'feb': 'feb', 'mar': 'mar', 'apr': 'apr',
        'may': 'maj', 'jun': 'jun', 'jul': 'jul', 'aug': 'aug',
        'sep': 'sep', 'oct': 'okt', 'nov': 'nov', 'dec': 'dec',
    }
    for en, da in danish_months.items():
        start = start.replace(en, da)
        end   = end.replace(en, da)
    return f"ugens-madplan-uge{week_number}-{start}-{end}.md"

def extract_grocery_list(meal_plan_text: str) -> str:
    """Udtrækker indkøbslisten fra madplan-teksten."""
    lines = meal_plan_text.split('\n')
    in_grocery = False
    grocery_lines = []
    for line in lines:
        if '🛒 Indkøbsliste' in line:
            in_grocery = True
            grocery_lines.append(line.strip())
            continue
        if in_grocery:
            if line.startswith('## ') and '🛒' not in line:
                break
            grocery_lines.append(line.strip())
    return '\n'.join(grocery_lines).strip()

def extract_offers_used(meal_plan_text: str) -> str:
    """Udtrækker tilbudssektionen fra madplan-teksten."""
    lines = meal_plan_text.split('\n')
    in_offers = False
    offer_lines = []
    for line in lines:
        if '🏷️' in line and 'tilbud' in line.lower():
            in_offers = True
            continue
        if in_offers:
            if line.startswith('## ') or line.startswith('---') or line.startswith('*Madplan'):
                break
            if line.strip():
                offer_lines.append(line.strip())
    return '\n'.join(offer_lines).strip()

def build_calendar_description(meal_plan_text: str, week_number: int, today: datetime, filename: str) -> str:
    """Simpel beskrivelse: madplan-tabel + indkøbsliste + link til GitHub."""
    meals       = extract_meals(meal_plan_text)
    supermarket = extract_supermarket(meal_plan_text)
    budget      = extract_total_budget(meal_plan_text)
    grocery     = extract_grocery_list(meal_plan_text)
    week_end    = today + timedelta(days=6)
    date_range  = f"{today.strftime('%d.')}-{week_end.strftime('%d. %B %Y')}"
    github_link = f"https://github.com/ai-mi-hammer/foodplaner/blob/main/arkiv/{filename}"

    return f"""🗓️ Ugens middage ({date_range})
🛒 Supermarked: {supermarket} | 💰 Budget: ~{budget} DKK

Mandag     → {meals.get('Mandag', '—')}
Tirsdag    → {meals.get('Tirsdag', '—')}
Onsdag     → {meals.get('Onsdag', '—')}
Torsdag    → {meals.get('Torsdag', '—')}
Fredag     → {meals.get('Fredag', '—')}
Weekend    → {meals.get('Weekend', '—')} (valgfri)

{grocery}

📋 Fuld madplan med opskrifter: {github_link}"""

def create_calendar_event(description: str, week_number: int, next_sunday: datetime):
    access_token = get_google_access_token()
    calendar_id  = os.environ.get('CALENDAR_ID', 'ai.mi.hammer@gmail.com')

    # Søndag kl. 9:00–9:30 dansk tid (Europe/Copenhagen)
    sunday_start = next_sunday.strftime('%Y-%m-%dT09:00:00')
    sunday_end   = next_sunday.strftime('%Y-%m-%dT09:30:00')

    event = {
        'summary':     f'🍽️ Ugens Madplan — Uge {week_number}',
        'description': description,
        'colorId':     '10',
        'start':       {'dateTime': sunday_start, 'timeZone': 'Europe/Copenhagen'},
        'end':         {'dateTime': sunday_end,   'timeZone': 'Europe/Copenhagen'},
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

    # Filnavne
    dated_filename = get_dated_filename(today, week_number)
    archive_path   = f"arkiv/{dated_filename}"
    os.makedirs('arkiv', exist_ok=True)

    # 1. Hent tilbud
    print("🔍 Henter tilbud fra etilbudsavis.dk...")
    offers = fetch_offers()

    # 2. Generér madplan via Claude
    print("🤖 Kalder Claude API...")
    meal_plan = generate_meal_plan(week_number, today, offers)
    print("✅ Madplan genereret")

    # 3. Gem til fil — både som løbende og dateret arkivfil
    with open('ugens-madplan.md', 'w', encoding='utf-8') as f:
        f.write(meal_plan)
    with open(archive_path, 'w', encoding='utf-8') as f:
        f.write(meal_plan)
    print(f"✅ Gemt til ugens-madplan.md og {archive_path}")

    # 4. Opret Google Calendar begivenhed
    print("📅 Opretter kalenderbegivenhed...")
    try:
        description = build_calendar_description(meal_plan, week_number, today, dated_filename)
        event = create_calendar_event(description, week_number, next_sunday)
        print(f"✅ Kalenderbegivenhed oprettet: {event.get('htmlLink', '—')}")
    except Exception as e:
        print(f"⚠️  Kalender fejlede (madplanen er stadig gemt): {e}")

    print("🎉 Færdig!")


if __name__ == '__main__':
    main()
