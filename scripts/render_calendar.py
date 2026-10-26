"""Draw GitHub's daily contribution data as a compact, accessible SVG calendar."""
from __future__ import annotations

from datetime import date
from html import escape

LEVELS = ("NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE")
PALETTES = {
    "light": ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"),
    "dark": ("#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"),
}


def render_calendar(calendar: dict, owner: str, theme: str = "light") -> str:
    palette = PALETTES[theme]
    dark = theme == "dark"
    background = "#0d1117" if dark else "#ffffff"
    foreground = "#f0f6fc" if dark else "#1f2328"
    muted = "#8b949e" if dark else "#57606a"
    border = "#30363d" if dark else "#d1d9e0"
    weeks = calendar["weeks"]
    if not weeks or len(weeks) > 55:
        raise ValueError("Expected a GitHub calendar with one year of weeks")
    all_days = [day for week in weeks for day in week["contributionDays"]]
    if not all_days:
        raise ValueError("The contribution calendar has no days")
    cell, step, left, top = 12, 16, 66, 83
    width = max(930, left + len(weeks) * step + 26)
    height = 235
    total = int(calendar["totalContributions"])
    year = max(date.fromisoformat(day["date"]).year for day in all_days)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
        f'<title id="title">{escape(owner)}: {total:,} contributions in the last year</title>',
        '<desc id="description">Daily GitHub contributions. Each square represents one date; darker green indicates more contributions. Data is refreshed by the profile workflow.</desc>',
        f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="10" fill="{background}" stroke="{border}"/>',
        f'<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif" fill="{foreground}">',
        f'<text x="24" y="34" font-size="21" font-weight="600">{total:,} contributions in the last year</text>',
        f'<text x="24" y="55" font-size="12" fill="{muted}">Daily activity from GitHub</text>',
        f'<text x="{width-26}" y="34" text-anchor="end" font-size="14" fill="{muted}">{year}</text>',
    ]
    months = []
    previous_month = None
    for column, week in enumerate(weeks):
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        if (first.year, first.month) != previous_month:
            months.append((column, first.strftime("%b")))
            previous_month = (first.year, first.month)
    for index, (column, label) in enumerate(months):
        if index + 1 < len(months) and months[index + 1][0] - column < 3:
            continue
        out.append(f'<text x="{left+column*step}" y="72" font-size="11" fill="{muted}">{label}</text>')
    for weekday, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="24" y="{top+weekday*step+10}" font-size="11" fill="{muted}">{label}</text>')
    for column, week in enumerate(weeks):
        for day in week["contributionDays"]:
            stamp = date.fromisoformat(day["date"])
            weekday = int(day["weekday"])
            count = int(day["contributionCount"])
            if not 0 <= weekday <= 6 or count < 0:
                raise ValueError("Invalid contribution calendar day")
            level = day["contributionLevel"]
            if level not in LEVELS:
                raise ValueError("Unknown GitHub contribution level")
            fill = palette[LEVELS.index(level)]
            label = f"{count} contribution{'s' if count != 1 else ''} on {stamp.isoformat()}"
            out.append(f'<rect x="{left+column*step}" y="{top+weekday*step}" width="{cell}" height="{cell}" rx="2" fill="{fill}" data-date="{stamp.isoformat()}" data-count="{count}"><title>{label}</title></rect>')
    legend_x = width - 184
    out.append(f'<text x="24" y="216" font-size="11" fill="{muted}">Each square is one day</text>')
    out.append(f'<text x="{legend_x-35}" y="216" font-size="11" fill="{muted}">Less</text>')
    for index, color in enumerate(palette):
        out.append(f'<rect x="{legend_x+index*16}" y="206" width="12" height="12" rx="2" fill="{color}"/>')
    out += [f'<text x="{legend_x+88}" y="216" font-size="11" fill="{muted}">More</text>', '</g>', '</svg>']
    return "\n".join(out) + "\n"
