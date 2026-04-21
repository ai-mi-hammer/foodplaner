"""Genererer ugentlig madplan via Claude API."""

import os
from datetime import datetime, timedelta

import anthropic

CLAUDE_MODEL = 'claude-sonnet-4-6'


def generate_meal_plan(week_number: int, today: datetime, offers_info: str) -> str:
    client   = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    week_end = today + timedelta(days=6)
    date_range = f"{today.strftime('%d.')}-{week_end.strftime('%d. %B %Y')}"

    prompt = _build_prompt(week_number, today, date_range, offers_info)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text


def _build_prompt(week_number: int, today: datetime, date_range: str, offers_info: str) -> str:
    return f"""Du er en madplanassistent for et dansk vegetarisk par (2 personer).
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
