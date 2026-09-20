# -*- coding: utf-8 -*-
"""Tests fuer das Standard-Set an observe-sources beim Seed.

Der interessante Fall ist nicht der eigene Host (dort ist ohnehin alles
konfiguriert), sondern ein fremder: Dort existiert ein Teil der Pfade nicht,
und genau dann darf nichts angelegt und nichts geworfen werden.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import seed  # noqa: E402


class FakeGardener:
    """Minimalzwilling: nur die zwei Methoden, die _seed_observe_sources nutzt."""

    def __init__(self, existing=None):
        self.sources = dict(existing or {})
        self.added = []

    def observe_source_list(self):
        return dict(self.sources)

    def observe_source_add(self, source_id, kind, **params):
        self.sources[source_id] = {"kind": kind, **params}
        self.added.append(source_id)
        return self.sources[source_id]


def _write_ref(tmp_path, tiers):
    (tmp_path / "sources.reference.json").write_text(
        json.dumps({"schema": "gardener.sources.reference.v1", "tiers": tiers}),
        encoding="utf-8",
    )


@pytest.fixture
def ref_dir(tmp_path, monkeypatch):
    """Laesst _seed_observe_sources die Referenz aus tmp_path lesen."""
    monkeypatch.setattr(seed, "__file__", str(tmp_path / "seed.py"))
    return tmp_path


def test_legt_vorhandene_quelle_an(ref_dir, tmp_path):
    real = tmp_path / "vorhanden"
    real.mkdir()
    _write_ref(ref_dir, {"base": {"da": {"kind": "markdown_dir", "path": str(real)}}})
    g = FakeGardener()
    seed._seed_observe_sources(g)
    assert g.added == ["da"]
    assert g.sources["da"]["kind"] == "markdown_dir"


def test_unterstuetzt_listen_in_pfaden(ref_dir, tmp_path):
    """Quellen mit Pfadlisten werden angelegt, wenn mindestens ein Pfad existiert."""
    real = tmp_path / "vorhanden"
    real.mkdir()
    not_real = tmp_path / "fehlt"
    _write_ref(ref_dir, {"base": {
        "multi": {
            "kind": "agent_transcripts",
            "path": [str(not_real / "*.jsonl"), str(real / "*.jsonl")],
        }
    }})
    g = FakeGardener()
    seed._seed_observe_sources(g)
    assert g.added == ["multi"]
    assert g.sources["multi"]["kind"] == "agent_transcripts"
    assert isinstance(g.sources["multi"]["path"], list)


def test_ueberspringt_fehlende_pfade_ohne_fehler(ref_dir, tmp_path):
    """Der Normalfall auf einem fremden Host -- kein Fehler, kein Eintrag."""
    _write_ref(ref_dir, {"base": {
        "fehlt": {"kind": "markdown_dir", "path": str(tmp_path / "gibt-es-nicht")},
        "fehlt_db": {"kind": "sqlite_table", "db_path": str(tmp_path / "nichts.db"), "table": "t"},
    }})
    g = FakeGardener()
    seed._seed_observe_sources(g)
    assert g.added == []


def test_ueberschreibt_bestehende_konfiguration_nicht(ref_dir, tmp_path):
    real = tmp_path / "vorhanden"
    real.mkdir()
    _write_ref(ref_dir, {"base": {"da": {"kind": "markdown_dir", "path": str(real)}}})
    g = FakeGardener({"da": {"kind": "markdown_dir", "path": "/eigener/pfad"}})
    seed._seed_observe_sources(g)
    assert g.added == []
    assert g.sources["da"]["path"] == "/eigener/pfad"


def test_user_ebene_wird_nicht_automatisch_uebernommen(ref_dir, tmp_path):
    real = tmp_path / "vorhanden"
    real.mkdir()
    _write_ref(ref_dir, {
        "base": {"b": {"kind": "markdown_dir", "path": str(real)}},
        "user": {"u": {"kind": "markdown_dir", "path": str(real)}},
    })
    g = FakeGardener()
    seed._seed_observe_sources(g)
    assert g.added == ["b"], "die user-Ebene ist hostspezifisch und wird von Hand gewaehlt"


def test_fehlende_referenzdatei_bricht_nicht_ab(ref_dir):
    g = FakeGardener()
    seed._seed_observe_sources(g)   # keine sources.reference.json geschrieben
    assert g.added == []


def test_kaputte_referenzdatei_bricht_nicht_ab(ref_dir):
    (ref_dir / "sources.reference.json").write_text("{kein valides json", encoding="utf-8")
    g = FakeGardener()
    seed._seed_observe_sources(g)
    assert g.added == []


# ---------------------------------------------------------------------------
# Freiwilligkeit (T-20260825-329696802): standalone-sichere Defaults + Abschaltbarkeit
# ---------------------------------------------------------------------------

def test_system_ebene_ist_ohne_zustimmung_nicht_default(ref_dir, tmp_path, monkeypatch):
    """'system' setzt ellmos-Infrastruktur voraus und darf nicht automatisch
    mitlaufen, nur weil ein Pfad zufaellig existiert (Standalone-Sicherheit)."""
    monkeypatch.delenv("GARDENER_SEED_ECOSYSTEM_SOURCES", raising=False)
    real = tmp_path / "vorhanden"
    real.mkdir()
    _write_ref(ref_dir, {
        "base": {"b": {"kind": "markdown_dir", "path": str(real)}},
        "system": {"s": {"kind": "markdown_dir", "path": str(real)}},
    })
    g = FakeGardener()
    seed._seed_observe_sources(g)  # kein explizites tiers -> Default-Ableitung
    assert g.added == ["b"], "system-Ebene braucht explizite Zustimmung, kein Default"


def test_system_ebene_mit_ausdruecklicher_zustimmung(ref_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("GARDENER_SEED_ECOSYSTEM_SOURCES", "1")
    real = tmp_path / "vorhanden"
    real.mkdir()
    _write_ref(ref_dir, {
        "base": {"b": {"kind": "markdown_dir", "path": str(real)}},
        "system": {"s": {"kind": "markdown_dir", "path": str(real)}},
    })
    g = FakeGardener()
    seed._seed_observe_sources(g)
    assert set(g.added) == {"b", "s"}


def test_komplett_abschaltbar(ref_dir, tmp_path, monkeypatch):
    """GARDENER_SEED_OBSERVE_SOURCES=0 ueberspringt auch die agentenneutrale
    'base'-Ebene -- volle Freiwilligkeit, nicht nur ein Teil-Opt-out."""
    monkeypatch.setenv("GARDENER_SEED_OBSERVE_SOURCES", "0")
    real = tmp_path / "vorhanden"
    real.mkdir()
    _write_ref(ref_dir, {"base": {"b": {"kind": "markdown_dir", "path": str(real)}}})
    g = FakeGardener()
    seed._seed_observe_sources(g)
    assert g.added == []


def test_voller_abschalter_wirkt_auch_bei_explizitem_tiers(ref_dir, tmp_path, monkeypatch):
    """GARDENER_SEED_OBSERVE_SOURCES=0 ist das staerkste Signal -- es gilt
    UNBEDINGT, auch wenn ein Aufrufer (z.B. ein Test) tiers explizit setzt."""
    monkeypatch.setenv("GARDENER_SEED_OBSERVE_SOURCES", "0")
    real = tmp_path / "vorhanden"
    real.mkdir()
    _write_ref(ref_dir, {"base": {"b": {"kind": "markdown_dir", "path": str(real)}}})
    g = FakeGardener()
    seed._seed_observe_sources(g, tiers=("base",))
    assert g.added == [], "GARDENER_SEED_OBSERVE_SOURCES=0 muss auch bei explizitem tiers wirken"


def test_default_seed_tiers_liest_env(monkeypatch):
    monkeypatch.delenv("GARDENER_SEED_ECOSYSTEM_SOURCES", raising=False)
    assert seed._default_seed_tiers() == ("base",)
    monkeypatch.setenv("GARDENER_SEED_ECOSYSTEM_SOURCES", "1")
    assert seed._default_seed_tiers() == ("base", "system")
    monkeypatch.setenv("GARDENER_SEED_ECOSYSTEM_SOURCES", "0")
    assert seed._default_seed_tiers() == ("base",)


def test_referenzset_enthaelt_das_beschlossene_plans_register():
    reference = Path(seed.__file__).resolve().parent / "sources.reference.json"
    data = json.loads(reference.read_text(encoding="utf-8"))
    plans = data["tiers"]["system"]["plans-register"]

    assert plans == {
        "kind": "markdown_dir",
        "path": "~/OneDrive/.TOPICS/_control-center/_PLANS",
        "patterns": ["README.md", "PLANS-REPORT.md", "plans-register.json"],
        "extra_tags": ["plan", "governance-register"],
    }


def test_referenzset_enthaelt_drei_musketiere_skills():
    reference = Path(seed.__file__).resolve().parent / "sources.reference.json"
    data = json.loads(reference.read_text(encoding="utf-8"))
    base = data["tiers"]["base"]

    assert "claude-skills" in base
    assert base["claude-skills"] == {
        "kind": "markdown_dir",
        "path": "~/.claude/skills/*",
    }

    assert "codex-skills" in base
    assert base["codex-skills"] == {
        "kind": "markdown_dir",
        "path": "~/.codex/skills/*",
    }

    assert "gemini-skills" in base
    assert base["gemini-skills"] == {
        "kind": "markdown_dir",
        "path": [
            "~/.gemini/skills/*",
            "~/.gemini/antigravity/builtin/skills/*",
        ],
    }


def test_apply_reference_sources_list_and_existence(tmp_path):
    import apply_reference_sources

    real_dir = tmp_path / "existiert"
    real_dir.mkdir()
    fake_dir = tmp_path / "existiert_nicht"

    # 1. source_paths mit einzelnen Strings und Listen
    cfg_list = {"path": [str(fake_dir / "*.jsonl"), str(real_dir / "*.jsonl")]}
    paths = apply_reference_sources.source_paths(cfg_list)
    assert len(paths) == 2
    assert str(fake_dir) in paths[0]
    assert str(real_dir) in paths[1]

    # 2. exists liefert True, wenn mindestens ein Pfad existiert
    assert apply_reference_sources.exists(cfg_list) is True

    # 3. exists liefert False, wenn kein Pfad existiert
    cfg_none = {"path": [str(fake_dir / "*.jsonl")]}
    assert apply_reference_sources.exists(cfg_none) is False

    # 4. exists liefert True, wenn gar kein Pfad konfiguriert ist
    assert apply_reference_sources.exists({}) is True
