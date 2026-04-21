"""Google Calendar — auth, beskrivelse og oprettelse af begivenhed."""

import os
import re
from datetime import datetime, timedelta

import requests

ATTENDEES = [
    'ai.mi.hammer@gmail.com',
    'mikkel.lindberg.hammer@gmail.com',
    'mette.b.jeppesen@gmail.com',
]


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_access_token() -> str:
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


# ── Parse-hjælpere ────────────────────────────────────────────────────────────

def _extract_meals(text: str) -> dict:
    meals = {}
    for line in text.split('\n'):
        for day in ['Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag', 'Weekend']:
            if f'| {day}' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    meal = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', parts[2])
                    meals[day] = meal.strip()
    return meals


def _extract_supermarket(text: str) -> str:
    for line in text.split('\n'):
        if 'Supermarked' in line and ('Føtex' in line or 'SuperBrugsen' in line):
            return 'SuperBrugsen' if 'SuperBrugsen' in line else 'Føtex'
    return 'Føtex'


def _extract_total_budget(text: str) -> str:
    for line in text.split('\n'):
        if '**Total**' in line:
            numbers = re.findall(r'\d+', line)
            if numbers:
                return numbers[-1]
    return '~800'


def _extract_grocery_list(text: str) -> str:
    lines, in_section, result = text.split('\n'), False, []
    for line in lines:
        if '🛒 Indkøbsliste' in line:
            in_section = True
            result.append(line.strip())
            continue
        if in_section:
            if line.startswith('## ') and '🛒' not in line:
                break
            result.append(line.strip())
    return '\n'.join(result).strip()


# ── Beskrivelse & oprettelse ──────────────────────────────────────────────────

def build_description(meal_plan: str, week_number: int, today: datetime, filename: str) -> str:
    meals       = _extract_meals(meal_plan)
    supermarket = _extract_supermarket(meal_plan)
    budget      = _extract_total_budget(meal_plan)
    grocery     = _extract_grocery_list(meal_plan)
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


def create_event(description: str, week_number: int, next_sunday: datetime) -> dict:
    access_token = get_access_token()
    calendar_id  = os.environ.get('CALENDAR_ID', 'ai.mi.hammer@gmail.com')

    event = {
        'summary':     f'🍽️ Ugens Madplan — Uge {week_number}',
        'description': description,
        'colorId':     '10',
        'start':       {'dateTime': next_sunday.strftime('%Y-%m-%dT09:00:00'), 'timeZone': 'Europe/Copenhagen'},
        'end':         {'dateTime': next_sunday.strftime('%Y-%m-%dT09:30:00'), 'timeZone': 'Europe/Copenhagen'},
        'attendees':   [{'email': e} for e in ATTENDEES],
    }

    r = requests.post(
        f'https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events?sendUpdates=all',
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        json=event,
    )
    r.raise_for_status()
    return r.json()
