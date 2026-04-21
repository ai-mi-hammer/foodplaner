"""
Henter aktuelle tilbud fra Tjek-API'et (backendet bag etilbudsavis.dk).

Returnerer en tekstblok til Claude med:
  - Føtex-tilbudsavisens produkter som madinspirations-kilde
  - Produktsøgninger med faktiske tilbudspriser (mærket TILBUDSPRIS)
"""

import requests

FOETEX_DEALER_ID = 'bdf5A'
TJEK_SEARCH      = 'https://squid-api.tjek.com/v2/offers/search'
TJEK_FRONTS      = 'https://squid-api.tjek.com/v2/dealerfront'

HEADERS = {
    'Accept':     'application/json',
    'User-Agent': 'MealPlanBot/2.0',
}

PRODUKTER = [
    'halloumi', 'feta', 'burrata', 'mascarpone', 'mozzarella',
    'tofu', 'kikærter', 'æg',
    'spinat', 'peberfrugt', 'avocado', 'kartofler', 'tomater', 'agurk',
    'pasta', 'ris', 'nudler', 'pitabrød',
    'kylling', 'laks', 'hakket oksekød',
    'mælk', 'smør', 'yoghurt', 'fløde',
]


def _fetch_publication_inspiration() -> list[str]:
    """Henter produktnavne fra Føtex-tilbudsavisen som madinspirations-kilde."""
    try:
        r = requests.get(
            TJEK_FRONTS,
            params={'dealer_id': FOETEX_DEALER_ID, 'limit': 100},
            headers=HEADERS,
            timeout=12,
        )
        if not r.ok:
            return []
        data = r.json()
        items = data if isinstance(data, list) else data.get('results', [])
        lines = []
        for item in items[:60]:
            heading = item.get('heading') or item.get('name', '')
            price   = (item.get('pricing') or {}).get('price', '')
            if heading:
                lines.append(heading + (f" ({price} DKK)" if price else ''))
        return lines
    except Exception:
        return []


def _search_product(produkt: str) -> list[str]:
    """Søger på ét produkt hos Føtex og returnerer formaterede linjer."""
    try:
        r = requests.get(
            TJEK_SEARCH,
            params={
                'query':      produkt,
                'dealer_ids': FOETEX_DEALER_ID,
                'limit':      3,
            },
            headers=HEADERS,
            timeout=10,
        )
        if not r.ok:
            return []
        items = r.json() if isinstance(r.json(), list) else r.json().get('results', [])
        lines = []
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
                lines.append(line)
        return lines
    except Exception:
        return []


def fetch_offers() -> str:
    """Returnerer tilbudsinfo som tekstblok klar til Claude-prompten."""
    sections = []

    # 1. Tilbudsavis-inspiration
    inspiration = _fetch_publication_inspiration()
    if inspiration:
        sections.append("=== FØTEX TILBUDSAVIS (inspiration til retter) ===")
        sections.extend(inspiration)

    # 2. Produktsøgninger med priser
    sections.append("\n=== PRODUKTSØGNING HOS FØTEX ===")
    sections.append("VIGTIGT: Priser mærket 'TILBUDSPRIS' er faktiske priser fra tilbudsavisen.")
    sections.append("Brug dem præcist på indkøbslisten (ingen 'ca.'). Estimér kun varer uden tilbudspris.\n")

    for produkt in PRODUKTER:
        sections.extend(_search_product(produkt))

    if len(sections) <= 4:
        return 'Kunne ikke hente tilbud fra Tjek-API — brug estimerede priser.'

    return '\n'.join(sections)
