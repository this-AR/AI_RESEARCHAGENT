import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from ai_research_agent.errors import WorkflowError
from ai_research_agent.file_parser import parse_csv, parse_file, parse_json


class ParseCSVTests(TestCase):
    def test_parse_valid_csv(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "leads.csv"
            path.write_text(
                "company_name,industry,key_decision_maker,position,recent_milestone\n"
                "Acme,Technology,Alice,CEO,Product launch\n"
                "Globex,Manufacturing,Bob,CTO,Factory expansion\n",
                encoding="utf-8",
            )
            targets, errors = parse_csv(path)
            self.assertEqual(len(targets), 2)
            self.assertEqual(errors, [])
            self.assertEqual(targets[0].company_name, "Acme")

    def test_rejects_missing_header(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("name,industry\nAcme,Technology\n", encoding="utf-8")
            targets, errors = parse_csv(path)
            self.assertEqual(len(targets), 0)
            self.assertTrue(any("missing required header" in e for e in errors))

    def test_rejects_empty_field(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(
                "company_name,industry,key_decision_maker,position,recent_milestone\n"
                "Acme,Technology,,CEO,Launch\n",
                encoding="utf-8",
            )
            targets, errors = parse_csv(path)
            self.assertEqual(len(targets), 0)
            self.assertTrue(any("empty" in e for e in errors))

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(WorkflowError):
            parse_csv("/nonexistent/file.csv")


class ParseJSONTests(TestCase):
    def test_parse_list(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "leads.json"
            data = [
                {
                    "company_name": "Acme",
                    "industry": "Tech",
                    "key_decision_maker": "Alice",
                    "position": "CEO",
                    "recent_milestone": "IPO",
                }
            ]
            path.write_text(json.dumps(data), encoding="utf-8")
            targets, _errors = parse_json(path)
            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0].key_decision_maker, "Alice")

    def test_parse_single_object(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "lead.json"
            data = {
                "company_name": "Acme",
                "industry": "Tech",
                "key_decision_maker": "Alice",
                "position": "CEO",
                "recent_milestone": "IPO",
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            targets, _errors = parse_json(path)
            self.assertEqual(len(targets), 1)

    def test_rejects_invalid_root(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("\"just a string\"", encoding="utf-8")
            targets, errors = parse_json(path)
            self.assertEqual(len(targets), 0)
            self.assertTrue(any("object or a list" in e for e in errors))


class ParseFileAutoTests(TestCase):
    def test_auto_csv(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "leads.csv"
            path.write_text(
                "company_name,industry,key_decision_maker,position,recent_milestone\n"
                "Acme,Technology,Alice,CEO,Launch\n",
                encoding="utf-8",
            )
            targets, _errors = parse_file(path)
            self.assertEqual(len(targets), 1)

    def test_auto_json(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "leads.json"
            path.write_text(json.dumps([{"company_name": "Acme", "industry": "Tech", "key_decision_maker": "Alice", "position": "CEO", "recent_milestone": "Launch"}]), encoding="utf-8")
            targets, _errors = parse_file(path)
            self.assertEqual(len(targets), 1)

    def test_unsupported_extension_raises(self) -> None:
        with self.assertRaises(WorkflowError):
            parse_file("data.txt")
