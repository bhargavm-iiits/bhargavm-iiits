"""Refresh a text contribution summary from GitHub, without static graph images."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os

from render_profile import ROOT
from sync_projects import GitHub

START = "<!-- CONTRIBUTIONS:START -->"
END = "<!-- CONTRIBUTIONS:END -->"
QUERY = """query($login:String!){user(login:$login){contributionsCollection{
  contributionCalendar{totalContributions}
}}}"""


def text_block(owner: str, total: int, checked: str) -> str:
    return "\n".join([
        START, "", f"## {total:,} contributions in the last year", "",
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
    total = response["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    now = datetime.now(timezone.utc)
    automated_commits = count_automation_commits(api, owner, now)
    path = ROOT / "data/contributions.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not needs_refresh(previous, total, automated_commits):
        print("Contribution summary already reflects the latest non-automation activity")
        return
    checked = now.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %H:%M IST")
    readme = ROOT / "README.md"
    content = replace_block(readme.read_text(encoding="utf-8"), text_block(owner, total, checked))
    readme.write_text(content, encoding="utf-8", newline="\n")
    state = {"total": total, "real_activity": total - automated_commits, "checked": checked}
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"GitHub contribution total: {total}")


if __name__ == "__main__":
    main()
