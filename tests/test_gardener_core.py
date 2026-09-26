import contextlib
import gc
import importlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class GardenerTempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        os.environ["GARDENER_DATA"] = str(base / "data")
        os.environ["GARDENER_HOME"] = str(base / "home")

        import gardener

        self.gardener = importlib.reload(gardener)
        self.af = self.gardener.Gardener()

    def tearDown(self):
        gc.collect()
        for attempt in range(3):
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.1)


class TestGardenerCore(GardenerTempCase):
    def test_put_get_and_find_round_trip(self):
        self.af.put(
            "beleg-scanner",
            content="Scannt Belege und Rechnungen.",
            type="knowledge",
            tags="steuer,belege",
        )

        entry = self.af.get("beleg-scanner")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["type"], "knowledge")

        results = self.af.find("Rechnungen")
        self.assertEqual(results[0]["name"], "beleg-scanner")

    def test_task_lifecycle_uses_everything_table(self):
        self.af.task("steuer-2026", "Unterlagen prüfen", priority="high")
        open_tasks = self.af.tasks(status="open")
        self.assertEqual([task["name"] for task in open_tasks], ["steuer-2026"])

        done = self.af.task_done("steuer-2026")
        self.assertIsNotNone(done)
        self.assertEqual(done["meta"]["status"], "done")

    def test_absorb_sets_original_name_and_materialize_uses_it(self):
        base = Path(self.temp.name)
        source = base / "bericht.bin"
        source.write_bytes(b"\x00\x01\x02gardener")

        entry = self.af.absorb(source)
        self.assertEqual(entry["meta"]["original_name"], "bericht.bin")
        self.assertEqual(entry["meta"]["storage"], "inline")
        self.assertIn("blob_path", entry["meta"])

        out_dir = base / "out"
        out_path = self.af.materialize("bericht.bin", dest=out_dir)
        self.assertIsNotNone(out_path)
        self.assertEqual(out_path.name, "bericht.bin")
        self.assertEqual(out_path.read_bytes(), b"\x00\x01\x02gardener")

    def test_consolidate_never_touches_pinned_entries(self):
        self.af.put(
            "pinned-memo",
            content="bleibt",
            type="memory",
            meta={"weight": 0.06, "decay_rate": 0.5},
            pinned=True,
        )
        self.af.put(
            "volatile-memo",
            content="verblasst",
            type="memory",
            meta={"weight": 0.06, "decay_rate": 0.5},
        )

        # Several cycles: volatile entry drops below the forget threshold
        for _ in range(3):
            self.af.consolidate()

        self.assertIsNone(self.af.get("volatile-memo"))
        pinned = self.af.get("pinned-memo")
        self.assertIsNotNone(pinned)
        # Weight of pinned entries must remain untouched (no decay)
        self.assertEqual(pinned["meta"]["weight"], 0.06)

    def test_find_orders_fts_hits_by_relevance(self):
        # Older but weaker match (single occurrence, long document)
        self.af.put(
            "zebra-weak",
            content="zebra " + " ".join(f"wort{i}" for i in range(60)),
            type="memory",
        )
        time.sleep(1.1)  # put() timestamps have second precision
        # Newer and stronger match (high term frequency, short document)
        self.af.put("zebra-strong", content="zebra zebra zebra", type="memory")

        results = self.af.find("zebra")
        names = [r["name"] for r in results]
        self.assertEqual(names[0], "zebra-strong")
        # Internal rank must not leak into the API result
        self.assertNotIn("rank", results[0])

        # Pinned entries still come first regardless of relevance
        self.af.put(
            "zebra-weak",
            content="zebra " + " ".join(f"wort{i}" for i in range(60)),
            type="memory",
            pinned=True,
        )
        names = [r["name"] for r in self.af.find("zebra")]
        self.assertEqual(names[0], "zebra-weak")

    def test_multi_word_query_ux_or_fallback_and_ranking(self):
        # Entry A contains only "Registry"
        self.af.put(
            "doc-registry",
            content="Dokumentation über System-Registry Einstellungen.",
            type="knowledge",
        )
        # Entry B contains only "Mitgliedschaft"
        self.af.put(
            "doc-mitgliedschaft",
            content="Bescheinigung über die Mitgliedschaft im Verein.",
            type="knowledge",
        )

        # Multi-word search when no document has both terms must still find both
        results = self.af.find("Registry Mitgliedschaft")
        names = [r["name"] for r in results]
        self.assertIn("doc-registry", names)
        self.assertIn("doc-mitgliedschaft", names)

        # Entry C contains BOTH terms
        self.af.put(
            "doc-both",
            content="Details zur Registry Mitgliedschaft und Benutzerrechten.",
            type="knowledge",
        )

        # Entry C (matching both terms) must rank higher than single-term matches
        results_with_both = self.af.find("Registry Mitgliedschaft")
        self.assertEqual(results_with_both[0]["name"], "doc-both")

    def test_build_fts_or_query_helper(self):
        build_or = self.gardener.Gardener._build_fts_or_query
        # Multi-word plain query -> OR query with quotes
        self.assertEqual(
            build_or("Registry Mitgliedschaft"), '"Registry" OR "Mitgliedschaft"'
        )
        # Single word -> None
        self.assertIsNone(build_or("Registry"))
        # Single quoted phrase -> None (preserved as exact phrase, not split)
        self.assertIsNone(build_or('"Registry Mitgliedschaft"'))
        # Mixed phrase and additional term -> OR query keeping the phrase intact
        self.assertEqual(
            build_or('"Registry Mitgliedschaft" Benutzer'),
            '"Registry Mitgliedschaft" OR "Benutzer"',
        )
        # Hyphenated word and bare word
        self.assertEqual(
            build_or("beleg-scanner rechnung"),
            '"beleg-scanner" OR "rechnung"',
        )
        # Prefix tokens
        self.assertEqual(
            build_or("beleg-scan* rechn*"),
            '"beleg-scan"* OR "rechn"*',
        )
        # Unclosed quote recovery
        self.assertEqual(
            build_or('"offenes zitat" rechnung'),
            '"offenes zitat" OR "rechnung"',
        )
        # Explicit operators -> None (preserved user boolean query)
        self.assertIsNone(build_or("Registry AND Mitgliedschaft"))
        self.assertIsNone(build_or("Registry OR Mitgliedschaft"))
        self.assertIsNone(build_or("Registry NOT Mitgliedschaft"))
        self.assertIsNone(build_or("NEAR(Registry, Mitgliedschaft)"))

    def test_multiword_phrase_or_fallback_and_like_clean_tokens(self):
        self.af.put(
            "doc-phrase-only",
            content="Der beleg-scanner verarbeitet Dokumente schnell.",
            type="tool",
        )
        self.af.put(
            "doc-term-only",
            content="Jede Eingangsrechnung erfordert eine Buchung.",
            type="knowledge",
        )

        # Query has a phrase and another term that never co-occur in one document
        # Exact AND search yields 0 hits; fallback to OR finds both documents
        results = self.af.find('"beleg-scanner" Eingangsrechnung', with_snippets=True)
        self.assertEqual(len(results), 2)
        names = {r["name"] for r in results}
        self.assertEqual(names, {"doc-phrase-only", "doc-term-only"})
        # Verify snippet generation on OR matches
        for r in results:
            self.assertIn("snippet", r)

        # Verify LIKE fallback token hygiene: _like_query extracts clean unquoted tokens
        tokens = [text for text, _, _ in self.gardener.Gardener._tokenize_query('"beleg-scanner" "rechnung"') if text]
        self.assertEqual(tokens, ["beleg-scanner", "rechnung"])

    def test_tokenize_query_and_build_fts_and_query_helpers(self):
        tokenize = self.gardener.Gardener._tokenize_query
        build_and = self.gardener.Gardener._build_fts_and_query

        # Tokenization of plain words and hyphens
        tokens = tokenize("beleg-scanner rechnung")
        self.assertEqual(tokens, [("beleg-scanner", False, False), ("rechnung", False, False)])

        # Quoted phrase and prefix
        tokens = tokenize('"beleg scanner" scan*')
        self.assertEqual(tokens, [("beleg scanner", True, False), ("scan", False, True)])

        # Unclosed quote recovery
        tokens = tokenize('"offenes zitat')
        self.assertEqual(tokens, [("offenes zitat", True, False)])

        # Asterisk-only tokens are ignored to prevent FTS5 special query crashes
        self.assertEqual(tokenize("***"), [])
        self.assertEqual(tokenize("scan* *** doc"), [("scan", False, True), ("doc", False, False)])

        # AND query building with token quoting for FTS5 safety
        self.assertEqual(build_and("beleg-scanner"), '"beleg-scanner"')
        self.assertEqual(build_and("beleg-scanner rechnung"), '"beleg-scanner" "rechnung"')
        self.assertEqual(build_and("beleg-scan*"), '"beleg-scan"*')
        self.assertEqual(build_and('C:\\Users\\lukas\\file.txt'), '"C:\\Users\\lukas\\file.txt"')

        # Preserves boolean operators by returning None (allowing native FTS evaluation)
        self.assertIsNone(build_and("beleg AND rechnung"))
        self.assertIsNone(build_and("beleg OR rechnung"))
        self.assertIsNone(build_and("beleg NOT archiv"))
        self.assertIsNone(build_and("NEAR(beleg, rechnung)"))
        self.assertIsNone(build_and(""))
        self.assertIsNone(build_and("   "))

        # Safe operator query building preserving AND / OR / NOT while quoting operands
        build_safe_op = self.gardener.Gardener._build_fts_safe_operator_query
        self.assertEqual(build_safe_op("beleg-scanner AND rechnung"), '"beleg-scanner" AND "rechnung"')
        self.assertEqual(build_safe_op("beleg-scanner OR rechnung"), '"beleg-scanner" OR "rechnung"')
        self.assertEqual(build_safe_op("rechnung NOT beleg-scanner"), '"rechnung" NOT "beleg-scanner"')
        self.assertEqual(build_safe_op("apple AND NOT banana"), '"apple" NOT "banana"')
        self.assertEqual(build_safe_op("apple OR NOT banana"), '"apple" NOT "banana"')
        self.assertEqual(build_safe_op("apple AND AND banana"), '"apple" AND "banana"')
        self.assertEqual(build_safe_op("apple OR OR banana"), '"apple" OR "banana"')
        self.assertEqual(build_safe_op("apple AND OR banana"), '"apple" OR "banana"')
        self.assertEqual(build_safe_op("c++ AND linux"), '"c++" AND "linux"')
        self.assertEqual(build_safe_op("c++ OR c#"), '"c++" OR "c#"')
        self.assertEqual(build_safe_op("c++ developer AND linux"), '"c++" AND "developer" AND "linux"')
        self.assertEqual(build_safe_op("beleg-scan* AND rechnung"), '"beleg-scan"* AND "rechnung"')
        self.assertEqual(build_safe_op("AND rechnung AND"), '"rechnung"')
        self.assertEqual(build_safe_op("NOT banana"), '"banana"')
        self.assertEqual(build_safe_op("banana NOT"), '"banana"')
        self.assertIsNone(build_safe_op("NOT"))
        self.assertIsNone(build_safe_op("AND OR NOT"))
        self.assertIsNone(build_safe_op("beleg-scanner rechnung"))
        self.assertIsNone(build_safe_op("NEAR(beleg, rechnung)"))
        self.assertIsNone(build_safe_op(""))

        # Column prefix tokenization & query building (name, content, tags)
        self.assertEqual(tokenize("tags:python-script"), [("tags:python-script", False, False)])
        self.assertEqual(tokenize('tags:"machine learning"'), [("tags:machine learning", True, False)])
        self.assertEqual(tokenize('tags: "machine learning"'), [("tags:machine learning", True, False)])
        self.assertEqual(tokenize("tags:scan*"), [("tags:scan", False, True)])
        self.assertEqual(tokenize("name:beleg-rechnung-1"), [("name:beleg-rechnung-1", False, False)])
        self.assertEqual(tokenize("content:error-404"), [("content:error-404", False, False)])

        self.assertEqual(build_and("tags:python-script"), 'tags:"python-script"')
        self.assertEqual(build_and("name:beleg-rechnung-1"), 'name:"beleg-rechnung-1"')
        self.assertEqual(build_and('tags:"machine learning"'), 'tags:"machine learning"')
        self.assertEqual(build_and("tags:scan*"), 'tags:"scan"*')

        self.assertEqual(
            build_safe_op("tags:python-script AND name:beleg-1"),
            'tags:"python-script" AND name:"beleg-1"'
        )
        self.assertEqual(
            build_safe_op("tags:python OR tags:javascript"),
            'tags:"python" OR tags:"javascript"'
        )
        self.assertEqual(
            build_safe_op("tags:python NOT tags:legacy"),
            'tags:"python" NOT tags:"legacy"'
        )
        self.assertEqual(
            build_safe_op("tags:python AND NOT tags:legacy"),
            'tags:"python" NOT tags:"legacy"'
        )
        self.assertEqual(
            build_safe_op("name:beleg* OR tags:rechnung*"),
            'name:"beleg"* OR tags:"rechnung"*'
        )

        # Parentheses grouping & operator normalization (lowercase and German synonyms)
        self.assertEqual(
            tokenize("(python OR rust) AND fast"),
            [("(", False, False), ("python", False, False), ("OR", False, False),
             ("rust", False, False), (")", False, False), ("AND", False, False),
             ("fast", False, False)]
        )
        self.assertEqual(
            build_safe_op("(python OR rust) AND fast"),
            '("python" OR "rust") AND "fast"'
        )
        self.assertEqual(
            build_safe_op("(beleg-scanner OR quittung) AND 2026"),
            '("beleg-scanner" OR "quittung") AND "2026"'
        )
        self.assertEqual(
            build_safe_op("backend AND (tags:python-script OR tags:rust-crate)"),
            '"backend" AND (tags:"python-script" OR tags:"rust-crate")'
        )
        self.assertEqual(
            build_safe_op('tags:python AND (fastapi OR "machine learning")'),
            'tags:"python" AND ("fastapi" OR "machine learning")'
        )
        self.assertEqual(
            build_safe_op("tags:python und (fastapi oder django)"),
            'tags:"python" AND ("fastapi" OR "django")'
        )
        self.assertEqual(
            build_safe_op("beleg und rechnung"),
            '"beleg" AND "rechnung"'
        )
        self.assertEqual(
            build_safe_op("beleg oder quittung"),
            '"beleg" OR "quittung"'
        )
        self.assertEqual(
            build_safe_op("rechnung nicht archiv"),
            '"rechnung" NOT "archiv"'
        )
        self.assertEqual(
            build_safe_op("(apple OR banana) NOT cherry"),
            '("apple" OR "banana") NOT "cherry"'
        )
        self.assertEqual(
            build_safe_op("((a OR b) AND (c OR d))"),
            '(("a" OR "b") AND ("c" OR "d"))'
        )
        self.assertEqual(
            build_safe_op("(python OR rust"),
            '("python" OR "rust")'
        )
        self.assertEqual(
            build_safe_op("python OR rust)"),
            '"python" OR "rust"'
        )
        self.assertEqual(
            build_safe_op("(OR python)"),
            '("python")'
        )
        self.assertEqual(
            build_safe_op("(python OR)"),
            '("python")'
        )
        self.assertIsNone(build_safe_op("()"))

    def test_find_with_boolean_operators_and_special_chars(self):
        self.af.put(
            "doc-scanner-rechnung",
            content="Der beleg-scanner verarbeitet jede Rechnung präzise.",
            type="knowledge",
        )
        self.af.put(
            "doc-rechnung-only",
            content="Nur eine Rechnung ohne jeglichen Scanner.",
            type="knowledge",
        )
        self.af.put(
            "doc-scanner-only",
            content="Der beleg-scanner archiviert Quittungen.",
            type="knowledge",
        )
        self.af.put(
            "doc-cpp-linux",
            content="Softwareentwicklung mit c++ unter linux.",
            type="tool",
        )

        # 1. Unquoted hyphenated term with explicit AND
        hits_and = self.af.find("beleg-scanner AND rechnung", with_snippets=True)
        self.assertEqual(len(hits_and), 1)
        self.assertEqual(hits_and[0]["name"], "doc-scanner-rechnung")
        self.assertIn("snippet", hits_and[0])
        self.assertIn(">>>beleg-scanner<<<", hits_and[0]["snippet"])

        # 2. Unquoted hyphenated term with NOT
        hits_not1 = self.af.find("rechnung NOT beleg-scanner")
        self.assertEqual(len(hits_not1), 1)
        self.assertEqual(hits_not1[0]["name"], "doc-rechnung-only")

        hits_not2 = self.af.find("beleg-scanner NOT rechnung")
        self.assertEqual(len(hits_not2), 1)
        self.assertEqual(hits_not2[0]["name"], "doc-scanner-only")

        # 3. Special symbol c++ with AND
        hits_cpp = self.af.find("c++ AND linux")
        self.assertEqual(len(hits_cpp), 1)
        self.assertEqual(hits_cpp[0]["name"], "doc-cpp-linux")

        # 4. Asterisk-only query does not crash FTS5
        hits_stars = self.af.find("***")
        self.assertEqual(hits_stars, [])

    def test_find_with_compound_boolean_operators_and_negation(self):
        """Testet erweiterte Operator-UX: 'AND NOT', 'OR NOT', wiederholte Operatoren und führendes NOT."""
        self.af.put(
            "doc-apple-fruit",
            content="Frischer roter Apfel direkt vom Obstbaum.",
            type="knowledge",
        )
        self.af.put(
            "doc-banana-fruit",
            content="Reife gelbe Banane reich an Kalium.",
            type="knowledge",
        )
        self.af.put(
            "doc-mixed-fruit",
            content="Fruchtsalat mit Apfel und Banane zusammen.",
            type="knowledge",
        )

        # 1. 'AND NOT' normalisiert auf 'NOT' im FTS5
        hits_and_not = self.af.find("Apfel AND NOT Banane", with_snippets=True)
        self.assertEqual(len(hits_and_not), 1)
        self.assertEqual(hits_and_not[0]["name"], "doc-apple-fruit")
        self.assertIn("snippet", hits_and_not[0])
        self.assertIn(">>>Apfel<<<", hits_and_not[0]["snippet"])

        # 2. 'OR NOT' normalisiert auf 'NOT' im FTS5
        hits_or_not = self.af.find("Banane OR NOT Apfel")
        self.assertEqual(len(hits_or_not), 1)
        self.assertEqual(hits_or_not[0]["name"], "doc-banana-fruit")

        # 3. Wiederholte Operatoren ('AND AND') werden dedupliziert
        hits_and_and = self.af.find("Apfel AND AND Banane")
        self.assertEqual(len(hits_and_and), 1)
        self.assertEqual(hits_and_and[0]["name"], "doc-mixed-fruit")

        # 4. Führendes NOT wirft keinen FTS5-Syntaxfehler, sondern sucht den Term
        hits_lead_not = self.af.find("NOT Banane")
        self.assertTrue(len(hits_lead_not) >= 2)
        hit_names = [h["name"] for h in hits_lead_not]
        self.assertIn("doc-banana-fruit", hit_names)
        self.assertIn("doc-mixed-fruit", hit_names)

    def test_find_with_column_filters_and_hyphenated_values(self):
        """Testet FTS5-Spaltenfilter (tags:, name:, content:) mit Bindestrichen, Phrasen und Operatoren."""
        self.af.put(
            "beleg-rechnung-42",
            content="Rechnung für Büromaterial und Schreibwaren.",
            tags="finanzen,beleg-scanner",
            type="knowledge",
        )
        self.af.put(
            "script-python-fastapi",
            content="Backend API Server mit FastAPI Framework für Microservices.",
            tags="python-script,backend",
            type="tool",
        )
        self.af.put(
            "script-python-legacy",
            content="Altes Python Wartungsskript ohne Framework.",
            tags="python-script,legacy",
            type="tool",
        )
        self.af.put(
            "ml-study-note",
            content="Notizen zu Machine Learning und Deep Learning Architekturen.",
            tags="ai,machine learning",
            type="memory",
        )

        # 1. Spaltenfilter mit Bindestrich im Wert: tags:python-script
        hits_tag = self.af.find("tags:python-script", with_snippets=True)
        self.assertEqual(len(hits_tag), 2)
        tag_names = [h["name"] for h in hits_tag]
        self.assertIn("script-python-fastapi", tag_names)
        self.assertIn("script-python-legacy", tag_names)

        # 2. Spaltenfilter mit Bindestrichen im Namen: name:beleg-rechnung-42
        hits_name = self.af.find("name:beleg-rechnung-42")
        self.assertEqual(len(hits_name), 1)
        self.assertEqual(hits_name[0]["name"], "beleg-rechnung-42")

        # 3. Spaltenfilter mit quotierter Phrase: tags:"machine learning"
        hits_phrase = self.af.find('tags:"machine learning"')
        self.assertEqual(len(hits_phrase), 1)
        self.assertEqual(hits_phrase[0]["name"], "ml-study-note")

        # 4. Spaltenfilter mit Leerzeichen nach Doppelpunkt: tags: "machine learning"
        hits_space = self.af.find('tags: "machine learning"')
        self.assertEqual(len(hits_space), 1)
        self.assertEqual(hits_space[0]["name"], "ml-study-note")

        # 5. Verknüpfung zweier Spaltenfilter mit AND
        hits_and = self.af.find("tags:python-script AND name:script-python-fastapi")
        self.assertEqual(len(hits_and), 1)
        self.assertEqual(hits_and[0]["name"], "script-python-fastapi")

        # 6. Spaltenfilter mit NOT-Ausschluss
        hits_not = self.af.find("tags:python-script NOT tags:legacy")
        self.assertEqual(len(hits_not), 1)
        self.assertEqual(hits_not[0]["name"], "script-python-fastapi")

        # 7. Präfix-Spaltenfilter mit Wildcard und OR
        hits_or = self.af.find("name:beleg* OR tags:ai")
        self.assertEqual(len(hits_or), 2)
        or_names = [h["name"] for h in hits_or]
        self.assertIn("beleg-rechnung-42", or_names)
        self.assertIn("ml-study-note", or_names)

        # 8. Präfix-Wildcard am Spaltenwert
        hits_wild = self.af.find("tags:python-script*")
        self.assertEqual(len(hits_wild), 2)

    def test_find_with_grouping_parentheses_and_normalized_operators(self):
        """Testet FTS5-Gruppierungsklammern und normalisierte Operatoren (Klein-/deutsche Schreibung)."""
        self.af.put(
            "doc-scanner-2026",
            content="Der beleg-scanner verarbeitet Rechnungen für das Jahr 2026.",
            tags="finanzen,beleg-scanner",
            type="knowledge",
        )
        self.af.put(
            "doc-quittung-2026",
            content="Eine wichtige quittung ausgestellt im Jahr 2026.",
            tags="finanzen,quittung",
            type="knowledge",
        )
        self.af.put(
            "doc-scanner-2024",
            content="Alter beleg-scanner Archivbericht aus dem Jahr 2024.",
            tags="legacy,beleg-scanner",
            type="knowledge",
        )
        self.af.put(
            "doc-quittung-2024",
            content="Alte quittung aus dem Jahr 2024.",
            tags="legacy,quittung",
            type="knowledge",
        )
        self.af.put(
            "service-fastapi-backend",
            content="Microservice Backend basierend auf FastAPI.",
            tags="python-script,backend",
            type="tool",
        )
        self.af.put(
            "service-rust-backend",
            content="Hochperformanter Rust Microservice Backend.",
            tags="rust-crate,backend",
            type="tool",
        )
        self.af.put(
            "service-python-gui",
            content="Grafische Benutzeroberfläche für Desktop-Clients.",
            tags="python-script,frontend",
            type="tool",
        )

        # 1. Gruppierung mit Bindestrich-Termen und OR: (beleg-scanner OR quittung) AND 2026
        hits_grouped1 = self.af.find("(beleg-scanner OR quittung) AND 2026", with_snippets=True)
        self.assertEqual(len(hits_grouped1), 2)
        names1 = {h["name"] for h in hits_grouped1}
        self.assertEqual(names1, {"doc-scanner-2026", "doc-quittung-2026"})
        for h in hits_grouped1:
            self.assertIn("snippet", h)
            self.assertIn(">>>2026<<<", h["snippet"])

        # 2. Umgekehrte Reihenfolge: 2026 AND (beleg-scanner OR quittung)
        hits_grouped2 = self.af.find("2026 AND (beleg-scanner OR quittung)")
        self.assertEqual(len(hits_grouped2), 2)
        names2 = {h["name"] for h in hits_grouped2}
        self.assertEqual(names2, {"doc-scanner-2026", "doc-quittung-2026"})

        # 3. Gruppierung mit Spaltenfiltern: backend AND (tags:python-script OR tags:rust-crate)
        hits_col_group = self.af.find("backend AND (tags:python-script OR tags:rust-crate)")
        self.assertEqual(len(hits_col_group), 2)
        names_col = {h["name"] for h in hits_col_group}
        self.assertEqual(names_col, {"service-fastapi-backend", "service-rust-backend"})

        # 4. Normalisierte Kleinschreibung: (beleg-scanner or quittung) and 2026
        hits_lower = self.af.find("(beleg-scanner or quittung) and 2026")
        self.assertEqual(len(hits_lower), 2)
        names_lower = {h["name"] for h in hits_lower}
        self.assertEqual(names_lower, {"doc-scanner-2026", "doc-quittung-2026"})

        # 5. Deutsche Operatoren: beleg-scanner UND 2026
        hits_de_and = self.af.find("beleg-scanner UND 2026")
        self.assertEqual(len(hits_de_and), 1)
        self.assertEqual(hits_de_and[0]["name"], "doc-scanner-2026")

        # 6. Deutsche Operatoren mit Klammern: (beleg-scanner ODER quittung) UND 2026
        hits_de_group = self.af.find("(beleg-scanner ODER quittung) UND 2026")
        self.assertEqual(len(hits_de_group), 2)
        names_de = {h["name"] for h in hits_de_group}
        self.assertEqual(names_de, {"doc-scanner-2026", "doc-quittung-2026"})

        # 7. Deutscher Ausschluss-Operator: beleg-scanner NICHT 2024
        hits_de_not = self.af.find("beleg-scanner NICHT 2024")
        self.assertEqual(len(hits_de_not), 1)
        self.assertEqual(hits_de_not[0]["name"], "doc-scanner-2026")

        # 8. Unbalancierte und verwaiste Klammern werfen keinen Fehler, sondern balancieren sicher
        hits_unbalanced = self.af.find("((beleg-scanner OR quittung) AND 2026")
        self.assertEqual(len(hits_unbalanced), 2)
        names_unbal = {h["name"] for h in hits_unbalanced}
        self.assertEqual(names_unbal, {"doc-scanner-2026", "doc-quittung-2026"})

        hits_orphan = self.af.find("(beleg-scanner OR quittung) AND 2026)")
        self.assertEqual(len(hits_orphan), 2)
        names_orphan = {h["name"] for h in hits_orphan}
        self.assertEqual(names_orphan, {"doc-scanner-2026", "doc-quittung-2026"})

    def test_like_query_with_column_filters(self):
        """Testet den gezielten Spaltenabgleich des LIKE-Fallbacks bei Vorliegen von Spaltenfiltern."""
        self.af.put(
            "doc-like-col",
            content="Normaler Inhalt ohne Stichwort im Text.",
            tags="custom-target-tag",
            type="knowledge",
        )
        with self.af.connection("user") as conn:
            # Gezielte Suche im tags-Feld über LIKE
            hits = self.af._like_query(conn, "tags:custom-target-tag")
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["name"], "doc-like-col")

            # Suche im name-Feld
            hits_name = self.af._like_query(conn, "name:doc-like-col")
            self.assertEqual(len(hits_name), 1)
            self.assertEqual(hits_name[0]["name"], "doc-like-col")

            # Falsche Spalte liefert 0 Treffer
            hits_none = self.af._like_query(conn, "content:custom-target-tag")
            self.assertEqual(len(hits_none), 0)

    def test_find_with_hyphens_special_chars_and_snippets(self):
        self.af.put(
            "tool-beleg-scanner",
            content="Der beleg-scanner verarbeitet Rechnungen und Quittungen zuverlässig.",
            type="tool",
        )
        self.af.put(
            "config-path",
            content="Die Konfiguration liegt unter C:\\Users\\lukas\\config.json für das Backup.",
            type="config",
        )
        self.af.put(
            "meeting-parens",
            content="Notiz zum Projektabschluss (2026) mit dem Team.",
            type="memory",
        )

        # 1. Hyphenated term produces highlighted snippets (previously crashed FTS5 to LIKE without snippets)
        hits = self.af.find("beleg-scanner", with_snippets=True)
        self.assertTrue(len(hits) >= 1)
        self.assertEqual(hits[0]["name"], "tool-beleg-scanner")
        self.assertIn("snippet", hits[0])
        self.assertIn(">>>beleg-scanner<<<", hits[0]["snippet"])

        # 2. Prefix query with hyphen
        hits = self.af.find("beleg-scan*", with_snippets=True)
        self.assertTrue(len(hits) >= 1)
        self.assertEqual(hits[0]["name"], "tool-beleg-scanner")
        self.assertIn(">>>beleg-scanner<<<", hits[0]["snippet"])

        # 3. Windows path with backslashes
        hits = self.af.find("C:\\Users\\lukas", with_snippets=True)
        self.assertTrue(len(hits) >= 1)
        self.assertEqual(hits[0]["name"], "config-path")
        self.assertIn("snippet", hits[0])
        self.assertIn(">>>C:\\Users\\lukas<<<", hits[0]["snippet"])

        # 4. Parentheses
        hits = self.af.find("(2026)", with_snippets=True)
        self.assertTrue(len(hits) >= 1)
        self.assertEqual(hits[0]["name"], "meeting-parens")
        self.assertIn("snippet", hits[0])
        self.assertIn(">>>2026<<<", hits[0]["snippet"])

    def test_multi_word_and_priority_with_hyphenated_terms(self):
        # Entry 1 matches both terms
        self.af.put(
            "doc-both-hyphen",
            content="Spezifikation für den beleg-scanner im Bereich Steuern und Finanzen.",
            type="knowledge",
        )
        # Entry 2 matches only "Steuern"
        self.af.put(
            "doc-steuern-only",
            content="Allgemeines Dokument über Steuern und Abgaben.",
            type="knowledge",
        )
        # Entry 3 matches only "beleg-scanner"
        self.af.put(
            "doc-scanner-only",
            content="Technisches Handbuch zum beleg-scanner Gerät.",
            type="knowledge",
        )

        # Multi-word AND search must return ONLY the document matching both terms first
        hits = self.af.find("beleg-scanner Steuern")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["name"], "doc-both-hyphen")

    def test_find_unclosed_quote_tolerance(self):
        self.af.put(
            "quote-doc",
            content="Wichtige Phrase fuer den Projektabschluss 2026 im Team.",
            type="memory",
        )
        # Unclosed quote must not raise FTS5 syntax error and should match the phrase
        hits = self.af.find('"Projektabschluss 2026', with_snippets=True)
        self.assertTrue(len(hits) >= 1)
        self.assertEqual(hits[0]["name"], "quote-doc")
        self.assertIn("snippet", hits[0])
        self.assertIn("Projektabschluss 2026", hits[0]["snippet"])

    def test_recall_tolerates_invalid_meta_json(self):
        conn = sqlite3.connect(Path(os.environ["GARDENER_DATA"]) / "user.db")
        try:
            conn.execute(
                """
                INSERT INTO everything
                    (name, content, type, tags, meta, pinned, created, updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "broken-meta-memory",
                    "needle memory content",
                    "memory",
                    "",
                    "{broken",
                    0,
                    "2026-06-22T00:00:00",
                    "2026-06-22T00:00:00",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        results = self.af.recall("needle")

        self.assertEqual(results[0]["name"], "broken-meta-memory")
        self.assertEqual(results[0]["meta"], {})

    def test_tasks_sorted_by_semantic_priority(self):
        self.af.task("t-low", "x", priority="low")
        self.af.task("t-critical", "x", priority="critical")
        self.af.task("t-normal", "x", priority="normal")
        self.af.task("t-high", "x", priority="high")

        names = [task["name"] for task in self.af.tasks()]
        self.assertEqual(names, ["t-critical", "t-high", "t-normal", "t-low"])

    def test_observe_skips_internal_runtime_dirs(self):
        home = Path(os.environ["GARDENER_HOME"])
        (home / "notes.md").write_text("sichtbar", encoding="utf-8")
        (home / ".absorber" / "incoming.txt").write_text("intern", encoding="utf-8")
        (home / ".output" / "exported.md").write_text("intern", encoding="utf-8")
        (home / ".gardener").mkdir(exist_ok=True)
        (home / ".gardener" / "state.txt").write_text("intern", encoding="utf-8")

        observed = self.af.observe()
        names = [entry["name"] for entry in observed]

        self.assertIn("observed/notes.md", names)
        for name in names:
            self.assertFalse(
                name.startswith(("observed/.absorber", "observed/.output",
                                 "observed/.gardener", "observed/__pycache__")),
                f"internal runtime file observed: {name}",
            )

        # observe() and sync() must apply the same skip logic
        self.af.sync()
        entries = self.af.list(type="observed", limit=100)
        self.assertEqual(
            sorted(entry["name"] for entry in entries), sorted(names)
        )

    def test_run_tool_success_and_payload_execution(self):
        self.af.put(
            "calc-add",
            type="tool",
            target="system",
            content="""# Calculator
```python
def execute(payload):
    a = payload.get("a", 0)
    b = payload.get("b", 0)
    return {"sum": a + b}
```
""",
        )
        ok, output = self.af.run("calc-add", input_data={"a": 17, "b": 25})
        self.assertTrue(ok)
        data = json.loads(output)
        self.assertEqual(data["sum"], 42)

        # Backwards compatibility with input= keyword argument
        ok_kw, output_kw = self.af.run("calc-add", input={"a": 3, "b": 4})
        self.assertTrue(ok_kw)
        self.assertEqual(json.loads(output_kw)["sum"], 7)

    def test_run_tool_configurable_timeout_from_param_and_config(self):
        self.af.put(
            "sleeper-tool",
            type="tool",
            target="system",
            content="""# Sleeper
```python
import time
def execute(payload):
    time.sleep(2.0)
    return {"status": "done"}
```
""",
        )
        # Timeout via parameter (1 second)
        ok, output = self.af.run("sleeper-tool", timeout=1)
        self.assertFalse(ok)
        self.assertIn("Timeout: 'sleeper-tool' hat länger als 1s gedauert.", output)

        # Timeout via config
        self.af.config["run_timeout"] = 1
        ok_cfg, output_cfg = self.af.run("sleeper-tool")
        self.assertFalse(ok_cfg)
        self.assertIn("Timeout: 'sleeper-tool' hat länger als 1s gedauert.", output_cfg)

    def test_run_tool_error_handling_missing_and_invalid_code(self):
        ok, output = self.af.run("nonexistent-tool")
        self.assertFalse(ok)
        self.assertIn("nicht gefunden", output)

        self.af.put("no-code-tool", content="Nur Markdown ohne Python-Block", type="tool")
        ok2, output2 = self.af.run("no-code-tool")
        self.assertFalse(ok2)
        self.assertIn("Kein ausführbarer Code-Block", output2)

    def test_observe_and_sync_custom_exclude_patterns(self):
        home = Path(os.environ["GARDENER_HOME"])
        (home / "valid_doc.md").write_text("wichtiger Inhalt", encoding="utf-8")
        (home / "cache.bak").write_text("altes backup", encoding="utf-8")
        (home / "temp_scratch.txt").write_text("scratch", encoding="utf-8")
        build_dir = home / "build"
        build_dir.mkdir(exist_ok=True)
        (build_dir / "target.log").write_text("build log", encoding="utf-8")

        self.af.config["exclude_patterns"] = ["*.bak", "temp_*", "build/*"]

        observed = self.af.observe()
        names = [entry["name"] for entry in observed]

        self.assertIn("observed/valid_doc.md", names)
        self.assertNotIn("observed/cache.bak", names)
        self.assertNotIn("observed/temp_scratch.txt", names)
        self.assertNotIn("observed/build/target.log", names)

        # Sync should also respect configured excludes
        sync_res = self.af.sync()
        self.assertEqual(sync_res["observed"], 1)
        db_entries = self.af.list(type="observed")
        db_names = [e["name"] for e in db_entries]
        self.assertEqual(db_names, ["observed/valid_doc.md"])

    def test_is_internal_custom_patterns_and_static_call_compatibility(self):
        # Static invocation compatibility
        self.assertTrue(self.gardener.Gardener._is_internal(".absorber/file.txt"))
        self.assertTrue(self.gardener.Gardener._is_internal("config.json"))
        self.assertFalse(self.gardener.Gardener._is_internal("normal.md"))

        # Extra excludes parameter
        self.assertTrue(self.af._is_internal("foo.tmp", extra_excludes=["*.tmp"]))
        self.assertFalse(self.af._is_internal("foo.md", extra_excludes=["*.tmp"]))

    def test_seeded_german_user_texts_use_real_umlauts(self):
        import seed

        seed = importlib.reload(seed)
        with contextlib.redirect_stdout(io.StringIO()):
            seed.seed()

        combined = []
        for db_name in ("gardener.db", "user.db"):
            db_path = Path(os.environ["GARDENER_DATA"]) / db_name
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT content FROM everything").fetchall()
            combined.extend(row[0] for row in rows)

        text = re.sub(r"```.*?```", "", "\n".join(combined), flags=re.DOTALL)
        legacy_spellings = [
            "fuer",
            "Fuer",
            "Fuehrt",
            "zurueck",
            "Buecher",
            "primaere",
            "Grosse",
            "ueber",
            "nuetzlich",
            "Uebersicht",
            "Groessen",
            "Bruecke",
            "draussen",
            "ausfuehren",
        ]
        for spelling in legacy_spellings:
            self.assertNotIn(spelling, text)

    def test_seeded_api_reference_covers_all_core_capabilities(self):
        import seed

        seed = importlib.reload(seed)
        with contextlib.redirect_stdout(io.StringIO()):
            seed.seed()

        api_doc = self.af.get("gardener-api")
        self.assertIsNotNone(api_doc)
        content = api_doc["content"]

        for method in (
            "find(", "recall(", "get(", "put(", "delete(", "list(", "run(",
            "pin(", "unpin(",
            "memo(", "lesson(", "session_end(", "consolidate(",
            "task(", "tasks(", "done(", "task_status(",
            "absorb(", "materialize(", "observe(", "sync(", "status(", "clean_workspace(",
            "observe_source_add(", "observe_source_list(", "observe_source_refresh(", "observe_sources(", "observe_source_remove("
        ):
            self.assertIn(method, content)

        for cli_cmd in (
            "find", "recall", "memo", "lesson", "session-end", "consolidate",
            "get", "put", "pin", "unpin", "delete", "list", "run",
            "absorb", "materialize", "observe", "sync", "status", "clean-workspace",
            "task", "tasks", "done", "observe-source", "gui"
        ):
            self.assertIn(f"python gardener.py {cli_cmd}", content)

    def test_clean_workspace_all_and_by_name(self):
        # Tools erzeugen und ausführen, um Workspace-Ordner zu generieren
        self.af.put("tool-a", content="```python\ndef execute(p):\n    return 'output a'\n```", type="tool")
        self.af.put("tool-b", content="```python\ndef execute(p):\n    return 'output b'\n```", type="tool")

        ok_a, out_a = self.af.run("tool-a")
        ok_b, out_b = self.af.run("tool-b")
        self.assertTrue(ok_a)
        self.assertTrue(ok_b)

        dir_a = self.af.workspace_dir / "tool-a"
        dir_b = self.af.workspace_dir / "tool-b"
        self.assertTrue((dir_a / "run.py").exists())
        self.assertTrue((dir_b / "run.py").exists())

        st = self.af.status()
        self.assertIn("workspace", st)
        self.assertGreaterEqual(st["workspace"]["files"], 2)

        # Selektiv nur tool-a aufräumen
        res_a = self.af.clean_workspace(name="tool-a")
        self.assertGreaterEqual(res_a["files"], 1)
        self.assertFalse(dir_a.exists())
        self.assertTrue(dir_b.exists())

        # Den restlichen Workspace komplett aufräumen
        res_all = self.af.clean_workspace()
        self.assertGreaterEqual(res_all["files"], 1)
        self.assertTrue(self.af.workspace_dir.exists())
        self.assertFalse(dir_b.exists())

        st_after = self.af.status()
        self.assertEqual(st_after["workspace"]["files"], 0)

    def test_clean_workspace_max_age_seconds(self):
        ws_test = self.af.workspace_dir / "tool-age"
        ws_test.mkdir(parents=True, exist_ok=True)
        old_file = ws_test / "old.txt"
        new_file = ws_test / "new.txt"
        old_file.write_text("old content", encoding="utf-8")
        new_file.write_text("new content", encoding="utf-8")

        # Modifikationszeit der alten Datei 200 Sekunden in die Vergangenheit setzen
        past_time = time.time() - 200
        os.utime(str(old_file), (past_time, past_time))

        # Bereinigung mit Schwellenwert 100 Sekunden
        res = self.af.clean_workspace(max_age_seconds=100)
        self.assertEqual(res["files"], 1)
        self.assertFalse(old_file.exists())
        self.assertTrue(new_file.exists())

        # Ein zukünftiger Zeitstempel erfüllt auch die Schwelle 0 nicht.
        future_time = time.time() + 5
        os.utime(str(new_file), (future_time, future_time))
        res_future = self.af.clean_workspace(max_age_seconds=0)
        self.assertEqual(res_future["files"], 0)
        self.assertTrue(new_file.exists())

        # Für die beabsichtigte Schwelle 0 die Datei deterministisch in die
        # Vergangenheit setzen, statt auf die Auflösung der Dateisystemuhr zu
        # vertrauen.
        recent_past_time = time.time() - 5
        os.utime(str(new_file), (recent_past_time, recent_past_time))
        res2 = self.af.clean_workspace(max_age_seconds=0)
        self.assertEqual(res2["files"], 1)
        self.assertFalse(new_file.exists())

    def test_clean_workspace_cli(self):
        # Datei in workspace erzeugen
        ws_test = self.af.workspace_dir / "tool-cli"
        ws_test.mkdir(parents=True, exist_ok=True)
        (ws_test / "run.py").write_text("print('hi')", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["GARDENER_DATA"] = str(self.af.data_dir)
        env["GARDENER_HOME"] = str(self.af.home)

        # 1. Bereinigen mit Treffer
        proc = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "clean-workspace", "tool-cli"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("Workspace für 'tool-cli' bereinigt:", proc.stdout)
        self.assertIn("Datei(en)", proc.stdout)

        # 2. Zweiter Lauf ohne Treffer
        proc2 = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "clean-workspace"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("Workspace ist sauber", proc2.stdout)

    def test_pin_and_unpin_api_and_persistence(self):
        # 1. Eintrag erstellen (standardmäßig unpinned)
        self.af.put("regel-1", content="Regel-Inhalt", type="knowledge")
        entry = self.af.get("regel-1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["pinned"], 0)

        # 2. pin() aufrufen
        ok = self.af.pin("regel-1")
        self.assertTrue(ok)
        entry_pinned = self.af.get("regel-1")
        self.assertEqual(entry_pinned["pinned"], 1)

        # 3. unpin() aufrufen
        ok_unpin = self.af.unpin("regel-1")
        self.assertTrue(ok_unpin)
        entry_unpinned = self.af.get("regel-1")
        self.assertEqual(entry_unpinned["pinned"], 0)

        # 4. Nicht-existierende Einträge
        self.assertFalse(self.af.pin("nicht-existent"))
        self.assertFalse(self.af.unpin("nicht-existent"))

    def test_list_with_pinned_filter(self):
        self.af.put("p-memo-1", content="Memo 1", type="memory", pinned=True)
        self.af.put("u-memo-2", content="Memo 2", type="memory", pinned=False)
        self.af.put("p-tool-1", content="Tool 1", type="tool", pinned=True)

        # Nur gepinnte Einträge
        pinned_entries = self.af.list(pinned=True)
        pinned_names = [e["name"] for e in pinned_entries]
        self.assertIn("p-memo-1", pinned_names)
        self.assertIn("p-tool-1", pinned_names)
        self.assertNotIn("u-memo-2", pinned_names)

        # Nur ungepinnte Einträge
        unpinned_entries = self.af.list(pinned=False)
        unpinned_names = [e["name"] for e in unpinned_entries]
        self.assertIn("u-memo-2", unpinned_names)
        self.assertNotIn("p-memo-1", unpinned_names)

        # Typ + Pinned Filter kombiniert
        pinned_tools = self.af.list(type="tool", pinned=True)
        pinned_tool_names = [e["name"] for e in pinned_tools]
        self.assertEqual(pinned_tool_names, ["p-tool-1"])

    def test_status_reports_pinned_entries(self):
        st_before = self.af.status()
        self.assertIn("pinned_entries", st_before)
        count_before = st_before["pinned_entries"]

        self.af.put("status-pin-test", content="content", type="knowledge", pinned=False)
        self.assertEqual(self.af.status()["pinned_entries"], count_before)

        self.af.pin("status-pin-test")
        self.assertEqual(self.af.status()["pinned_entries"], count_before + 1)

        self.af.unpin("status-pin-test")
        self.assertEqual(self.af.status()["pinned_entries"], count_before)

    def test_pin_and_unpin_cli(self):
        self.af.put("cli-pin-target", content="CLI Content", type="knowledge")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["GARDENER_DATA"] = str(self.af.data_dir)
        env["GARDENER_HOME"] = str(self.af.home)

        # 1. gardener pin
        proc_pin = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "pin", "cli-pin-target"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("[OK] 'cli-pin-target' angepinnt (dauerhaft geschützt)", proc_pin.stdout)

        # 2. gardener list --pinned
        proc_list = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "list", "--pinned"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("cli-pin-target", proc_list.stdout)
        self.assertIn("[PIN]", proc_list.stdout)

        # 3. gardener unpin
        proc_unpin = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "unpin", "cli-pin-target"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("[OK] Pinnadel von 'cli-pin-target' entfernt", proc_unpin.stdout)

        # 4. gardener pin auf nicht existierenden Eintrag
        proc_missing = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "pin", "nicht-vorhanden"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("Nicht gefunden: nicht-vorhanden", proc_missing.stdout)

    def test_find_with_pinned_filter(self):
        self.af.put("find-p-1", content="Einheitlicher Pin-Suchbegriff alpha", type="knowledge", pinned=True)
        self.af.put("find-u-1", content="Einheitlicher Pin-Suchbegriff beta", type="knowledge", pinned=False)
        self.af.put("find-p-2", content="Einheitlicher Pin-Suchbegriff gamma", type="memory", pinned=True)

        # 1. pinned=True liefert nur gepinnte Treffer
        res_pinned = self.af.find("Pin-Suchbegriff", pinned=True)
        names_pinned = [r["name"] for r in res_pinned]
        self.assertIn("find-p-1", names_pinned)
        self.assertIn("find-p-2", names_pinned)
        self.assertNotIn("find-u-1", names_pinned)

        # 2. pinned=False liefert nur ungepinnte Treffer
        res_unpinned = self.af.find("Pin-Suchbegriff", pinned=False)
        names_unpinned = [r["name"] for r in res_unpinned]
        self.assertEqual(names_unpinned, ["find-u-1"])

        # 3. pinned=None liefert alle Treffer, mit gepinnten zuerst
        res_all = self.af.find("Pin-Suchbegriff", pinned=None)
        names_all = [r["name"] for r in res_all]
        self.assertEqual(len(names_all), 3)
        self.assertEqual(res_all[0]["pinned"], 1)
        self.assertEqual(res_all[1]["pinned"], 1)
        self.assertEqual(res_all[2]["pinned"], 0)

        # 4. Filter kombiniert mit type
        res_typed = self.af.find("Pin-Suchbegriff", type="memory", pinned=True)
        self.assertEqual([r["name"] for r in res_typed], ["find-p-2"])

    def test_find_pinned_cli(self):
        self.af.put("cli-p-item", content="CLI Pin Testinhalt", type="knowledge", pinned=True)
        self.af.put("cli-u-item", content="CLI Pin Testinhalt", type="knowledge", pinned=False)

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["GARDENER_DATA"] = str(self.af.data_dir)
        env["GARDENER_HOME"] = str(self.af.home)

        # 1. gardener find --pinned
        proc_pinned = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "find", "--pinned", "Testinhalt"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("cli-p-item", proc_pinned.stdout)
        self.assertIn("[PIN]", proc_pinned.stdout)
        self.assertNotIn("cli-u-item", proc_pinned.stdout)

        # 2. gardener find --unpinned
        proc_unpinned = subprocess.run(
            [sys.executable, str(ROOT / "gardener.py"), "find", "--unpinned", "Testinhalt"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("cli-u-item", proc_unpinned.stdout)
        self.assertNotIn("cli-p-item", proc_unpinned.stdout)
        self.assertNotIn("[PIN]", proc_unpinned.stdout)


class TestCliI18n(unittest.TestCase):
    def run_help(self, lang):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["GARDENER_DATA"] = str(Path(tmp) / "data")
            env["GARDENER_HOME"] = str(Path(tmp) / "home")
            env["GARDENER_LANG"] = lang
            result = subprocess.run(
                [sys.executable, str(ROOT / "gardener.py")],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            )
            return result.stdout

    def test_german_help_uses_real_umlauts(self):
        output = self.run_help("de")
        self.assertIn("Befehle:", output)
        self.assertIn("Einträge", output)
        self.assertIn("Gedächtnis konsolidieren", output)
        self.assertNotIn("Gedaechtnis", output)

    def test_english_help_from_environment(self):
        output = self.run_help("en")
        self.assertIn("Gardener -- LLM-native operating system", output)
        self.assertIn("Commands:", output)
        self.assertIn("Consolidate memory", output)

    def test_help_falls_back_when_translations_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp) / "app"
            app_dir.mkdir()
            shutil.copy2(ROOT / "gardener.py", app_dir / "gardener.py")
            shutil.copy2(ROOT / "i18n.py", app_dir / "i18n.py")

            for lang, expected in (
                ("de", "Gedächtnis konsolidieren"),
                ("en", "Consolidate memory"),
            ):
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["GARDENER_DATA"] = str(Path(tmp) / f"data-{lang}")
                env["GARDENER_HOME"] = str(Path(tmp) / f"home-{lang}")
                env["GARDENER_LANG"] = lang
                result = subprocess.run(
                    [sys.executable, str(app_dir / "gardener.py")],
                    cwd=app_dir,
                    env=env,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    check=True,
                )
                self.assertIn(expected, result.stdout)
                self.assertNotIn("cmd.consolidate", result.stdout)
                self.assertNotIn("help.title", result.stdout)


class TestRepositoryHygiene(unittest.TestCase):
    def setUp(self):
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.skipTest("Not inside a git repository")

    def test_gitignore_protects_runtime_and_secret_artifacts(self):
        protected_paths = [
            "gardener.db-wal",
            "gardener.db-shm",
            "user.sqlite3",
            ".env",
            ".env.local",
            ".npmrc",
            ".pypirc",
            "credentials.json",
            "token.json",
            "secrets.json",
            "deploy.pem",
            "deploy.key",
            "id_ed25519",
            "npm_recovery_codes.txt",
        ]

        result = subprocess.run(
            ["git", "check-ignore", "-v", *protected_paths],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        ignored = {
            line.rsplit("\t", 1)[-1].replace("\\", "/")
            for line in result.stdout.splitlines()
            if "\t" in line
        }
        self.assertEqual(set(protected_paths), ignored)

    def test_gitignore_keeps_env_examples_trackable(self):
        for path in (".env.example", ".env.sample"):
            result = subprocess.run(
                ["git", "check-ignore", "--quiet", path],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 1, path)


class TestGardenerHardening(GardenerTempCase):
    def test_materialize_sanitizes_traversal_filename(self):
        self.af.put(
            "evil-entry",
            content="harmlos",
            type="document",
            meta={"filename": "../../../evil.txt"},
        )
        dest = Path(self.temp.name) / "safe-dest"
        out_path = self.af.materialize("evil-entry", dest=dest)
        self.assertEqual(out_path.parent, dest)
        self.assertEqual(out_path.name, "evil.txt")
        self.assertFalse((Path(self.temp.name) / "evil.txt").exists())

    def test_materialize_sanitizes_absolute_filename(self):
        target = Path(self.temp.name) / "outside.txt"
        self.af.put(
            "evil-abs",
            content="harmlos",
            type="document",
            meta={"filename": str(target)},
        )
        dest = Path(self.temp.name) / "safe-dest"
        out_path = self.af.materialize("evil-abs", dest=dest)
        self.assertEqual(out_path.parent, dest)
        self.assertFalse(target.exists())

    def test_absorb_directory_raises_clean_error(self):
        folder = Path(self.temp.name) / "ein-ordner"
        folder.mkdir()
        with self.assertRaises(FileNotFoundError):
            self.af.absorb(folder)

    def test_sync_always_absorb_preserves_config_json(self):
        home = Path(os.environ["GARDENER_HOME"])
        (home / "notiz.txt").write_text("inhalt", encoding="utf-8")
        self.af.config["mode"] = "always_absorb"
        self.af.sync()
        self.assertTrue((home / "config.json").exists())
        self.assertFalse((home / "notiz.txt").exists())

    def test_is_internal_matches_segments_not_prefixes(self):
        is_internal = self.gardener.Gardener._is_internal
        self.assertTrue(is_internal(".absorber/x.txt"))
        self.assertTrue(is_internal("sub/__pycache__/x.pyc"))
        self.assertTrue(is_internal("config.json"))
        self.assertFalse(is_internal(".absorber-notes.txt"))
        self.assertFalse(is_internal(".outputs/x.txt"))
        self.assertFalse(is_internal("sub/config.json"))

    def test_observe_names_use_posix_separators(self):
        home = Path(os.environ["GARDENER_HOME"])
        nested = home / "unterordner"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "datei.txt").write_text("inhalt", encoding="utf-8")
        observed = self.af.observe()
        names = [o["name"] for o in observed]
        self.assertIn("observed/unterordner/datei.txt", names)
        self.assertFalse(any("\\" in n for n in names))

    def test_sqlite_connection_context_manager_safety(self):
        with self.af.connection("user") as conn:
            self.assertIsNotNone(conn)
            row = conn.execute("SELECT 1").fetchone()
            self.assertEqual(row[0], 1)


class TestFindSourceFilter(GardenerTempCase):
    """find(source=...) -- WHERE-Filter auf den observed/<id>/-Namensraum."""

    def _observed(self, source_id, key, content, type="observed"):
        return self.af.put(f"observed/{source_id}/{key}", content=content, type=type)

    def test_source_filter_restricts_to_one_source(self):
        self._observed("usmc-working", "n1", "Store-Welle eingereicht")
        self._observed("codex-sessions", "n2", "Store-Welle eingereicht")

        hits = self.af.find("Store-Welle", source="usmc-working")
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0]["name"].startswith("observed/usmc-working/"))

    def test_source_filter_beats_bulk_source_in_ranking(self):
        """Der eigentliche Fehlerfall: die grosse Quelle verdraengt die kleine."""
        for i in range(40):
            self._observed("codex-sessions", f"line{i}", "Store Welle Einreichung Notiz")
        self._observed("usmc-working", "treffer", "Store Welle Einreichung Notiz")

        ungefiltert = self.af.find("Store Welle Einreichung", limit=5)
        self.assertTrue(all("codex-sessions" in r["name"] for r in ungefiltert))

        gefiltert = self.af.find("Store Welle Einreichung", limit=5, source="usmc-working")
        self.assertEqual(len(gefiltert), 1)
        self.assertEqual(gefiltert[0]["name"], "observed/usmc-working/treffer")

    def test_source_filter_accepts_multiple_ids(self):
        self._observed("usmc-working", "a", "gemeinsamer Begriff")
        self._observed("usmc-facts", "b", "gemeinsamer Begriff")
        self._observed("codex-sessions", "c", "gemeinsamer Begriff")

        hits = self.af.find("gemeinsamer", source="usmc-working,usmc-facts")
        self.assertEqual(len(hits), 2)
        self.assertFalse(any("codex-sessions" in r["name"] for r in hits))

    def test_source_filter_accepts_list_and_observed_prefix(self):
        self._observed("usmc-working", "a", "Testinhalt")
        self._observed("codex-sessions", "b", "Testinhalt")

        self.assertEqual(len(self.af.find("Testinhalt", source=["usmc-working"])), 1)
        self.assertEqual(len(self.af.find("Testinhalt", source="observed/usmc-working")), 1)
        self.assertEqual(len(self.af.find("Testinhalt", source="observed/usmc-working/")), 1)

    def test_source_id_matches_whole_segment_only(self):
        """'usmc' darf 'usmc-working' nicht mitnehmen -- Praefix ist bis zum Slash."""
        self._observed("usmc-working", "a", "Segmenttest")
        self._observed("usmc", "b", "Segmenttest")

        hits = self.af.find("Segmenttest", source="usmc")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["name"], "observed/usmc/b")

    def test_source_filter_escapes_like_wildcards(self):
        """'_' ist ein LIKE-Platzhalter und darf nicht als solcher wirken."""
        self._observed("a_b", "x", "Wildcardtest")
        self._observed("axb", "y", "Wildcardtest")

        hits = self.af.find("Wildcardtest", source="a_b")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["name"], "observed/a_b/x")

    def test_source_filter_survives_multi_word_or_fallback(self):
        """Stufe 2 von find(): OR-Fallback darf den Filter nicht verlieren."""
        self._observed("codex-sessions", "a", "Alpha")
        self._observed("usmc-working", "b", "Beta")

        # Kein Eintrag enthaelt beide Woerter -> exakte FTS-Suche liefert 0,
        # der OR-Fallback greift.
        hits = self.af.find("Alpha Beta", source="usmc-working")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["name"], "observed/usmc-working/b")

    def test_source_filter_survives_like_fallback(self):
        """Stufe 3 von find(): auch die LIKE-Suche filtert nach Quelle."""
        self._observed("codex-sessions", "a", "Teilwortsuche")
        self._observed("usmc-working", "b", "Teilwortsuche")

        with self.af.connection("user") as conn:
            hits = self.af._like_query(conn, "eilwortsuch", source="usmc-working")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["name"], "observed/usmc-working/b")

    def test_source_without_query_lists_the_source(self):
        self._observed("usmc-working", "a", "eins")
        self._observed("usmc-working", "b", "zwei")
        self._observed("codex-sessions", "c", "drei")

        hits = self.af.find("", source="usmc-working")
        self.assertEqual(len(hits), 2)
        self.assertTrue(all("usmc-working" in r["name"] for r in hits))

    def test_empty_query_without_source_keeps_browse_behaviour(self):
        """Ohne Quelle bleibt die leere Query, was sie war: LIKE '%%' listet alles.

        Der Nur-Quelle-Zweig darf diesen Altbestand nicht stillschweigend
        auf [] umbiegen -- er ist der einzige Verhaltenspfad, den ein
        bestehender Aufrufer bereits nutzen konnte.
        """
        self._observed("usmc-working", "a", "eins")
        self._observed("codex-sessions", "b", "zwei")
        self.assertEqual(len(self.af.find("")), 2)

    def test_source_combines_with_type(self):
        self._observed("usmc-working", "a", "Kombitest", type="observed")
        self._observed("usmc-working", "b", "Kombitest", type="memory")

        hits = self.af.find("Kombitest", source="usmc-working", type="memory")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["type"], "memory")

    def test_find_without_source_is_unchanged(self):
        self._observed("usmc-working", "a", "Rueckwaertskompatibel")
        self._observed("codex-sessions", "b", "Rueckwaertskompatibel")

        self.assertEqual(len(self.af.find("Rueckwaertskompatibel")), 2)
        self.assertEqual(len(self.af.find("Rueckwaertskompatibel", source=None)), 2)
        self.assertEqual(len(self.af.find("Rueckwaertskompatibel", source="")), 2)

    def test_unknown_source_yields_no_hits(self):
        self._observed("usmc-working", "a", "Vorhanden")
        self.assertEqual(self.af.find("Vorhanden", source="gibtsnicht"), [])

    def test_normalize_sources_helper(self):
        norm = self.gardener.Gardener._normalize_sources
        self.assertEqual(norm(None), [])
        self.assertEqual(norm(""), [])
        self.assertEqual(norm("a"), ["a"])
        self.assertEqual(norm("a,b"), ["a", "b"])
        self.assertEqual(norm(" a , b "), ["a", "b"])
        self.assertEqual(norm("observed/a/"), ["a"])
        self.assertEqual(norm(["observed/a", "b"]), ["a", "b"])
        self.assertEqual(norm("a,,b"), ["a", "b"])


class TestFindArgParsing(unittest.TestCase):
    """Das find-CLI kennt kein argparse -- die Trennung muss selbst stimmen."""

    def setUp(self):
        import gardener

        self.parse = gardener._parse_find_args

    def test_plain_query_has_no_options(self):
        opts, words, err = self.parse(["store", "welle"])
        self.assertIsNone(err)
        self.assertEqual(words, ["store", "welle"])
        self.assertIsNone(opts["source"])
        self.assertEqual(opts["limit"], 20)

    def test_source_is_not_swallowed_into_the_query(self):
        opts, words, err = self.parse(["--source", "usmc-working", "store"])
        self.assertIsNone(err)
        self.assertEqual(opts["source"], "usmc-working")
        self.assertEqual(words, ["store"])

    def test_equals_form(self):
        opts, words, err = self.parse(["--source=usmc-working", "--type=memory", "store"])
        self.assertIsNone(err)
        self.assertEqual(opts["source"], "usmc-working")
        self.assertEqual(opts["type"], "memory")
        self.assertEqual(words, ["store"])

    def test_limit_is_an_int(self):
        opts, words, err = self.parse(["--limit", "5", "store"])
        self.assertIsNone(err)
        self.assertEqual(opts["limit"], 5)

    def test_bad_limit_reports_error(self):
        _, _, err = self.parse(["--limit", "viele"])
        self.assertIsNotNone(err)
        _, _, err = self.parse(["--limit", "0"])
        self.assertIsNotNone(err)

    def test_unknown_option_reports_error(self):
        _, _, err = self.parse(["--quelle", "x"])
        self.assertIsNotNone(err)
        self.assertIn("--quelle", err)

    def test_missing_value_reports_error(self):
        _, _, err = self.parse(["store", "--source"])
        self.assertIsNotNone(err)

    def test_options_may_follow_the_query(self):
        opts, words, err = self.parse(["store", "--source", "usmc-working"])
        self.assertIsNone(err)
        self.assertEqual(words, ["store"])
        self.assertEqual(opts["source"], "usmc-working")

    def test_refresh_source_is_parsed_separately_from_query(self):
        opts, words, err = self.parse([
            "--refresh-source", "claude-transcripts,control-tickets",
            "aecf581b-951d-4f7d-ba13-16fdbfe459cb",
        ])
        self.assertIsNone(err)
        self.assertEqual(
            opts["refresh-source"], "claude-transcripts,control-tickets")
        self.assertEqual(words, ["aecf581b-951d-4f7d-ba13-16fdbfe459cb"])


class TestSQLiteHardeningAndLifecycle(GardenerTempCase):
    """Prüfungen für Connection-Lifecycle, Timeout-Absicherung und Context-Manager."""

    def test_connection_context_manager_closes_after_block(self):
        with self.af.connection("user") as conn:
            self.assertIsNotNone(conn)
            row = conn.execute("SELECT 1").fetchone()
            self.assertEqual(row[0], 1)
            c = conn
        with self.assertRaises(sqlite3.ProgrammingError):
            c.execute("SELECT 1")

    def test_connection_context_manager_closes_on_exception(self):
        c = None
        with self.assertRaises(ValueError), self.af.connection("user") as conn:
            c = conn
            raise ValueError("test error")
        self.assertIsNotNone(c)
        with self.assertRaises(sqlite3.ProgrammingError):
            c.execute("SELECT 1")

    def test_connection_context_manager_system_target(self):
        with self.af.connection("system") as conn:
            c = conn
            row = conn.execute("SELECT 1").fetchone()
            self.assertEqual(row[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            c.execute("SELECT 1")

    def test_gardener_class_as_context_manager(self):
        home_path = Path(self.temp.name) / "cm_home"
        data_path = Path(self.temp.name) / "cm_data"
        with self.gardener.Gardener(home=home_path, data_dir=data_path) as g:
            g.put("cm_test_entry", content="lifecycle works", type="memory")
            res = g.get("cm_test_entry")
            self.assertIsNotNone(res)
            self.assertEqual(res["content"], "lifecycle works")

    def test_db_timeout_default_and_custom(self):
        self.assertEqual(self.af.db_timeout, 30.0)

        custom_home = Path(self.temp.name) / "custom_home"
        custom_data = Path(self.temp.name) / "custom_data"
        custom_home.mkdir(parents=True, exist_ok=True)
        with open(custom_home / "config.json", "w", encoding="utf-8") as f:
            json.dump({"db_timeout": 12.5}, f)

        g_custom = self.gardener.Gardener(home=custom_home, data_dir=custom_data)
        self.assertEqual(g_custom.db_timeout, 12.5)

    def test_conn_cleanup_on_attach_failure(self):
        # Wenn der zu attachende Pfad ein Verzeichnis statt einer Datei ist,
        # schlägt ATTACH fehl. _conn() muss die Connection schließen und die Exception re-raisen.
        original_system_db = self.af.system_db_path
        try:
            self.af.system_db_path = Path(self.temp.name)  # directory
            with self.assertRaises(sqlite3.OperationalError):
                self.af._conn("user")
        finally:
            self.af.system_db_path = original_system_db


class TestGardenerCli(unittest.TestCase):
    def setUp(self):
        import gardener
        self.gardener_mod = gardener
        self.temp_home = tempfile.TemporaryDirectory()
        self.temp_data = tempfile.TemporaryDirectory()
        self.orig_env = os.environ.copy()
        os.environ["GARDENER_HOME"] = self.temp_home.name
        os.environ["GARDENER_DATA"] = self.temp_data.name

    def tearDown(self):
        self.temp_home.cleanup()
        self.temp_data.cleanup()
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_cli_help_flags_output_usage(self):
        for flag in ("-h", "--help", "help"):
            with patch("sys.argv", ["gardener", flag]):
                buf = io.StringIO()
                with patch("sys.stdout", buf):
                    self.gardener_mod.main()
                out = buf.getvalue()
                self.assertIn("Gardener", out)
                self.assertIn("gardener find", out)
                self.assertIn("gardener status", out)
                self.assertNotIn("Unbekannter Befehl", out)

    def test_cli_no_args_outputs_usage(self):
        with patch("sys.argv", ["gardener"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                self.gardener_mod.main()
            out = buf.getvalue()
            self.assertIn("Gardener", out)
            self.assertIn("gardener find", out)

    def test_cli_unknown_command(self):
        with patch("sys.argv", ["gardener", "nonexistent-cmd"]):
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                self.gardener_mod.main()
            out = buf.getvalue()
            self.assertIn("Unbekannter Befehl: nonexistent-cmd", out)


if __name__ == "__main__":
    unittest.main()
