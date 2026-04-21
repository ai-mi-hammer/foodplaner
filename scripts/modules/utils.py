"""Dato- og filnavne-hjælpere."""

from datetime import datetime, timedelta


def get_week_number() -> int:
    return datetime.now().isocalendar()[1]


def get_next_sunday() -> datetime:
    today = datetime.now()
    days = (6 - today.weekday()) % 7
    return today + timedelta(days=days if days > 0 else 7)


def get_dated_filename(today: datetime, week_number: int) -> str:
    """Returnerer fx 'ugens-madplan-uge17-21apr-27apr2026.md'."""
    week_end = today + timedelta(days=6)
    start = today.strftime('%d%b').lower()
    end   = week_end.strftime('%d%b%Y').lower()
    danish_months = {
        'jan': 'jan', 'feb': 'feb', 'mar': 'mar', 'apr': 'apr',
        'may': 'maj', 'jun': 'jun', 'jul': 'jul', 'aug': 'aug',
        'sep': 'sep', 'oct': 'okt', 'nov': 'nov', 'dec': 'dec',
    }
    for en, da in danish_months.items():
        start = start.replace(en, da)
        end   = end.replace(en, da)
    return f"ugens-madplan-uge{week_number}-{start}-{end}.md"
