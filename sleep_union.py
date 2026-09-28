"""Soft sleep for memory_union v2 databases. No records are deleted."""

from __future__ import annotations

import json
import os
import sqlite3
import warnings
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None


DEFAULTS = {
    "fact_decay_rate": 0.01,
    "lesson_decay_rate": 0.005,
    "min_confidence": 0.2,
    "max_facts": 1000,
    "max_lessons": 200,
    "auto_cleanup_enabled": 1,
    "cleanup_interval_days": 7,
    "last_cleanup_at": None,
}
REQUIRED_WORKING = {"type", "expires_at", "is_active", "agent_id", "created_at"}


def _columns(conn, table):
    # Names come only from this module, never from user input.
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _config(path):
    if not path.is_file():
        return {}
    if tomllib is None:
        warnings.warn("sleep.toml ignored: Python 3.10 has no tomllib", RuntimeWarning, stacklevel=2)
        return {}
    with path.open("rb") as handle:
        config = tomllib.load(handle)
    return config.get("ttl_days", {})


def _ttl(config, agent, kind):
    value = config.get(agent, {}).get(kind, config.get("default", {}).get(kind, {"handoff": 30, "context": 14}[kind]))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid TTL for {agent}/{kind}: {value!r}")
    return value


def _time(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(value)


def sleep(db_path, *, agent=None, if_due=False, dry_run=False, decay=True,
          report=None, now=None, config_path=None) -> dict:
    """Apply TTL grace/deactivation and optional confidence decay atomically.

    ``dry_run`` opens the database read-only and rolls back the simulated updates.
    The caller must pass ``decay=False`` for BACH, which owns its own decay path.
    """
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    current = _time(now) if now is not None else datetime.now(timezone.utc).replace(tzinfo=None)
    stamp = current.strftime("%Y-%m-%d %H:%M:%S")
    config_file = Path(config_path or os.environ.get("GARDENER_SLEEP_CONFIG") or
                       Path.home() / ".gardener" / "sleep.toml")
    ttl_config = _config(config_file)
    uri = path.as_uri() + ("?mode=ro" if dry_run else "?mode=rw")
    result = {"time": stamp, "db_path": str(path), "dry_run": dry_run, "agents": {}}
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN" if dry_run else "BEGIN IMMEDIATE")
        try:
            schemas = {name: _columns(conn, name) for name in
                       ("memory_working", "memory_facts", "memory_lessons", "decay_config")}
            if not schemas["memory_working"] >= REQUIRED_WORKING:
                missing = sorted(REQUIRED_WORKING - schemas["memory_working"])
                raise ValueError(f"memory_working Union contract missing columns: {missing}")
            agent_ids = set()
            for table in ("memory_working", "memory_facts", "memory_lessons"):
                if "agent_id" in schemas[table]:
                    agent_ids.update(row[0] for row in conn.execute(
                        f"SELECT DISTINCT agent_id FROM {table} WHERE agent_id IS NOT NULL"))
            if agent is not None:
                agent_ids = {agent}

            config_columns = schemas["decay_config"]
            has_config = {"agent_id", "last_cleanup_at"} <= config_columns
            for agent_id in sorted(agent_ids):
                stats = {"ttl_gesetzt": 0, "deaktiviert": 0, "facts_decayed": 0,
                         "lessons_decayed": 0, "caps_ueberschritten": {}, "uebersprungen": []}
                result["agents"][agent_id] = stats
                cfg = dict(DEFAULTS)
                if has_config:
                    row = conn.execute("SELECT * FROM decay_config WHERE agent_id=?", (agent_id,)).fetchone()
                    if row:
                        cfg.update({key: row[key] for key in DEFAULTS
                                    if key in config_columns and row[key] is not None})
                else:
                    stats["uebersprungen"].append("decay_config missing required columns")
                    if if_due:
                        stats["uebersprungen"].append("decay_config_unavailable")
                        continue
                if if_due:
                    if not cfg["auto_cleanup_enabled"]:
                        stats["uebersprungen"].append("auto_cleanup_disabled")
                        continue
                    if cfg["last_cleanup_at"]:
                        elapsed = (current - _time(cfg["last_cleanup_at"])).total_seconds() / 86400
                        if elapsed < cfg["cleanup_interval_days"]:
                            stats["uebersprungen"].append("not_due")
                            continue

                # Deactivate only pre-existing expirations. Newly assigned TTLs wait
                # until a later invocation, even when their calculated date is past.
                stats["deaktiviert"] = conn.execute(
                    "SELECT COUNT(*) FROM memory_working WHERE agent_id=? AND is_active=1 "
                    "AND type IN ('handoff', 'context') AND expires_at IS NOT NULL "
                    "AND datetime(expires_at) < datetime(?)", (agent_id, stamp)).fetchone()[0]
                if not dry_run:
                    conn.execute("UPDATE memory_working SET is_active=0 WHERE agent_id=? AND is_active=1 "
                                 "AND type IN ('handoff', 'context') AND expires_at IS NOT NULL "
                                 "AND datetime(expires_at) < datetime(?)", (agent_id, stamp))
                for kind in ("handoff", "context"):
                    days = _ttl(ttl_config, agent_id, kind)
                    predicate = ("agent_id=? AND type=? AND is_active=1 AND expires_at IS NULL "
                                 "AND datetime(created_at) IS NOT NULL")
                    stats["ttl_gesetzt"] += conn.execute(
                        f"SELECT COUNT(*) FROM memory_working WHERE {predicate}",
                        (agent_id, kind)).fetchone()[0]
                    if not dry_run:
                        conn.execute(f"UPDATE memory_working SET expires_at=datetime(created_at, ?) "
                                     f"WHERE {predicate}", (f"+{days} days", agent_id, kind))

                for table, rate_key, counter in (
                    ("memory_facts", "fact_decay_rate", "facts_decayed"),
                    ("memory_lessons", "lesson_decay_rate", "lessons_decayed"),
                ):
                    columns = schemas[table]
                    if not {"agent_id", "confidence"} <= columns:
                        stats["uebersprungen"].append(f"{table} missing confidence/agent_id")
                        continue
                    floor = cfg["min_confidence"]
                    if decay:
                        days = max(0, (current - _time(cfg["last_cleanup_at"])).days) if cfg["last_cleanup_at"] else 1
                        rate = cfg[rate_key]
                        if not 0 <= rate <= 1 or not 0 <= floor <= 1:
                            raise ValueError(f"Invalid decay_config for {agent_id}")
                        if days:
                            entries = conn.execute(
                                f"SELECT rowid AS sleep_rowid, confidence FROM {table} WHERE agent_id=? "
                                "AND confidence > ?", (agent_id, floor)).fetchall()
                            stats[counter] = len(entries)
                            if not dry_run:
                                conn.executemany(f"UPDATE {table} SET confidence=? WHERE rowid=?",
                                                 [(max(floor, item["confidence"] * (1 - rate) ** days),
                                                   item["sleep_rowid"]) for item in entries])
                    cap = cfg["max_facts" if table == "memory_facts" else "max_lessons"]
                    active = " AND is_active=1" if "is_active" in columns else ""
                    count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE agent_id=?{active}",
                                         (agent_id,)).fetchone()[0]
                    if cap is not None and count > cap:
                        stats["caps_ueberschritten"]["facts" if table == "memory_facts" else "lessons"] = count - cap

                if has_config and not dry_run:
                    conn.execute("INSERT OR IGNORE INTO decay_config (agent_id) VALUES (?)", (agent_id,))
                    conn.execute("UPDATE decay_config SET last_cleanup_at=? WHERE agent_id=?",
                                 (stamp, agent_id))
            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
    if report is not None:
        with Path(report).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result
