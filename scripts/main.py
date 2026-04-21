"""
Ugentlig madplan-generator — orkestrering.

Kørsel: python scripts/main.py
"""

import os
from datetime import datetime, timedelta

from modules.utils     import get_next_sunday, get_dated_filename
from modules.offers    import fetch_offers
from modules.recipes   import fetch_recipe_urls, format_recipe_urls_for_prompt
from modules.meal_plan import generate_meal_plan
from modules.calendar  import build_description, create_event


def main():
    today       = datetime.now()
    next_sunday = get_next_sunday()

    # Kører på søndag → planlæg for ugen der starter i morgen (mandag)
    if today.weekday() == 6:
        today = today + timedelta(days=1)

    week_number = today.isocalendar()[1]

    print(f"🍽️  Genererer madplan for uge {week_number}...")

    # Filnavne
    dated_filename = get_dated_filename(today, week_number)
    archive_path   = f"arkiv/{dated_filename}"
    os.makedirs('arkiv', exist_ok=True)

    # 1. Hent tilbud
    print("🔍 Henter tilbud fra etilbudsavis.dk...")
    offers = fetch_offers()

    # 2. Hent verificerede opskrifts-URL'er
    print("📖 Henter opskrifts-URL'er fra valdemarsro.dk og gourministeriet.dk...")
    recipe_urls = fetch_recipe_urls()
    total = sum(len(v) for v in recipe_urls.values())
    print(f"✅ Fandt {total} opskrifts-URL'er")
    recipe_info = format_recipe_urls_for_prompt(recipe_urls)

    # 3. Generér madplan via Claude
    print("🤖 Kalder Claude API...")
    meal_plan = generate_meal_plan(week_number, today, offers, recipe_info)
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
