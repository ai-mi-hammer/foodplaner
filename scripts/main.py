"""
Ugentlig madplan-generator — orkestrering.

Kørsel: python scripts/main.py
"""

import os
from datetime import datetime

from modules.utils     import get_week_number, get_next_sunday, get_dated_filename
from modules.offers    import fetch_offers
from modules.meal_plan import generate_meal_plan
from modules.calendar  import build_description, create_event


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

    # 3. Gem filer
    with open('ugens-madplan.md', 'w', encoding='utf-8') as f:
        f.write(meal_plan)
    with open(archive_path, 'w', encoding='utf-8') as f:
        f.write(meal_plan)
    print(f"✅ Gemt til ugens-madplan.md og {archive_path}")

    # 4. Kalenderbegivenhed
    print("📅 Opretter kalenderbegivenhed...")
    try:
        description = build_description(meal_plan, week_number, today, dated_filename)
        event = create_event(description, week_number, next_sunday)
        print(f"✅ Kalenderbegivenhed oprettet: {event.get('htmlLink', '—')}")
    except Exception as e:
        print(f"⚠️  Kalender fejlede (madplanen er stadig gemt): {e}")

    print("🎉 Færdig!")


if __name__ == '__main__':
    main()
