import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_profile import START, END, directory, render, safe_text
from sync_projects import infer_category, merged_topics, synchronize


def repo(name="new-project", **changes):
    return {"name": name, "full_name": "bhargavm-iiits/" + name,
            "html_url": "https://github.com/bhargavm-iiits/" + name,
            "topics": [], "description": "", "language": "Python", **changes}


def info(dependencies="", readme="", paths=None):
    return {"paths": paths or [], "readme": readme, "manifests": {"manifest": dependencies}}


class ClassificationTests(unittest.TestCase):
    def test_realistic_stack_categories(self):
        cases = [
            (repo(), info('"com.unity.xr.arcore":"6"', "Augmented reality navigation"), "ar"),
            (repo(), info('"com.unity.xr.openxr":"1", "com.unity.xr.arfoundation":"6"', "VR physics"), "vr-xr"),
            (repo(), info(paths=["Assets", "Packages", "ProjectSettings"]), "unity"),
            (repo(), info('"@react-three/xr":"5", "react":"18"'), "vr-xr"),
            (repo(description="CNN plant classification"), info("tensorflow flask"), "ml"),
            (repo(description="Scientific evidence retrieval"), info("langgraph ollama torch"), "genai"),
            (repo(description="Image generation"), info("diffusers torch"), "genai"),
            (repo(), info('"react":"19"\nfastapi'), "fullstack"),
            (repo("my-portfolio"), info('"three":"0.1"'), "portfolio"),
            (repo(), info(), "other"),
        ]
        for metadata, evidence, expected in cases:
            with self.subTest(expected=expected, evidence=evidence):
                self.assertEqual(infer_category(metadata, evidence)[0], expected)

    def test_existing_category_wins_over_ambiguous_dependencies(self):
        self.assertEqual(infer_category(repo(topics=["full-stack"]), info("openai torch"))[0], "fullstack")

    def test_topics_are_preserved(self):
        self.assertEqual(merged_topics(["custom-topic", "python"], "machine-learning"), ["custom-topic", "machine-learning", "python"])

    def test_full_topic_list_is_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            merged_topics([f"topic-{n}" for n in range(20)], "new-category")

    def test_existing_required_topic_is_idempotent(self):
        self.assertEqual(merged_topics(["python", "machine-learning"], "machine-learning"), ["machine-learning", "python"])


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
        self.projects = json.loads((ROOT / "data/projects.json").read_text(encoding="utf-8"))["projects"]

    def test_custom_header_and_footer_are_preserved(self):
        existing = f"My custom header\n{START}\nold\n{END}\nMy footer"
        output = render(self.config, self.projects, existing)
        self.assertTrue(output.startswith("My custom header\n"))
        self.assertTrue(output.endswith("\nMy footer"))

    def test_missing_markers_refuse_to_overwrite(self):
        with self.assertRaises(ValueError):
            render(self.config, self.projects, "My biography")

    def test_repository_descriptions_cannot_inject_markdown_images(self):
        escaped = safe_text('![external](https://example.invalid/pixel) <script>alert(1)</script>')
        self.assertNotIn('![', escaped)
        self.assertNotIn('<script>', escaped)

    def test_render_is_stable_when_inventory_is_unchanged(self):
        first = render(self.config, self.projects, f"Header\n{START}\nold\n{END}\nFooter")
        self.assertEqual(render(self.config, self.projects, first), first)

    def test_all_project_links_and_filters_are_rendered(self):
        output = directory(self.config, self.projects)
        for project in self.projects:
            self.assertIn(f"#### [{project['name']}]", output)
        for category in self.config["categories"]:
            if any(p["category"] == category["id"] for p in self.projects):
                self.assertIn("topic%3A" + category["topic"], output)

    def test_new_repository_is_classified_tagged_and_added(self):
        created = repo("new-vision-app", description="CNN classification", topics=["my-custom-tag"])
        calls = []
        class FakeAPI:
            def repositories(self, owner):
                return [created]
            def request(self, path, method="GET", payload=None, missing=None):
                calls.append((path, method, payload))
                if path.endswith("/readme"):
                    return None
                if path.endswith("/contents"):
                    return []
                if path.endswith("/topics"):
                    return {"names": payload["names"] if method == "PUT" else ["my-custom-tag"]}
                return missing
        projects, report = synchronize(self.config, {"projects": []}, FakeAPI(), True)
        self.assertEqual(projects[0]["category"], "ml")
        self.assertEqual(report["new_projects"], ["new-vision-app"])
        topic_writes = [body for _, method, body in calls if method == "PUT"]
        self.assertEqual(topic_writes, [{"names": ["machine-learning", "my-custom-tag"]}])
        self.assertIn("new-vision-app", directory(self.config, projects))

    def test_empty_inventory_does_not_erase_directory(self):
        class EmptyAPI:
            def repositories(self, owner):
                return []
        with self.assertRaises(RuntimeError):
            synchronize(self.config, {"projects": self.projects}, EmptyAPI(), False)


if __name__ == "__main__":
    unittest.main()
