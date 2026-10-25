"""Discover public repositories, infer their stack, add topics, and refresh the profile.

Repository contents are inspected as data. Nothing from another repository is run.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from render_profile import ROOT, render

API = "https://api.github.com"
MAX_TEXT = 80_000
CATEGORY_TOPICS = {
    "virtual-reality": "vr-xr", "augmented-reality": "ar", "unity-simulation": "unity",
    "machine-learning": "ml", "generative-ai": "genai", "full-stack": "fullstack",
    "portfolio": "portfolio", "other-projects": "other",
}


class GitHub:
    def __init__(self, token: str):
        self.token = token

    def request(self, path: str, method: str = "GET", payload=None, missing=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Only GitHub API paths are allowed")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Public-Profile-Sync",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(API + path, data=body, method=method, headers=headers)
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except HTTPError as error:
                if error.code == 404:
                    return missing
                if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                # Error messages never include headers or token-bearing request objects.
                raise RuntimeError(f"GitHub API returned HTTP {error.code} for {method} {path}") from None
            except URLError:
                if attempt == 2:
                    raise RuntimeError(f"GitHub API connection failed for {method} {path}") from None
                time.sleep(2 ** attempt)
        raise RuntimeError("GitHub API retries exhausted")

    def file(self, repository: str, path: str) -> str:
        data = self.request(f"/repos/{repository}/contents/{quote(path, safe='/')}")
        if not isinstance(data, dict) or data.get("type") != "file" or data.get("size", 0) > 150_000:
            return ""
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")[:MAX_TEXT]

    def repositories(self, owner: str) -> list[dict]:
        repos = []
        page = 1
        while True:
            batch = self.request(f"/users/{owner}/repos?type=owner&per_page=100&sort=full_name&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError("Public repository listing was unavailable; existing directory preserved")
            repos.extend(repo for repo in batch if not repo.get("private") and repo["owner"]["login"].casefold() == owner.casefold())
            if len(batch) < 100:
                return repos
            page += 1


def fingerprint(repo: dict) -> str:
    values = {key: repo.get(key) for key in ("pushed_at", "description", "language", "default_branch", "size")}
    values["topics"] = sorted(repo.get("topics") or [])
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def evidence(api: GitHub, repo: dict) -> dict:
    name = repo["full_name"]
    root = api.request(f"/repos/{name}/contents", missing=[])
    paths = [item["name"] for item in root] if isinstance(root, list) else []
    readme_data = api.request(f"/repos/{name}/readme")
    readme = ""
    if isinstance(readme_data, dict) and readme_data.get("size", 0) <= 150_000:
        readme = base64.b64decode(readme_data.get("content", "")).decode("utf-8", errors="replace")[:MAX_TEXT]
    # A bounded selection of manifests gives stronger evidence than language statistics.
    manifests = {}
    candidates = ["package.json", "requirements.txt", "pyproject.toml", "environment.yml"]
    if "Packages" in paths:
        candidates.append("Packages/manifest.json")
    for folder in ("frontend", "backend", "web", "client", "server", "app"):
        if folder in paths:
            candidates.extend([folder + "/package.json", folder + "/requirements.txt", folder + "/pyproject.toml"])
    for path in candidates:
        if "/" not in path and path not in paths:
            continue
        text = api.file(name, path)
        if text:
            manifests[path] = text
    return {"paths": paths, "readme": readme, "manifests": manifests}


def infer_category(repo: dict, info: dict) -> tuple[str, str]:
    topics = set(repo.get("topics") or [])
    for topic, category in CATEGORY_TOPICS.items():
        if topic in topics and category != "other":
            return category, "existing category topic"
    paths = {path.casefold() for path in info.get("paths", [])}
    manifests = info.get("manifests", {})
    dependencies = "\n".join(manifests.values()).casefold()
    description = " ".join([repo["name"], repo.get("description") or "", info.get("readme", "")]).casefold()
    unity = {"assets", "packages", "projectsettings"} <= paths or "com.unity." in dependencies
    if unity:
        ar = any(word in dependencies for word in ("xr.arcore", "xr.arkit", "vuforia"))
        vr = any(word in dependencies for word in ("xr.openxr", "xr.interaction.toolkit", "meta.xr", "openvr", "vrtk"))
        if ar and ("augmented reality" in description or re.search(r"\bar[ _-](navigation|app|project)", description)):
            return "ar", "Unity AR packages and project description"
        if vr:
            return "vr-xr", "Unity XR packages"
        if ar:
            return "ar", "Unity AR packages"
        return "unity", "Unity project structure"
    if any(word in description + dependencies for word in ("webxr", "@react-three/xr", "virtual reality", "360° video")):
        return "vr-xr", "web XR or virtual reality evidence"
    genai = sum(weight for word, weight in (
        ("langgraph", 8), ("langchain", 6), ("retrieval-augmented", 8), ("rag", 5),
        ("ollama", 6), ("diffusers", 8), ("flux", 6), ("generative ai", 8),
        ("openai", 4), ("anthropic", 4), ("google-genai", 4), ("llm", 4),
    ) if re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", description + "\n" + dependencies))
    ml = sum(weight for word, weight in (
        ("tensorflow", 7), ("torch", 5), ("pytorch", 5), ("scikit-learn", 4),
        ("cnn", 7), ("classification", 5), ("machine learning", 5), ("computer vision", 5),
    ) if re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", description + "\n" + dependencies))
    if genai and genai >= ml:
        return "genai", "generative model or retrieval dependencies"
    if ml:
        return "ml", "ML frameworks or model-training evidence"
    if "portfolio" in description:
        return "portfolio", "portfolio project description"
    frontend = any(word in dependencies for word in ('"react"', '"vue"', '"next"', '"svelte"', '"angular"')) or bool(paths & {"frontend", "web", "client"})
    backend = any(word in dependencies for word in ("fastapi", "flask", "django", '"express"', '"nestjs"')) or bool(paths & {"backend", "server", "api"})
    if frontend and backend:
        return "fullstack", "frontend and backend implementation"
    return "other", "insufficient evidence; category can be overridden in profile.json"


def infer_stack(repo: dict, info: dict) -> list[str]:
    dependencies = "\n".join(info.get("manifests", {}).values()).casefold()
    matches = []
    for marker, label in [
        ("com.unity.", "Unity"), ("xr.arfoundation", "AR Foundation"), ("xr.arcore", "ARCore"),
        ("xr.openxr", "OpenXR"), ("xr.interaction.toolkit", "XR Interaction Toolkit"),
        ('"next"', "Next.js"), ('"react"', "React"), ('"vue"', "Vue"), ('"three"', "Three.js"),
        ('"typescript"', "TypeScript"), ('"express"', "Express"), ("fastapi", "FastAPI"),
        ("flask", "Flask"), ("django", "Django"), ("torch", "PyTorch"), ("tensorflow", "TensorFlow"),
        ("scikit-learn", "Scikit-learn"), ("langgraph", "LangGraph"), ("langchain", "LangChain"),
        ("chromadb", "ChromaDB"), ("ollama", "Ollama"), ("openai", "OpenAI"), ("anthropic", "Anthropic"),
        ("google-genai", "Gemini"), ("streamlit", "Streamlit"), ("diffusers", "Diffusers"),
        ("capacitor", "Capacitor"), ("sqlalchemy", "SQLAlchemy"),
    ]:
        if marker in dependencies and label not in matches:
            matches.append(label)
    language = repo.get("language")
    if language and language not in matches and language not in ("Rich Text Format", "Jupyter Notebook", "ShaderLab"):
        matches.append(language)
    return matches[:8]


def merged_topics(existing: list[str], required: str) -> list[str]:
    result = list(dict.fromkeys(existing))
    if required not in result:
        if len(result) >= 20:
            raise ValueError("Repository already has 20 topics; preserving them instead of removing one")
        result.append(required)
    return sorted(result)


def synchronize(config: dict, cached: dict, api: GitHub, update_topics: bool) -> tuple[list[dict], dict]:
    owner = config["owner"]
    categories = {category["id"]: category for category in config["categories"]}
    excluded = set(config.get("exclude_repositories", []))
    previous = {item["name"]: item for item in cached.get("projects", [])}
    repositories = [repo for repo in api.repositories(owner)
                    if repo["name"] not in excluded and not repo.get("private")]
    if previous and not repositories:
        raise RuntimeError("Unexpected empty repository inventory; previous directory preserved")
    projects = []
    added_topics = 0
    for repo in repositories:
        name = repo["name"]
        override = config.get("overrides", {}).get(name)
        old = previous.get(name)
        current_fingerprint = fingerprint(repo)
        if override:
            project = {"name": name, "url": repo["html_url"], **override, "evidence": "curated project classification"}
        elif old and old.get("fingerprint") == current_fingerprint:
            project = dict(old)
        else:
            info = evidence(api, repo)
            category, reason = infer_category(repo, info)
            project = {
                "name": name, "url": repo["html_url"], "category": category,
                "summary": (repo.get("description") or "Public project; see the repository for implementation details.")[:260],
                "stack": infer_stack(repo, info), "evidence": reason,
            }
        required = categories[project["category"]]["topic"]
        topics = repo.get("topics") or []
        desired = merged_topics(topics, required)
        if update_topics and sorted(topics) != desired:
            # Re-read before changing topics to preserve edits made since discovery.
            fresh = api.request(f"/repos/{owner}/{name}/topics")
            if not isinstance(fresh, dict):
                raise RuntimeError(f"Could not read current topics for {name}")
            desired = merged_topics(fresh.get("names", []), required)
            result = api.request(f"/repos/{owner}/{name}/topics", "PUT", {"names": desired})
            if not isinstance(result, dict) or required not in result.get("names", []):
                raise RuntimeError(f"Topic update was not confirmed for {name}")
            repo["topics"] = result["names"]
            added_topics += 1
        project["fingerprint"] = fingerprint(repo)
        projects.append(project)
    projects.sort(key=lambda item: item["name"].casefold())
    report = {"repositories": len(projects), "topics_updated": added_topics,
              "new_projects": sorted(set(p["name"] for p in projects) - set(previous)),
              "other_projects": [p["name"] for p in projects if p["category"] == "other"]}
    return projects, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-topics", action="store_true")
    parser.add_argument("--check", action="store_true", help="Classify and report without writing files or topics")
    args = parser.parse_args()
    if args.check and args.update_topics:
        parser.error("--check cannot be combined with --update-topics")
    config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    token = os.environ.get("PROJECTS_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if args.update_topics and not os.environ.get("PROJECTS_TOKEN"):
        raise RuntimeError("PROJECTS_TOKEN is required to update topics across repositories; see AUTOMATION.md")
    api = GitHub(token)
    if args.update_topics:
        identity = api.request("/user")
        if not identity or identity.get("login", "").casefold() != config["owner"].casefold():
            raise RuntimeError("PROJECTS_TOKEN must belong to the configured repository owner")
    cache_path = ROOT / "data/projects.json"
    cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {"projects": []}
    projects, report = synchronize(config, cached, api, args.update_topics)
    if not args.check:
        readme = ROOT / "README.md"
        text = render(config, projects, readme.read_text(encoding="utf-8"))
        cache_path.parent.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        readme.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(report))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(f"## Profile sync\n\nProjects: **{report['repositories']}**. Topic updates: **{report['topics_updated']}**.\n")
            if report["new_projects"]:
                summary.write("\nNew projects: " + ", ".join(report["new_projects"]) + ".\n")
            if report["other_projects"]:
                summary.write("\nReview category overrides for: " + ", ".join(report["other_projects"]) + ".\n")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"Profile sync failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
