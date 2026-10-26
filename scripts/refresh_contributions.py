"""Refresh the profile's green daily contribution grid from GitHub's calendar data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import hashlib

from render_profile import ROOT
from render_calendar import render_calendar
from sync_projects import GitHub

START = "<!-- CONTRIBUTIONS:START -->"
END = "<!-- CONTRIBUTIONS:END -->"
QUERY = """query($login:String!){user(login:$login){contributionsCollection{
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday contributionLevel}}}
}}}"""


def text_block(owner: str, total: int, checked: str, version: str = "") -> str:
    asset_root = f"https://raw.githubusercontent.com/{owner}/{owner}/main/assets"
    suffix = f"?v={version}" if version else ""
    return "\n".join([
        START, "", "<picture>",
        f'  <source media="(prefers-color-scheme: dark)" srcset="{asset_root}/contributions-dark.svg{suffix}">',
        f'  <img alt="Daily GitHub contributions: {total:,} contributions in the last year" src="{asset_root}/contributions-light.svg{suffix}" width="100%">',
        "</picture>", "",
        f"[View GitHub's live contribution graph](https://github.com/{owner}#js-contribution-activity-description)", "",
        f"<sub>GitHub contribution data checked {checked}. Refreshed by the hourly workflow.</sub>", "", END,
    ])


def replace_block(readme: str, block: str) -> str:
    if START not in readme or END not in readme:
        raise ValueError("Contribution markers missing; refusing to replace the profile header")
    before, tail = readme.split(START, 1)
    _, after = tail.split(END, 1)
    return before + block + after


def needs_refresh(previous: dict, total: int, automated_commits: int) -> bool:
    if not previous:
        return True
    # Do not create an hourly commit merely to count the previous hourly commit.
    real_activity = total - automated_commits
    return total != previous["total"] and real_activity != previous["real_activity"]


def count_automation_commits(api: GitHub, owner: str, now: datetime) -> int:
    since = (now - timedelta(days=366)).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = 0
    page = 1
    while True:
        commits = api.request(f"/repos/{owner}/{owner}/commits?since={since}&per_page=100&page={page}")
        if not isinstance(commits, list):
            raise RuntimeError("Could not read profile automation history")
        total += sum(commit["commit"]["message"].splitlines()[0] == "Refresh project directory" for commit in commits)
        if len(commits) < 100:
            return total
        page += 1


def main() -> None:
    config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    owner = config["owner"]
    # The repository-scoped token sees public contribution data and does not gain
    # the broader private-repository access of PROJECTS_TOKEN.
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to read GitHub's contribution total")
    api = GitHub(token)
    response = api.request("/graphql", "POST", {"query": QUERY, "variables": {"login": owner}})
    if response.get("errors"):
        raise RuntimeError("GitHub could not provide the public contribution total")
    calendar = response["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    total = calendar["totalContributions"]
    now = datetime.now(timezone.utc)
    automated_commits = count_automation_commits(api, owner, now)
    path = ROOT / "data/contributions.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    window_end = max(day["date"] for week in calendar["weeks"] for day in week["contributionDays"])
    assets = ROOT / "assets"
    graph_missing = any(not (assets / f"contributions-{theme}.svg").exists() for theme in ("light", "dark"))
    if (previous.get("calendar_version") == 1 and previous.get("window_end") == window_end
            and not graph_missing and not needs_refresh(previous, total, automated_commits)):
        print("Contribution calendar already reflects the latest non-automation activity")
        return
    checked = now.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %H:%M IST")
    readme = ROOT / "README.md"
    version = hashlib.sha256(json.dumps(calendar, sort_keys=True).encode()).hexdigest()[:12]
    content = replace_block(readme.read_text(encoding="utf-8"), text_block(owner, total, checked, version))
    assets.mkdir(exist_ok=True)
    for theme in ("light", "dark"):
        (assets / f"contributions-{theme}.svg").write_text(render_calendar(calendar, owner, theme), encoding="utf-8", newline="\n")
    readme.write_text(content, encoding="utf-8", newline="\n")
    state = {"total": total, "real_activity": total - automated_commits, "checked": checked,
             "calendar_version": 1, "window_end": window_end, "calendar": calendar}
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"GitHub contribution total: {total}")


if __name__ == "__main__":
    main()
