"""Contract tests for the Union sleep path; all databases are temporary."""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

import pytest

import sleep_union
from sleep_union import sleep

NOW = datetime(2026, 9, 27, 12, 0, 0)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "union.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE memory_working (
                id INTEGER PRIMARY KEY, agent_id TEXT, type TEXT, created_at TEXT,
                expires_at TEXT, is_active INTEGER DEFAULT 1);
            CREATE TABLE memory_facts (
                id INTEGER PRIMARY KEY, agent_id TEXT, confidence REAL);
            CREATE TABLE memory_lessons (
                id INTEGER PRIMARY KEY, agent_id TEXT, confidence REAL,
                is_active INTEGER DEFAULT 1);
            CREATE TABLE decay_config (
                agent_id TEXT PRIMARY KEY, fact_decay_rate REAL DEFAULT 0.01,
                lesson_decay_rate REAL DEFAULT 0.005, min_confidence REAL DEFAULT 0.2,
                max_facts INTEGER DEFAULT 1000, max_lessons INTEGER DEFAULT 200,
                auto_cleanup_enabled INTEGER DEFAULT 1,
                cleanup_interval_days INTEGER DEFAULT 7, last_cleanup_at TEXT);
        """)
    return path


def rows(path, table):
    with sqlite3.connect(path) as conn:
        return conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()


def run_sleep(db, **kwargs):
    return sleep(db, now=NOW, config_path=db.with_suffix(".toml"), **kwargs)


def test_grace_period_and_permanent_types(db):
    with sqlite3.connect(db) as conn:
        conn.executemany(
            "INSERT INTO memory_working VALUES (?, 'a', ?, ?, ?, 1)",
            [(1, "handoff", "2026-08-01 00:00:00", None),
             (2, "context", "2026-08-01 00:00:00", None),
             (3, "note", "2020-01-01 00:00:00", None),
             (4, "loop", "2020-01-01 00:00:00", None),
             (5, "handoff", "2026-08-01 00:00:00", "2026-09-26 00:00:00")])
    first = run_sleep(db, decay=False)
    assert first["agents"]["a"]["ttl_gesetzt"] == 2
    assert first["agents"]["a"]["deaktiviert"] == 1
    assert [r[-1] for r in rows(db, "memory_working")] == [1, 1, 1, 1, 0]
    second = run_sleep(db, decay=False)
    assert second["agents"]["a"]["deaktiviert"] == 2
    assert [r[-1] for r in rows(db, "memory_working")] == [0, 0, 1, 1, 0]
    assert len(rows(db, "memory_working")) == 5


def test_ttl_override_and_dry_run(db):
    db.with_suffix(".toml").write_text(
        "[ttl_days.default]\nhandoff = 30\ncontext = 14\n"
        "[ttl_days.a]\nhandoff = 3\n", encoding="utf-8")
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO memory_working VALUES (1, 'a', 'handoff', '2026-09-20 00:00:00', NULL, 1)")
    before = db.read_bytes()
    preview = run_sleep(db, dry_run=True, decay=False)
    assert preview["agents"]["a"]["ttl_gesetzt"] == 1
    assert db.read_bytes() == before
    if sleep_union.tomllib is None:
        with pytest.warns(RuntimeWarning, match="sleep.toml ignored"):
            run_sleep(db, decay=False)
        expected = "2026-10-20 00:00:00"
    else:
        run_sleep(db, decay=False)
        expected = "2026-09-23 00:00:00"
    assert rows(db, "memory_working")[0][4] == expected


def test_decay_floor_caps_and_no_decay(db):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO memory_facts VALUES (1, 'a', 0.8)")
        conn.execute("INSERT INTO memory_lessons VALUES (1, 'a', 0.21, 1)")
        conn.execute("INSERT INTO decay_config (agent_id, fact_decay_rate, lesson_decay_rate, "
                     "min_confidence, max_facts, max_lessons, last_cleanup_at) "
                     "VALUES ('a', 0.1, 0.5, 0.2, 0, 0, '2026-09-24 12:00:00')")
    run_sleep(db, decay=False)
    assert rows(db, "memory_facts")[0][2] == 0.8
    # Restore elapsed time so this run has exactly three full days.
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE decay_config SET last_cleanup_at='2026-09-24 12:00:00'")
    result = run_sleep(db)
    assert rows(db, "memory_facts")[0][2] == pytest.approx(0.8 * 0.9 ** 3)
    assert rows(db, "memory_lessons")[0][2] == pytest.approx(0.2)
    assert result["agents"]["a"]["caps_ueberschritten"] == {"facts": 1, "lessons": 1}


def test_if_due_report_and_no_delete(db, tmp_path):
    report = tmp_path / "report.jsonl"
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO memory_working VALUES (1, 'a', 'handoff', '2026-08-01 00:00:00', NULL, 1)")
        conn.execute("INSERT INTO memory_working VALUES (2, 'b', 'context', '2026-08-01 00:00:00', NULL, 1)")
        conn.execute("INSERT INTO decay_config (agent_id, auto_cleanup_enabled) VALUES ('a', 0)")
    result = run_sleep(db, if_due=True, decay=False, report=report)
    assert result["agents"]["a"]["uebersprungen"] == "auto_cleanup_disabled"
    assert result["agents"]["b"]["ttl_gesetzt"] == 1
    assert rows(db, "decay_config")[1][-1] == "2026-09-27 12:00:00"
    assert len(rows(db, "memory_working")) == 2
    again = run_sleep(db, if_due=True, decay=False, report=report)
    assert again["agents"]["b"]["uebersprungen"] == "not_due"
    assert len(report.read_text(encoding="utf-8").splitlines()) == 2
    assert json.loads(report.read_text(encoding="utf-8").splitlines()[0])["db_path"] == str(db)


def test_missing_contract_and_optional_steps(db):
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE memory_lessons")
        conn.execute("DROP TABLE decay_config")
        conn.execute("INSERT INTO memory_facts VALUES (1, 'a', 0.8)")
    result = run_sleep(db)
    assert any("memory_lessons" in reason for reason in result["agents"]["a"]["uebersprungen"])
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE memory_working")
    with pytest.raises(ValueError, match="memory_working"):
        run_sleep(db)


def test_rollback_on_update_failure(db):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO memory_working VALUES (1, 'a', 'handoff', '2026-08-01 00:00:00', NULL, 1)")
        conn.execute("INSERT INTO memory_facts VALUES (1, 'a', 0.9)")
        conn.executescript("""
            CREATE TRIGGER reject_decay BEFORE UPDATE OF confidence ON memory_facts
            BEGIN SELECT RAISE(ABORT, 'decay rejected'); END;
        """)
    before = {table: rows(db, table) for table in
              ("memory_working", "memory_facts", "decay_config")}
    with pytest.raises(sqlite3.IntegrityError, match="decay rejected"):
        run_sleep(db)
    assert {table: rows(db, table) for table in before} == before


def test_cli_dry_run_uses_only_selected_database(db):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO memory_working VALUES (1, 'a', 'handoff', '2026-08-01 00:00:00', NULL, 1)")
    env = os.environ.copy()
    env["GARDENER_SLEEP_CONFIG"] = str(db.with_suffix(".toml"))
    env["GARDENER_DATA"] = str(db.parent / "must_not_be_created")
    command = [sys.executable, "gardener.py", "sleep", "--db", str(db),
               "--agent", "a", "--dry-run", "--no-decay"]
    result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    assert result.returncode == 0, result.stderr
    assert "TTL 1" in result.stdout
    assert not (db.parent / "must_not_be_created").exists()
