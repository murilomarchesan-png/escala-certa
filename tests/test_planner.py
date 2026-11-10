import sys
from io import BytesIO
from pathlib import Path
import unittest
from zipfile import ZipFile
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
from planner import Model, demo, shift_slots
from server import xlsx

class PlannerTests(unittest.TestCase):
    def test_demo_is_reproducible_and_has_distinct_covered_scenarios(self):
        model = Model(demo())
        result = model.solve()
        self.assertEqual(result, model.solve())
        self.assertGreaterEqual(len(result["scenarios"]), 2)
        for scenario in result["scenarios"]:
            self.assertEqual(scenario["deficit"], 0)
            self.assertEqual(scenario["findings"], [])
            self.assertEqual(scenario["legal"], "PENDING_LEGAL_REVIEW")

    def test_structural_shortage(self):
        config = demo()
        config["demand"][0].update(minimum=8, target=8)
        result = Model(config).solve()
        self.assertGreater(result["structural"], 0)
        self.assertGreaterEqual(result["scenarios"][0]["deficit"], result["structural"])

    def test_demand_applies_to_selected_weekdays(self):
        config = demo()
        config["start"] = "2026-11-18"
        config["demand"] = [dict(shift=0, role="Cozinha", minimum=1, target=1, weekdays=[0, 5])]
        report = Model(config).solve()["scenarios"][0]
        self.assertEqual({slot // 96 for slot, *_ in report["coverage"]}, {3, 5})
        self.assertEqual(report["deficit"], 0)

    def test_pause_and_overnight(self):
        start, end, work = shift_slots(dict(start="21:00", end="02:00", pause_start="23:45", pause_end="00:00"))
        self.assertEqual((start, end, len(work)), (84, 104, 19))
        self.assertNotIn(95, work)
        with self.assertRaises(ValueError):
            shift_slots(dict(start="08:00", end="17:15", pause_start="12:00", pause_end="13:00"))

    def test_seven_day_window_crosses_week_boundary(self):
        config = demo()
        config["days"] = 14
        model = Model(config)
        result = model.report([(2, d, 0, "Cozinha") for d in (2, 3, 4, 5, 6, 7)])
        self.assertTrue(any("janela móvel" in f["message"] for f in result["findings"]))

    def test_overlap_does_not_count_person_twice(self):
        model = Model(demo())
        result = model.report([(6, 0, 1, "Caixa"), (6, 0, 1, "Atendimento")])
        self.assertTrue(result["findings"])
        self.assertEqual(sum(r[4] for r in result["coverage"]), 16)

    def test_unsupported_excluded(self):
        config = demo()
        config["people"][0]["regime"] = "especial"
        result = Model(config).solve()["scenarios"][0]
        self.assertIn(config["people"][0]["name"], result["unsupported"])
        self.assertFalse(any(a[0] == 0 for a in result["assignments"]))

    def test_spreadsheet_contains_valid_xml_and_simulation_label(self):
        model = Model(demo())
        result = model.solve()["scenarios"][0]
        with ZipFile(BytesIO(xlsx(model, result))) as archive:
            self.assertIsNone(archive.testzip())
            for name in archive.namelist():
                ElementTree.fromstring(archive.read(name))
            self.assertIn("Revisão jurídica pendente", archive.read("xl/worksheets/sheet1.xml").decode())
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            names = [sheet.get("name") for sheet in workbook.findall(".//{*}sheet")]
            self.assertEqual(names, ["Gerencial", "Cobertura", *[p["name"] for p in model.people]])
            individual = archive.read("xl/worksheets/sheet3.xml").decode()
            self.assertIn(model.people[0]["name"], individual)
            self.assertNotIn(model.people[1]["name"], individual)

    def test_spreadsheet_sanitizes_duplicate_and_reserved_tab_names(self):
        config = demo()
        for person, name in zip(config["people"], ["Gerencial", "gerencial", "A/B", "A?B"]):
            person["name"] = name
        model = Model(config)
        with ZipFile(BytesIO(xlsx(model, model.report([])))) as archive:
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            names = [sheet.get("name") for sheet in workbook.findall(".//{*}sheet")]
            self.assertEqual(names[:6], ["Gerencial", "Cobertura", "Gerencial (2)", "gerencial (3)", "A B", "A B (2)"])

if __name__ == "__main__":
    unittest.main()
