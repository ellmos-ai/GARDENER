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
        # Explicit quotes -> None (preserved user phrase)
        self.assertIsNone(build_or('"Registry Mitgliedschaft"'))
        # Explicit operators -> None (preserved user boolean query)
        self.assertIsNone(build_or("Registry AND Mitgliedschaft"))
        self.assertIsNone(build_or("Registry OR Mitgliedschaft"))
        self.assertIsNone(build_or("Registry NOT Mitgliedschaft"))

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

        # Jetzt auch die neuere Datei bereinigen. Windows-Dateisysteme können
        # einen mtime knapp vor die Python-Uhr setzen; 0 bedeutet trotzdem
        # ausdrücklich "kein Mindestalter".
        future_time = time.time() + 5
        os.utime(str(new_file), (future_time, future_time))
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


if __name__ == "__main__":
    unittest.main()
