from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_calendar import render_calendar

CALENDAR = {"totalContributions": 5, "weeks": [{"contributionDays": [
    {"date": "2026-10-24", "weekday": 6, "contributionCount": 2, "contributionLevel": "FIRST_QUARTILE"},
    {"date": "2026-10-25", "weekday": 0, "contributionCount": 3, "contributionLevel": "FOURTH_QUARTILE"},
]}]}
NS = {"svg": "http://www.w3.org/2000/svg"}


class CalendarTests(unittest.TestCase):
    def test_actual_dates_and_counts_are_preserved(self):
        root = ET.fromstring(render_calendar(CALENDAR, "bhargavm-iiits"))
        cells = [node for node in root.findall(".//svg:rect", NS) if "data-date" in node.attrib]
        self.assertEqual([(c.attrib["data-date"], c.attrib["data-count"]) for c in cells], [("2026-10-24", "2"), ("2026-10-25", "3")])

    def test_sunday_and_saturday_use_the_correct_rows(self):
        root = ET.fromstring(render_calendar(CALENDAR, "bhargavm-iiits"))
        cells = [node for node in root.findall(".//svg:rect", NS) if "data-date" in node.attrib]
        self.assertGreater(int(cells[0].attrib["y"]), int(cells[1].attrib["y"]))

    def test_dark_mode_retains_the_same_counts(self):
        light = ET.fromstring(render_calendar(CALENDAR, "bhargavm-iiits", "light"))
        dark = ET.fromstring(render_calendar(CALENDAR, "bhargavm-iiits", "dark"))
        light_days = [n for n in light.findall(".//svg:rect", NS) if "data-date" in n.attrib]
        dark_days = [n for n in dark.findall(".//svg:rect", NS) if "data-date" in n.attrib]
        self.assertEqual(len(light_days), 2)
        self.assertEqual(len(dark_days), 2)
        for left, right in zip(light_days, dark_days):
            self.assertEqual(left.attrib["data-count"], right.attrib["data-count"])
            self.assertNotEqual(left.attrib["fill"], right.attrib["fill"])

    def test_no_script_or_external_resource_is_embedded(self):
        svg = render_calendar(CALENDAR, "bhargavm-iiits")
        self.assertNotIn("<script", svg)
        self.assertNotIn("href=", svg)

    def test_invalid_data_is_rejected(self):
        with self.assertRaises(ValueError):
            render_calendar({"totalContributions": 0, "weeks": []}, "bhargavm-iiits")


if __name__ == "__main__":
    unittest.main()
