"""
Henter rigtige opskrifts-URL'er og titler fra valdemarsro.dk og gourministeriet.dk.

- gourministeriet.dk: WordPress REST API (åben)
- valdemarsro.dk: sitemap.xml (REST API kræver login)
"""

import re
import requests

HEADERS = {
    'User-Agent': 'MealPlanBot/2.0',
    'Accept': '*/*',
}

PER_PAGE = 100
MAX_PAGES = 3


# ── gourministeriet.dk via WP REST API ───────────────────────────────────────

def _fetch_gourministeriet() -> list[dict]:
    api_url = 'https://gourministeriet.dk/wp-json/wp/v2/posts'
    all_posts = []
    for page in range(1, MAX_PAGES + 1):
        try:
            r = requests.get(
                api_url,
                params={'per_page': PER_PAGE, 'page': page, '_fields': 'title,link'},
                headers=HEADERS,
                timeout=12,
            )
            if not r.ok:
                print(f"  ⚠️  gourministeriet side {page}: HTTP {r.status_code}")
                break
            posts = r.json()
            if not posts:
                break
            all_posts.extend(posts)
            if len(posts) < PER_PAGE:
                break
        except Exception as e:
            print(f"  ⚠️  gourministeriet: {e}")
            break
    return [
        {'title': p.get('title', {}).get('rendered', ''), 'link': p.get('link', '')}
        for p in all_posts if p.get('link')
    ]


# ── valdemarsro.dk via sitemap ────────────────────────────────────────────────

VALDEMARSRO_SITEMAPS = [
    'https://www.valdemarsro.dk/wp-sitemap.xml',        # WordPress 5.5+ index
    'https://www.valdemarsro.dk/sitemap_index.xml',     # Yoast SEO index
    'https://www.valdemarsro.dk/sitemap.xml',           # generisk
    'https://www.valdemarsro.dk/wp-sitemap-posts-post-1.xml',  # WP direkte
]

# Slugs der indikerer en opskrift
RECIPE_SLUGS = [
    'opskrift', 'ret', 'suppe', 'salat', 'pasta', 'pizza', 'burger',
    'wok', 'curry', 'taerte', 'tærte', 'gryde', 'steg', 'frikadell',
    'lasagne', 'risotto', 'falafel', 'omelet', 'pandekag', 'tofu',
    'halloumi', 'laks', 'kylling', 'tikka', 'tacos', 'pitabroed',
    'foraarsrulle', 'kartoffel', 'groentsag', 'vegetar', 'fisk',
]

EXCLUDE = ['/category/', '/tag/', '/author/', '/page/']


def _is_recipe_url(url: str) -> bool:
    u = url.lower()
    if any(ex in u for ex in EXCLUDE):
        return False
    # Hent stien efter domænet
    path = u.split('valdemarsro.dk/', 1)[-1].rstrip('/')
    return any(kw in path for kw in RECIPE_SLUGS)


def _slug_to_title(url: str) -> str:
    """Lav en læsbar titel fra URL-slug: 'laks-med-citron' → 'Laks med citron'."""
    slug = url.rstrip('/').split('/')[-1]
    return slug.replace('-', ' ').capitalize()


def _fetch_sitemap_locs(url: str) -> list[str]:
    """Henter alle <loc>-værdier fra en sitemap-URL."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if not r.ok:
            print(f"  ⚠️  valdemarsro {url}: HTTP {r.status_code}")
            return []
        return re.findall(r'<loc>(https?://[^<]+)</loc>', r.text)
    except Exception as e:
        print(f"  ⚠️  valdemarsro {url}: {e}")
        return []


def _fetch_valdemarsro() -> list[dict]:
    for sitemap_url in VALDEMARSRO_SITEMAPS:
        locs = _fetch_sitemap_locs(sitemap_url)
        if not locs:
            continue

        # Er det et sitemap-index? (indeholder .xml-links → resolve child-sitemaps)
        child_sitemaps = [l for l in locs if l.endswith('.xml')]
        if child_sitemaps:
            print(f"  📋 valdemarsro sitemap-index fundet: {len(child_sitemaps)} child-sitemaps")
            all_locs = []
            for child in child_sitemaps:
                if 'post' in child:  # kun post-sitemaps, ikke categories/tags
                    all_locs.extend(_fetch_sitemap_locs(child))
            locs = all_locs

        recipe_urls = [u for u in locs if _is_recipe_url(u)]
        if recipe_urls:
            print(f"  ✅ valdemarsro: {len(recipe_urls)} opskrifter fra {sitemap_url}")
            return [{'title': _slug_to_title(u), 'link': u} for u in recipe_urls[:300]]

    print("  ⚠️  valdemarsro: ingen opskrifter hentet fra sitemaps")
    return []


# ── Fælles interface ──────────────────────────────────────────────────────────

def fetch_recipe_urls() -> dict[str, list[dict]]:
    return {
        'valdemarsro.dk':     _fetch_valdemarsro(),
        'gourministeriet.dk': _fetch_gourministeriet(),
    }


def format_recipe_urls_for_prompt(recipe_urls: dict[str, list[dict]]) -> str:
    lines = [
        '=== VERIFICEREDE OPSKRIFTER ===',
        "Brug KUN URL'er fra denne liste som opskriftskilder.",
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
