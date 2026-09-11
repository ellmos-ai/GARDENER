# -*- coding: utf-8 -*-
"""
Metadata and Discoverability Parity Tests for Gardener OS.
Asserts that pyproject.toml, README.md, README_de.md, SECURITY.md, CI workflows, and llms.txt remain in sync.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestMetadataParity(unittest.TestCase):
    def setUp(self):
        self.pyproject_path = ROOT / "pyproject.toml"
        self.readme_en_path = ROOT / "README.md"
        self.readme_de_path = ROOT / "README_de.md"
        self.security_path = ROOT / "SECURITY.md"
        self.ci_workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
        self.llms_txt_path = ROOT / "llms.txt"
        self.changelog_path = ROOT / "CHANGELOG.md"
        self.marketing_log_path = ROOT / "MARKETING-LOG.txt"
        self.gitignore_path = ROOT / ".gitignore"

        self.pyproject = self.pyproject_path.read_text(encoding="utf-8")
        self.readme_en = self.readme_en_path.read_text(encoding="utf-8")
        self.readme_de = self.readme_de_path.read_text(encoding="utf-8")
        self.security = self.security_path.read_text(encoding="utf-8")
        self.ci_workflow = self.ci_workflow_path.read_text(encoding="utf-8")
        self.llms_txt = self.llms_txt_path.read_text(encoding="utf-8")
        self.changelog = self.changelog_path.read_text(encoding="utf-8")
        self.marketing_log = self.marketing_log_path.read_text(encoding="utf-8")
        self.gitignore = self.gitignore_path.read_text(encoding="utf-8")

    def test_pyproject_version_matches(self):
        match = re.search(r'version\s*=\s*"([^"]+)"', self.pyproject)
        self.assertIsNotNone(match, "pyproject.toml missing version")
        version = match.group(1)
        self.assertEqual(version, "0.4.2")

        # Check READMEs reference version
        self.assertIn(f"v{version}", self.readme_en)
        self.assertIn(f"v{version}", self.readme_de)
        self.assertIn(f"[{version}]", self.changelog)

    def test_readme_badges_and_test_count(self):
        # Assert test badges show 163 passed
        self.assertIn("tests-163%20passed-brightgreen.svg", self.readme_en)
        self.assertIn("tests-163%20passed-brightgreen.svg", self.readme_de)

        # Assert code style Ruff
        self.assertIn("code%20style-ruff-000000.svg", self.readme_en)
        self.assertIn("code%20style-ruff-000000.svg", self.readme_de)

        # Assert security badge with SLA
        self.assertIn("security-48h%20SLA-blue.svg", self.readme_en)
        self.assertIn("sicherheit-48h%20SLA-blue.svg", self.readme_de)

        # Assert umbrella and ecosystem badges
        self.assertIn("ecosystem-ellmos--ai-informational.svg", self.readme_en)
        self.assertIn("umbrella-open--bricks-blue.svg", self.readme_en)
        self.assertIn("LLM--Ready-llms.txt-orange.svg", self.readme_en)

        self.assertIn("ecosystem-ellmos--ai-informational.svg", self.readme_de)
        self.assertIn("umbrella-open--bricks-blue.svg", self.readme_de)
        self.assertIn("LLM--Ready-llms.txt-orange.svg", self.readme_de)

        # Assert CI badge
        self.assertIn("actions/workflows/ci.yml/badge.svg", self.readme_en)
        self.assertIn("actions/workflows/ci.yml/badge.svg", self.readme_de)

    def test_llms_txt_consistency(self):
        self.assertIn("Last-checked: 2026-09-11", self.llms_txt)
        self.assertIn("163 passing tests", self.llms_txt)
        self.assertIn("https://github.com/ellmos-ai/gardener", self.llms_txt)
        self.assertIn("ellmos-ai/gardener", self.llms_txt)
        self.assertIn("SECURITY.md", self.llms_txt)

    def test_mermaid_architecture_in_readmes(self):
        self.assertIn("```mermaid", self.readme_en)
        self.assertIn("```mermaid", self.readme_de)
        self.assertIn("everything", self.readme_en)
        self.assertIn("everything", self.readme_de)

    def test_sequence_diagram_in_readmes(self):
        self.assertIn("sequenceDiagram", self.readme_en)
        self.assertIn("sequenceDiagram", self.readme_de)
        self.assertIn("autonumber", self.readme_en)
        self.assertIn("autonumber", self.readme_de)
        self.assertIn("materialize", self.readme_en)
        self.assertIn("materialisieren", self.readme_de)

    def test_quick_navigation_anchors_in_readmes(self):
        en_anchors = [
            "#what-is-gardener",
            "#discovery-context",
            "#architecture",
            "#end-to-end-query--execution-lifecycle",
            "#governance--runtime-invariants",
            "#data-model",
            "#memory-no-separate-memory-system",
            "#tasks-no-separate-system",
            "#three-relationships-with-files",
            "#cross-source-federated-index",
            "#comparison-gardener-vs-rinnsal",
            "#sibling-projects--ecosystem",
            "#security-model-read-this",
            "#haftung--liability",
        ]
        for anchor in en_anchors:
            self.assertIn(f"({anchor})", self.readme_en)

        de_anchors = [
            "#was-ist-gardener",
            "#suchkontext",
            "#architektur",
            "#end-to-end-abfrage---ausführungs-lebenszyklus",
            "#governance--laufzeit-invarianten",
            "#datenmodell",
            "#memory-kein-separates-gedächtnis-system",
            "#tasks-kein-separates-system",
            "#drei-beziehungen-zu-dateien",
            "#quellenübergreifender-föderierter-index",
            "#vergleich-gardener-vs-rinnsal",
            "#geschwisterwerkzeuge--ökosystem",
            "#sicherheitsmodell-bitte-lesen",
            "#haftung--liability",
        ]
        for anchor in de_anchors:
            self.assertIn(f"({anchor})", self.readme_de)

    def test_governance_invariants_table_parity(self):
        invariants = [
            "100% Offline / Zero-Egress",
            "FTS5 BM25",
            "Secret",
            "Cloud",
            "Read-Only",
            "Path Traversal",
            "Ephemeral Workspace",
            "Multi-OS CI",
            "cancel-in-progress",
            "Metadata Parity",
        ]
        for inv in invariants:
            self.assertIn(inv, self.readme_en)

        de_invariants = [
            "100% Offline / Zero-Egress",
            "FTS5 BM25",
            "Secret-Schwärzung",
            "Cloud-Leak",
            "Schreibgeschützte Beobachtung",
            "Schutz vor Pfad-Traversal",
            "Flüchtige Workspaces",
            "Multi-OS CI",
            "cancel-in-progress",
            "Metadaten-Parität",
        ]
        for inv in de_invariants:
            self.assertIn(inv, self.readme_de)

    def test_sibling_tools_matrix(self):
        for doc in (self.readme_en, self.readme_de):
            self.assertIn("ellmos-core", doc)
            self.assertIn("clutch", doc)
            self.assertIn("ellmos-controlcenter-mcp", doc)
            self.assertIn("ellmos-filecommander-mcp", doc)
            self.assertIn("ellmos-codecommander-mcp", doc)
            self.assertIn("ellmos-clatcher-mcp", doc)
            self.assertIn("n8n-manager-mcp", doc)
            self.assertIn("open-bricks", doc)

    def test_ci_workflow_integrity(self):
        self.assertTrue(self.ci_workflow_path.is_file(), ".github/workflows/ci.yml must exist")
        self.assertIn("actions/checkout@v4", self.ci_workflow)
        self.assertIn("actions/setup-python@v5", self.ci_workflow)
        for os_target in ("ubuntu-latest", "windows-latest", "macos-latest"):
            self.assertIn(os_target, self.ci_workflow)
        for py_ver in ("'3.10'", "'3.11'", "'3.12'", "'3.13'"):
            self.assertIn(py_ver, self.ci_workflow)
        self.assertIn("ruff check .", self.ci_workflow)
        self.assertIn("pytest -v", self.ci_workflow)

    def test_ci_concurrency_and_bytecode_gate(self):
        self.assertIn("concurrency:", self.ci_workflow)
        self.assertIn("cancel-in-progress: true", self.ci_workflow)
        self.assertIn("python -m compileall -q .", self.ci_workflow)

    def test_security_policy_exists_and_invariants(self):
        self.assertTrue(self.security_path.is_file(), "SECURITY.md must exist")
        self.assertIn("## English", self.security)
        self.assertIn("## Deutsch", self.security)
        self.assertIn("security@ellmos.ai", self.security)
        self.assertIn("security@open-bricks.org", self.security)
        self.assertIn("support@lukasgeiger.com", self.security)
        self.assertIn("48 hours", self.security)
        self.assertIn("48 Stunden", self.security)
        self.assertIn("5 business days", self.security)
        self.assertIn("5 Werktagen", self.security)
        self.assertIn("Zero-Egress", self.security)
        self.assertIn("Local-First", self.security)
        self.assertIn("Non-Elevation", self.security)
        self.assertIn("https://github.com/ellmos-ai/gardener/security/advisories", self.security)

    def test_pyproject_pep621_classifiers_and_urls(self):
        self.assertIn("classifiers = [", self.pyproject)
        self.assertIn("Development Status :: 4 - Beta", self.pyproject)
        self.assertIn("Operating System :: OS Independent", self.pyproject)
        self.assertIn("Programming Language :: Python :: 3.10", self.pyproject)
        self.assertIn("Programming Language :: Python :: 3.13", self.pyproject)

        for key in ("Homepage", "Documentation", "Repository", "Issues", "Changelog", "Security", "Parent Organization", "Umbrella"):
            self.assertIn(f'"{key}" = ' if " " in key else f"{key} = ", self.pyproject)

    def test_gitignore_hardened_patterns(self):
        self.assertTrue(self.gitignore_path.is_file(), ".gitignore must exist")
        self.assertIn("*.sync-conflict-*", self.gitignore)
        self.assertIn("LOCK.*", self.gitignore)
        self.assertIn("*.lock", self.gitignore)
        self.assertIn(".ruff_cache/", self.gitignore)
        self.assertIn(".pytest_cache/", self.gitignore)

    def test_marketing_log_and_changelog_recency(self):
        self.assertTrue(self.marketing_log_path.is_file(), "MARKETING-LOG.txt must exist")
        self.assertIn("2026-09-08", self.marketing_log)
        self.assertIn("Pfad B", self.marketing_log)
        self.assertIn("ellmos-ai/gardener", self.marketing_log)
        self.assertIn("2026-09-08", self.changelog)
        self.assertIn("Marketing, Discoverability", self.changelog)

    def test_license_and_liability_notice(self):
        license_path = ROOT / "LICENSE"
        self.assertTrue(license_path.is_file(), "LICENSE must exist")
        license_text = license_path.read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Lukas Geiger", license_text)

        # Assert BGB § 521 liability limitation notice in both READMEs
        for doc in (self.readme_en, self.readme_de):
            self.assertIn("521 BGB", doc)
            self.assertIn("Liability", doc)

    def test_offline_zero_egress_contract(self):
        # Assert Invariant #1: Core engine and ingestion modules must never import remote network clients
        for module_name in ("gardener.py", "sources.py"):
            mod_code = (ROOT / module_name).read_text(encoding="utf-8")
            for forbidden in ("urllib.request", "requests", "httpx", "aiohttp"):
                self.assertNotIn(forbidden, mod_code, f"{module_name} must not import {forbidden}")


if __name__ == "__main__":
    unittest.main()
