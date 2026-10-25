"""Render a GitHub-friendly project directory without custom CSS or dependencies."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- PROJECT-DIRECTORY:START -->"
END = "<!-- PROJECT-DIRECTORY:END -->"


def safe_text(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    value = html.escape(value, quote=True)
    for character in "[]`!*\\|":
        value = value.replace(character, f"&#{ord(character)};")
    return value


def heading_anchor(value: str) -> str:
    # Headings deliberately use a stable ASCII label; icons are outside the anchor.
    return re.sub(r"[^a-z0-9 -]", "", value.lower()).replace(" ", "-")


def directory(config: dict, projects: list[dict]) -> str:
    owner = config["owner"]
    groups = [(category, [p for p in projects if p["category"] == category["id"]])
              for category in config["categories"]]
    groups = [(category, items) for category, items in groups if items]
    out = [START, "", "## Explore a technology", "",
           "Choose a section below, or open its matching filter in the **Repositories** tab.", "",
           "| Technology | Projects | Filter repositories |", "| --- | ---: | --- |"]
    for category, items in groups:
        title = category["title"]
        topic = category["topic"]
        filter_url = f"https://github.com/{owner}?tab=repositories&q={quote('topic:' + topic, safe='')}"
        out.append(f"| **[{safe_text(title)}](#{heading_anchor(title)})** | **{len(items)}** | [Browse projects →]({filter_url}) |")
    for category, items in groups:
        title = category["title"]
        filter_url = f"https://github.com/{owner}?tab=repositories&q={quote('topic:' + category['topic'], safe='')}"
        out += ["", "---", "", f'<a id="{heading_anchor(title)}"></a>', "",
                f"## {category['icon']} {safe_text(title)}", "",
                f"**{len(items)} projects** · [View this category in Repositories →]({filter_url})", ""]
        for project in sorted(items, key=lambda p: p["name"].casefold()):
            name = project["name"]
            url = f"https://github.com/{owner}/{quote(name, safe='-._')}"
            out += [f"### [{safe_text(name)}]({url})", "", safe_text(project["summary"]), ""]
            if project.get("stack"):
                out += ["**Built with:** " + " · ".join(f"**{safe_text(tool)}**" for tool in project["stack"]), ""]
    out += ["---", "", "<sub>New public repositories are checked hourly and grouped by their technology. "
            "Unclear projects appear under Other Projects until their category is refined.</sub>", "", END]
    return "\n".join(out)


def render(config: dict, projects: list[dict], existing: str, initialize: bool = False) -> str:
    block = directory(config, projects)
    if START in existing and END in existing:
        before, tail = existing.split(START, 1)
        _, after = tail.split(END, 1)
        return before + block + after
    if not initialize:
        raise ValueError("README directory markers are missing; refusing to replace custom content")
    header = existing.split("Choose a technology", 1)[0].rstrip()
    return header + "\n\n" + block + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    projects = json.loads((ROOT / "data/projects.json").read_text(encoding="utf-8"))["projects"]
    readme = ROOT / "README.md"
    content = render(config, projects, readme.read_text(encoding="utf-8"), args.initialize)
    readme.write_text(content, encoding="utf-8", newline="\n")
    print(f"Rendered {len(projects)} projects")


if __name__ == "__main__":
    main()
