"""
Henter rigtige opskrifts-URL'er og titler fra valdemarsro.dk og gourministeriet.dk
via WordPress REST API, så Claude kun kan vælge verificerede links.
"""

import requests

HEADERS = {
    'User-Agent': 'MealPlanBot/2.0',
    'Accept': 'application/json',
}

SITES = {
    'valdemarsro.dk':     'https://www.valdemarsro.dk/wp-json/wp/v2/posts',
    'gourministeriet.dk': 'https://gourministeriet.dk/wp-json/wp/v2/posts',
}

FIELDS = 'title,link'
PER_PAGE = 100
MAX_PAGES = 3  # op til 300 opskrifter per site


def _fetch_posts(api_url: str) -> list[dict]:
    """Henter opskrifter fra WordPress REST API (pagineret)."""
    all_posts = []
    for page in range(1, MAX_PAGES + 1):
        try:
            r = requests.get(
                api_url,
                params={'per_page': PER_PAGE, 'page': page, '_fields': FIELDS},
                headers=HEADERS,
                allow_redirects=True,
                timeout=12,
            )
            if not r.ok:
                print(f"  ⚠️  {api_url} side {page}: HTTP {r.status_code} — {r.text[:200]}")
                break
            posts = r.json()
            if not posts:
                break
            all_posts.extend(posts)
            if len(posts) < PER_PAGE:
                break
        except Exception as e:
            print(f"  ⚠️  {api_url} side {page}: {type(e).__name__}: {e}")
            break
    return all_posts


def fetch_recipe_urls() -> dict[str, list[dict]]:
    """
    Returnerer dict med op til 300 opskrifter per site.
    { 'valdemarsro.dk': [{'title': '...', 'link': '...'}, ...], ... }
    """
    result = {}
    for site, api_url in SITES.items():
        posts = _fetch_posts(api_url)
        result[site] = [
            {'title': p.get('title', {}).get('rendered', ''), 'link': p.get('link', '')}
            for p in posts
            if p.get('link')
        ]
    return result


def format_recipe_urls_for_prompt(recipe_urls: dict[str, list[dict]]) -> str:
    """Formaterer opskriftslisterne til en tekstblok til Claude-prompten."""
    lines = [
        '=== VERIFICEREDE OPSKRIFTER ===',
        'Brug KUN URL\'er fra denne liste som opskriftskilder.',
        'Find en opskrift hvis titel matcher retten — brug URL\'en præcist som den står.',
        'Hvis ingen passer, skriv kun domænenavnet (fx valdemarsro.dk).',
        'Find ALDRIG på egne URL-stier.\n',
    ]

    for site, recipes in recipe_urls.items():
        if recipes:
            lines.append(f'--- {site} ({len(recipes)} opskrifter) ---')
            for r in recipes:
                lines.append(f'{r["title"]} → {r["link"]}')
            lines.append('')
        else:
            lines.append(f'--- {site}: ingen opskrifter hentet (brug kun domænenavnet) ---\n')

    return '\n'.join(lines)
