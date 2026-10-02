# Changelog
 
## [Unreleased]

### FTS5/LIKE Reines Negations-Routing & Wiederholte Inline-Filter Akkumulierung (2026-10-02)

- **Behebung der Negations-Invertierung (`gardener.py`)**:
  - `_build_fts_safe_operator_query`: Behebt Fehler, bei dem reine Negationsqueries (`-draft`, `-draft -temp`) durch Umwandlung führender negierter Tokens in positive FTS-Tokens die Suche invertierten und nur Treffer MIT den ausgeschlossenen Begriffen lieferten. Reine Negationsanfragen liefern nun `None`, damit sie sauber an die LIKE-Ebene delegiert werden.
  - `_build_fts_and_query` & `_build_fts_or_query`: Negations-Guard hinzugefügt, sodass Queries mit Minus-Negation abgewiesen werden (`return None`), anstatt ungültige Tokens wie `"NOT" "draft"` zu erzeugen.
  - `find()`: Schneller Direktpfad für reine Negationssuchen (`has_neg and not safe_op_query`) direkt zu `_like_query()`, wo negative SQL-Bedingungen (`WHERE 1=1 AND (e.name NOT LIKE ? AND e.content NOT LIKE ? AND e.tags NOT LIKE ?)`) mit Typ-, Quell- und Pinned-Filtern ausgeführt werden.
- **Akkumulierung wiederholter Inline-Filter (`gardener.py`)**:
  - `_extract_inline_filters`: Wiederholte `type:`/`typ:`- sowie `source:`/`quelle:`-Filter werden jetzt mit Kommas akkumuliert (`task,tool` bzw. `usmc-working,github`), statt nach dem ersten Token ignoriert zu werden und in den Freitextsuchbegriff zu lecken.
- **Search-GUI & API Parität (`tests/test_search_gui.py`)**:
  - Neuer API-Test `test_api_search_pure_negation_and_repeated_filters`: Verifiziert `/api/search?q=-belege` und `/api/search?q=type:knowledge%20type:memory`.
- **Vertragstests & Metadaten (`tests/test_gardener_core.py`, `tests/test_metadata.py`, `README.md`, `README_de.md`, `llms.txt`)**:
  - Neue Tests `test_find_with_pure_negations_and_inline_filters` und Assertions in `test_find_and_list_multi_type_and_negations_contract`.
  - Testsuite von 225 auf **227 passed, 35 subtests passed** (100% grün) erhöht; Badges und `llms.txt` Stand 2026-10-02 synchronisiert.

### Multi-Type-Filterung & Negations-Suchsyntax (`-term`, `-"phrase"`) (2026-10-01)

- **Multi-Type-Filterung (`gardener.py`)**:
  - `Gardener._normalize_types(type_val)` und `Gardener._type_filter(type_val, column="e.type")` implementiert: Unterstützt kommaseparierte Strings (`"task,knowledge"`, `"typ:task,memo"`) und Listen/Iterables (`["task", "knowledge"]`), die zu parametrisierten `e.type IN (?, ...)` SQL-Klauseln aufgelöst werden.
  - Nahtlos integriert über `_fts_query()`, `_like_query()`, `_source_listing()`, `find()` und `list()`.
  - Type-Hints und Docstrings von `find()` und `list()` auf `Optional[Union[str, List[str]]] = None` aktualisiert.
- **Negations- & Ausschluss-Suchsyntax (`-term`, `-"quoted phrase"`, `-tag:deprecated`) (`gardener.py`)**:
  - `_TOKEN_PATTERN` Regex um Negations-Erkennung `(?P<neg>-(?!-))` erweitert, ohne Bindestrichwörter (`beleg-scanner`), isolierte Bindestriche (`python - c++`) oder CLI-Flags (`--help`) fälschlich als Negation zu erfassen.
  - `_tokenize_query()` liefert FTS5-kompatible Token-Struktur und emittiert `("NOT", False, False)` vor negierten Token.
  - `_build_fts_safe_operator_query()` erkennt Negations-Präfixe, beachtet die SQLite-FTS5-Invariante (strikter binärer `A NOT B` Operator), ordnet führende Negationen um (z. B. `-draft rechnung` -> `"rechnung" NOT "draft"`) und fängt isolierte `NOT`-Token syntaktisch sauber ab.
  - `_like_query()` Fallback-Suche unterstützt Negationen über `(name NOT LIKE ? AND content NOT LIKE ? AND tags NOT LIKE ?)` und behält Browse-Modus und Wildcard-Suchen bei.
- **Search-GUI Anpassung (`search_gui.py`)**:
  - Platzhalter im Suchfeld um Multi-Type- und Negations-Beispiele (`type:task,tool`, `-draft`) ergänzt.
- **Umfassende Vertragstests (`tests/test_gardener_core.py`, `tests/test_metadata.py`)**:
  - Neuer Vertragstest `test_find_and_list_multi_type_and_negations_contract`, erweiterte Assertions in `test_tokenize_query_and_build_fts_and_query_helpers` und `test_find_with_inline_filters_and_column_aliases` (Abschnitte 11, 12, 13).
  - Testsuite auf **225 passed, 35 subtests passed** (100% grün) erhöht; Badges und Metadaten in `README.md`, `README_de.md`, `llms.txt` und `test_metadata.py` synchronisiert.

### Bilingual 18-Point Navigation Parity, ASCII Architecture Topology & Level 1 SBOM Companion (2026-09-30)

- **Level 1 Software Bill of Materials (SBOM) Companion (`THIRD_PARTY_LICENSES.txt`)**:
  - Authored canonical plain-text companion file `THIRD_PARTY_LICENSES.txt` Stand 2026-09-30 with all 10 governance and runtime invariants (`INV-LOCAL-01` to `INV-SLA-10`), `RunAsInvoker` unprivileged execution guarantee, zero runtime dependencies (100% Python Standard Library PSF-2.0), development tooling (pytest, ruff, setuptools), and complete license texts.
  - Linked `THIRD_PARTY_LICENSES.txt` in `NOTICE`, `THIRD_PARTY_LICENSES.md`, `README.md`, `README_de.md`, `llms.txt`, and `pyproject.toml`.
- **ASCII Four-View Architectural Topology Projection (`README.md`, `README_de.md`)**:
  - Embedded high-clarity 4-view ASCII architectural diagrams in Section 2 across both English and German README specifications:
    - View 1: Layered System Topology (User Surfaces -> Orchestration -> Engine & Filter -> Substrate & Storage).
    - View 2: Data Flow & Mutation Isolation (`RunAsInvoker` unprivileged execution boundary, `workspace/` sandbox lifecycle, zero-egress SQLite).
    - View 3: Federated Ingestion vs. Curated Custody (Telescope Observe vs. House Ingestion).
    - View 4: Everything Substrat Dual-Database Physical Layout (`gardener.db` system blueprints vs. `user.db` userland state).
- **Bilingual 18-Point Direct Anchor Navigation Parity**:
  - Standardized explicit HTML target anchors `<a id="sec-01">` through `<a id="sec-18">` across all 18 numbered sections in both `README.md` and `README_de.md`.
  - Harmonized Quick Navigation overview tables with direct anchor links (`[#sec-01](#sec-01)` .. `[#sec-18](#sec-18)`).
- **PEP 621 Metadata & GitHub Discoverability Standardization (`pyproject.toml`)**:
  - Added `THIRD_PARTY_LICENSES.txt` to `project.license-files`.
  - Saturated `keywords` to 20 canonical topics aligning 1:1 with GitHub remote topics.
  - Added `[project.urls]` entries for `"Level 1 SBOM"`, `"Third-Party Licenses (Text)"`, and `"Plain-Text License"`.
- **Contract Tests**:
  - Added assertions in `tests/test_metadata.py` verifying bilingual 18-point anchor parity (`sec-01` .. `sec-18`), ASCII topology projections, Level 1 SBOM invariants, and PEP 621 URL/keyword alignment.
  - Test suite expanded to **224 passed, 35 subtests passed** (100% green); badges and metadata synchronized.

### Deutsche Filter-Aliase, Inline Limit-Parsing & Search-GUI-Härtung (2026-09-29)

- **Deutsche Filter-Aliase & `limit:` / `max:` Inline-Parsing (`gardener.py`)**:
  - `_FILTER_TOKEN_RE` und `_extract_inline_filters()` um deutsche Aliase erweitert: `typ:` (Alias für `type:`), `quelle:` (Alias für `source:`), `gepinnt:` (Alias für `pinned:` mit `ja/true/1` bzw. `nein/false/0`), `ist:gepinnt` und `nicht:gepinnt`.
  - Inline `limit:<Zahl>` und `max:<Zahl>` Parsing implementiert: Ermöglicht z. B. `find("backup limit:5")` oder `find("typ:task limit:3")`. Extrahiert das Limit, bereinigt den Suchstring und setzt das Limit in `find()`, falls nicht explizit anders übergeben.
  - Ermöglicht nahtlose kombinierte Abfragen wie `find("typ:tool quelle:usmc-working ist:gepinnt limit:5 backup")`.
- **Search-GUI Erweiterung & Härtung (`search_gui.py`)**:
  - `/api/search` um `source`-Parameter erweitert: Reicht `source` an `gardener.find(..., source=source_filter)` durch.
  - Browse-Modus bei leerem Suchbegriff: Wenn `type`, `source` oder `pinned` gesetzt sind, führt `/api/search` die gefilterte Suche auch ohne Freitextbegriff aus, statt sofort ein leeres Array zurückzugeben.
  - HTML & Frontend-Erweiterung: Neues `<select id="pinned">`-Dropdown (`alle Status`, `nur gepinnt`, `ungepinnt`) in der Suchleiste integriert und im JavaScript an die Such-API angebunden.
  - Suchfeld-Platzhalter um nützliche Beispiele für Inline-Filter (`z. B. type:task, tag:python, is:pinned, limit:10`) ergänzt.
- **Tests & Parität**:
  - Neue Vertragstests `test_api_search_empty_query_browse_mode`, `test_api_search_source_filter` und `test_api_search_inline_filters_in_gui` in `tests/test_search_gui.py`.
  - Erweiterte Assertions für deutsche Filter-Aliase und Inline-Limits in `tests/test_gardener_core.py`.
  - Testsuite-Vollständigkeit auf **222 passed, 35 subtests passed** (100% grün) erhöht; Badges und Metadaten synchronisiert.

### Federated Ingestion & Custody Architecture Parity (2026-09-29)

- **Comprehensive Bilingual Documentation of Federated observe_source Architecture (`DESIGN.md`, `KONZEPT.md`)**:
  - Documented the architectural evolution from local single-directory observation to the cross-source federated index substrate across multi-agent environments.
  - Formally specified the four adapter kinds (`markdown_dir`, `remember_files`, `sqlite_table`, `agent_transcripts`) and streaming byte-offset mechanics for multi-gigabyte JSONL chat transcripts (`claude_code`, `gemini_antigravity`, `codex`, `kimi`).
  - Added the definitive comparison between **Curated Custody** (`absorb()`, physical ingestion into the house, `.absorber/` mailbox model, lifecycle decay & pruning) and **Federated Ingestion** (`observe()` / `observe_source`, read-only non-intrusive lens, telescope model, `source_ref` back-citations).
  - Updated architectural open questions, marking cross-source adapters and workspace management as resolved.
- **Bilingual Documentation Parity Contract Test (`tests/test_metadata.py`)**:
  - Added `test_bilingual_architecture_docs_parity` asserting existence, reciprocal links, adapter definitions, provenance metadata, query scoping, and custody distinction across `DESIGN.md` and `KONZEPT.md`.
  - Expanded test suite from 218 to 219 passing tests (35 subtests, 100% green).
  - Synchronized `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py`.

### Core Paths Contract Tests (2026-09-29)

- **Comprehensive Core Engine Contract Tests (`TestCorePathsContract` in `tests/test_gardener_core.py`)**:
  - Implemented 8 dedicated contract tests covering all fundamental lifecycle operations:
    - `absorb()`: Verified all 3 storage levels (inline for text <= 1MB, blob storage for binary/1MB-50MB, and halde storage for > 50MB) with correct metadata tagging (`meta["storage"]`, `blob_path`, `blob_hash`).
    - `materialize()`: Verified restoration of inline documents and blob/halde binaries to destination paths with safe filenames, as well as `None` handling for missing records.
    - `sync()`: Verified `selective` mode (clears absorber, unlinks absorbed files, observes home without unlinking) and `always_absorb` mode (absorbs and unlinks home files); verified error handling resilience when bad absorber files fail to absorb (logs to `sync-error/...` memory entry without crashing sync loop).
    - `consolidate()`: Verified decay arithmetic (`weight * decay_rate`), automatic pruning/forgetting of entries with weight < 0.05, keeping entries, preserving pinned entries, and returning accurate execution statistics (`decayed`, `forgotten`, `kept`).
    - `recall()`: Verified retrieval boosting, ensuring accessed count increments, weight increases, and `last_accessed` is recorded.
    - `delete()`: Verified deleting entries from `user.db` and attached `system.db` with boolean confirmation and clean removal, as well as `False` return on missing entries.
    - `list()`: Verified filtering by `type`, result limits, and ordering by `updated DESC`.
- **Test Suite & Parity**:
  - Expanded test suite from 210 to 218 passing tests (35 subtests, 100% green).
  - Synchronized `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py`.

### Internationalization Tier-2 Complete Catalogs (2026-09-29)

- **Comprehensive 6-Language Coverage (`locales/translations.json`)**:
  - Populated complete translations for all 57 keys across all declared languages (`de`, `en`, `es`, `zh`, `ja`, `ru`), eliminating empty placeholder values and fallback reliance for Spanish, Chinese, Japanese, and Russian CLI consumers.
- **Contract Test & Metadata Parity (`tests/test_gardener_core.py`, `tests/test_metadata.py`)**:
  - Added `test_translations_catalog_completeness` contract test asserting 100% non-empty values across all declared languages in `locales/translations.json`.
  - Updated measured test suite to 210 passed tests across `README.md`, `README_de.md`, `llms.txt`, and metadata contract tests.

### Documentation & Roadmap Parity (2026-09-29)

- **Repository Layout & Local Storage Documentation**:
  - Aligned repository directory trees in both canonical English (`README.md`) and German (`README_de.md`) documentation: `workspace/` and `blobs/` correctly moved to the `~/.gardener/` local storage section, reflecting that runtime sandboxes and large binary blobs reside exclusively in user data storage rather than repository checkouts.
- **Roadmap Synchronization (`ROADMAP.md` & `ROADMAP_de.md`)**:
  - Synchronized release versions and dates to `v0.4.2` (Stand 2026-09-29).
  - Recorded recent architectural milestones and decisions: atomic upsert in `put()` (SQLite >= 3.24), FTS5 query tokenization & safe operator sanitization, inline query filters (`type:`, `source:`, `is:pinned`/`not:pinned`), natural column aliases (`tag:`, `title:`, `body:`), and in-place directory pruning with 10MB text limits.

### Configurable Observe/Sync Excludes Directory Pruning & Size Limit (2026-09-29)

- **In-place Directory Pruning in Observe / Sync (`Gardener._iter_files_to_observe`)**:
  - Introduced `_iter_files_to_observe(directory)` replacing naive `rglob("*")` tree walks with in-place subdirectory pruning via `os.walk`.
  - Excluded subtrees (`node_modules`, `.git`, `.gardener`, `.absorber`, `.output`, or custom `exclude_patterns` such as `build/*`, `cache/`) are pruned immediately at the directory level, preventing expensive deep filesystem traversals on large project trees or cloud-synced folders.
- **Configurable `max_file_size` Text Limit in `observe()` and `sync()`**:
  - Added configurable `max_file_size` (default: `10_000_000` / 10MB, `DEFAULT_MAX_FILE_SIZE`).
  - Text files exceeding the size limit avoid loading massive payloads into memory or SQLite FTS5 index; instead, a clean placeholder `[Datei überschreitet Größenlimit: <size> Bytes > <max_size> Bytes]` is indexed while retaining accurate file metadata (`path`, `size`, `modified`).
- **Tests & Parity**:
  - Added `test_observe_and_sync_directory_pruning` and `test_observe_and_sync_file_size_limit_and_custom_config` in `tests/test_gardener_core.py`.
  - Metadata, badges, and documentation updated to 209 passing tests (100% green).

### Atomic Upsert in `put()` (2026-09-28)

- **Atomic SQLite Upsert (`Gardener.put` in `gardener.py`)**:
  - Replaced non-atomic `SELECT`-then-`INSERT`/`UPDATE` pattern with single atomic `INSERT INTO ... ON CONFLICT(name) DO UPDATE SET ...` statement (SQLite >= 3.24).
  - Eliminates TOCTOU race conditions where concurrent writers attempting to write the same entry name could fail with an unhandled `sqlite3.IntegrityError`.
  - Preserves original `created` timestamp while cleanly updating `content`, `type`, `tags`, `meta`, `pinned`, and `updated`.
  - Seamlessly triggers SQLite `everything_au` update trigger for full FTS5 index consistency.
- **Tests & Verification**:
  - Added `test_put_atomic_upsert_preserves_created_and_updates_content` to `tests/test_gardener_core.py`.
### FTS5 Inline-Filter & Spalten-Aliase UX (2026-09-28)

- **Inline-Filter in Suchanfragen (`_extract_inline_filters`, `find()` in `gardener.py`)**:
  - Unterstützt direkte Angabe von `type:<typ>` (z. B. `type:task`, `type:tool`) und `source:<id>` (z. B. `source:usmc-working`) direkt im Suchstring.
  - Unterstützt Pinned-Filter direkt in der Query: `is:pinned`, `not:pinned`, `pinned:1`, `pinned:0`, `pinned:true`, `pinned:false`.
  - Filter außerhalb von Anführungszeichen werden sauber extrahiert und auf SQL-Ebene als präzise Filterbedingungen angewendet, während bereinigte Suchbegriffe an die FTS5-Engine übergeben werden.
  - Quotierte Vorkommen wie `"type:task in doc"` bleiben als wörtliche Phrasen erhalten und werden nicht versehentlich als Filter interpretiert.
  - Vollständige Toleranz: Nach dem Entfernen führender oder nachlaufender Operatoren (`type:task AND rechnung` -> `rechnung`) bleibt die Abfragesyntax fehlerfrei.
  - Reines Filter-Listing: Anfragen wie `find("type:task")` ohne zusätzlichen Suchtext listen direkt alle passenden Einträge ohne fehlerhafte FTS5-Leermatches auf.
- **FTS5 Spalten-Aliase (`COLUMN_ALIASES`, `_split_col`, `_tokenize_query`)**:
  - Aliase für natürliche Suche eingeführt: `tag:` -> `tags:`, `title:` -> `name:`, `body:` -> `content:`.
  - Vollständige FTS5-Kompatibilität bei Bindestrich-Werten (z. B. `tag:python-script` -> `tags:"python-script"`), Phrasen und logischen Verknüpfungen (z. B. `(tag:python OR tag:rust) AND title:scanner`).
- **Tests & Parität**:
  - Neue Vertragstests `test_find_with_inline_filters_and_column_aliases` und erweiterte Tokenizer-/Builder-Assertions in `tests/test_gardener_core.py`.
  - Badges und Metadaten auf 206 passed aktualisiert.

### Sleep Stats `uebersprungen` List Type Fix (2026-09-28)

- **Consistent `stats["uebersprungen"]` list semantics (`sleep_union.py` `sleep()`)**:
  - Fixed the three `if_due` skip paths (`decay_config_unavailable`, `auto_cleanup_disabled`, `not_due`) that overwrote the `uebersprungen` list with a plain string, destroying the previously appended `decay_config missing required columns` message and breaking list consumers.
  - Skip reasons now accumulate via `.append(...)` on the initial `[]`, so `uebersprungen` is always a list across all code paths.
- **CLI skip reporting (`gardener.py` sleep handler)**:
  - Normalized `uebersprungen` defensively (`isinstance(str)` check) and joined multiple skip reasons with `", "` in the `sleep.skipped` output line; agents without skips keep the plain TTL/deactivated/decayed summary line.
- **Tests (`tests/test_sleep_union.py`)**:
  - Updated the `auto_cleanup_disabled` and `not_due` assertions to expect list values, matching the always-list `uebersprungen` stats key.

### Union memory soft sleep (2026-09-27)

- Added `gardener sleep --db` for Union v2 databases with a TTL grace pass, optional confidence decay, due gating, dry-run, per-agent TOML TTL overrides, and JSONL reports. No records are deleted; BACH callers can disable decay with `--no-decay`.

### Recall Multi-Word Query UX, FTS5 Safe-Operator Alignment & Observed-Awareness (2026-09-28)

- **FTS5 Multi-Word & Safe-Operator Recall Hardening (`Gardener.recall`)**:
  - Aligned `recall()` with `find()`'s multi-stage query architecture: Exact MATCH -> Safe Operator (`_build_fts_safe_operator_query`) -> Safe AND (`_build_fts_and_query`) -> Multi-word OR Fallback (`_build_fts_or_query`) -> Tokenized LIKE Fallback.
  - Consolidated single-pass retrieval across target types via `WHERE everything_fts MATCH ? AND e.type IN (...)` within `@contextmanager connection("user")`, eliminating redundant queries and ensuring safe connection lifecycles.
  - Targeted score boost: `self._boost(conn, item["id"])` is strictly limited to recalled items belonging to memory types (`memory`, `lesson`, `session`), preventing unwanted boosts on observed sources.
- **Observed-Awareness & Parameter Expansion (`include_observed`, CLI `gardener recall`)**:
  - Added optional parameter `include_observed: bool = False` to `Gardener.recall()` and exposed via `--include-observed` / `-o` in CLI `main()`.
  - Added intelligent observed-awareness hint in CLI `recall`: If 0 memory hits are returned, but hits exist in other observed types or external sources via `find()`, the user receives a helpful tip: `(Hinweis: X Treffer in anderen Quellen/Typen vorhanden — nutze 'gardener find')`.
- **Automated Test Suite Expansion & Badge Parity**:
  - Added 3 unit tests in `tests/test_gardener_core.py`: `test_recall_multi_word_query_ux_or_fallback_and_ranking`, `test_recall_include_observed_parameter`, and `test_cli_recall_observed_awareness_hint`.
  - Synchronized test badges and assertions across `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py` to 206 passing tests (100% green).

### FTS5 Grouping Parentheses & Normalized Boolean Operators (2026-09-26)

- **FTS5 Grouping Parentheses Precision (`_pad_parens_outside_quotes`, `_build_fts_safe_operator_query`, `Gardener.find`)**:
  - Implemented parenthesis grouping support for FTS5 queries (`(term1 OR term2) AND term3` or `term1 AND (term2 OR term3)`), preserving operator precedence without dropping or mangling parentheses into quoted word strings.
  - Automatically isolates unquoted parentheses outside double quotes via `_pad_parens_outside_quotes` and ensures column-filtered tokens inside groups (e.g. `(tags:python-script OR tags:rust-crate) AND backend`) retain their column prefix mapping.
  - Tolerantly balances unclosed parentheses (e.g. `((beleg-scanner OR quittung) AND 2026` -> `(("beleg-scanner" OR "quittung") AND "2026")`) and safely discards orphan closing or empty parentheses without FTS5 syntax crashes.
- **Operator Case-Insensitivity & German Synonym Normalization (`OPERATOR_MAP`)**:
  - Normalized boolean operators across case variants (`and`, `or`, `not`) and German equivalents (`und` -> `AND`, `oder` -> `OR`, `nicht` -> `NOT`) to standard uppercase SQLite FTS5 operators.
  - Prioritized `safe_op_query` evaluation in `Gardener.find()` when boolean operators or grouping syntax are present, preventing lowercase words from being misprocessed as literal text matching terms.
- **LIKE Fallback Cleanups (`_like_query`)**:
  - Stripped structural parentheses and boolean operator keywords from token lists during secondary LIKE fallback queries to eliminate spurious substring matches.
- **Automated Test Suite Expansion & Badge Parity**:
  - Added unit test method `test_find_with_grouping_parentheses_and_normalized_operators` and token/query builder assertions in `tests/test_gardener_core.py`.
  - Synchronized badges and assertions across `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py` to 189 passing tests (100% green).

### Pfad A: Repository Hygiene, CI Matrix Hardening, Multi-Host Defense & Contract Tests (2026-09-26)

- **Canonical Root Attribution (`NOTICE`, `pyproject.toml`, `THIRD_PARTY_LICENSES.md`)**:
  - Established canonical root `NOTICE` file documenting copyright attribution to Lukas Geiger, the ellmos-ai family, and the open-bricks open-source umbrella.
  - Registered `Notice` URL in `[project.urls]` and added `NOTICE` to `license-files` in `pyproject.toml`.
  - Re-audited `THIRD_PARTY_LICENSES.md` (Audit Date: 2026-09-26) with explicit cross-reference to `NOTICE`.
- **CI Matrix & Workflow Hardening (`.github/workflows/*.yml`)**:
  - Hardened `.github/workflows/auto-assign.yml` with `timeout-minutes: 5`, concurrency control (`cancel-in-progress: true`), and explicit permissions (`pull-requests: write`, `issues: write`).
  - Hardened `.github/workflows/label-sync.yml` with `timeout-minutes: 5` and concurrency control (`cancel-in-progress: true`).
  - Added editable package installation check (`pip install -e .`) in `.github/workflows/ci.yml` dependencies step to guarantee package metadata and CLI entrypoint integrity on all operating systems (Ubuntu, Windows, macOS) across Python 3.10-3.13.
- **Multi-Host Cloud-Sync & Defensive Ignore Hardening (`.gitignore`)**:
  - Added multi-host tokens and conflict protection patterns (`*-WORKSTATION-LG*`, `*-ASUS-GEI*`, `*-MacBook*`, `*-IDEAPAD*`, `*_WORKSTATION*`, `*_WORKSTATION-LG*`, `*-WORKSTATION.*`, `*-WORKSTATION-LG.*`).
  - Hardened lock-system defense patterns (`LOCK.user.*`, `LOCK.until.*`, `LOCK.condition.*`, `LOCK.permissions.json`, `.automation-lock`).
  - Added test runner temporary directories (`.pytest_temp/`, `.pytest_tmp*/`, `.tox/`) and OS/editor artifacts (`.DS_Store`, `Thumbs.db`, `ehthumbs.db`, `Desktop.ini`, `*.swp`, `*.swo`).
- **PEP 621 Standard URLs & Ruff Linter Expansion (`pyproject.toml`)**:
  - Enriched `[project.urls]` with `"Bug Tracker"` and `"Source Code"` alongside `Issues` and `Repository` for comprehensive PEP 621 tooling compatibility.
  - Hardened `[tool.pytest.ini_options]` with `addopts = "-ra -v --basetemp=.pytest_temp"` and `norecursedirs` for `.pytest_temp` and `.hypothesis`.
  - Expanded Ruff linter ruleset `[tool.ruff.lint]` with `"SIM"` (`select = ["E", "F", "W", "I", "B", "C4", "SIM"]`).
  - Strict version freeze discipline per T-20260920-167562623 maintained: `version = "0.4.2"` preserved unchanged.
- **Pythonic Code Cleanups & CLI Flags (`gardener.py`, `sources.py`, `tests/test_gardener_core.py`)**:
  - Upgraded `gardener.py` CLI argument parsing to handle standard help flags (`-h`, `--help`, `help`) cleanly without triggering unknown command errors.
  - Refactored `try-except-pass` in `gardener.py:1839` to `contextlib.suppress(sqlite3.Error)`.
  - Refactored nested `if` statements in `sources.py:582` and `sources.py:660` to single combined expressions and modernized ternary assignment.
  - Modernized nested `with` statements in `tests/test_gardener_core.py:1492`.
- **Automated Contract Test Suite Expansion (`tests/test_metadata.py`)**:
  - Added contract tests verifying `NOTICE` presence and attribution, multi-host `.gitignore` patterns, workflow concurrency/timeouts across all 5 workflows, PEP 621 URLs, Ruff SIM rules, and CLI help flag invocations.

### FTS5 Column-Filtered Query Parsing & Hyphen Hardening (2026-09-22)

- **Column-Aware FTS5 & LIKE Search UX (`_tokenize_query`, `_split_col`, `_format_fts_token`, `_like_query`)**:
  - Implemented column prefix awareness for FTS5 indexed columns (`name`, `content`, `tags`) in `_tokenize_query` while distinguishing them from Windows drive letters (`C:\...`).
  - Formats column-filtered tokens safely as `col:"<val>"` (e.g. `tags:python-script` -> `tags:"python-script"`), eliminating SQLite FTS5 column subtraction syntax errors (`no such column: script`) when searching hyphenated tags or names.
  - Supports quoted phrases in column filters (e.g. `tags:"machine learning"`), prefix wildcards (`tags:scan*`), boolean operator combinations (`tags:python-script AND name:beleg-1`, `tags:python NOT tags:legacy`), and tolerant spacing after colons.
  - Upgraded `_like_query` fallback to direct targeted column searches (`WHERE e.col LIKE ?`) when column filters are present in single-term or multi-term queries.
- **Automated Test Suite Expansion & Badge Parity**:
  - Added unit test methods `test_find_with_column_filters_and_hyphenated_values` and `test_like_query_with_column_filters`, plus expanded helper assertions in `tests/test_gardener_core.py`.
  - Synchronized badges and assertions across `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py` to 183 passing tests (100% green).

### FTS5 Compound Boolean Operators Normalization & Negation UX (2026-09-21)

- **FTS5 Compound Boolean Operator Consolidation (`_build_fts_safe_operator_query`, `Gardener.find`)**:
  - Upgraded `_build_fts_safe_operator_query` with state-machine token stream consolidation for user-entered boolean queries.
  - Consolidates compound boolean sequences like `AND NOT` or `OR NOT` into SQLite FTS5's required binary `NOT` syntax (`<term1> NOT <term2>`), preventing `sqlite3.OperationalError: fts5: syntax error near "NOT"`.
  - Normalizes consecutive repeated operators (e.g. `AND AND`, `OR OR`, `AND OR`) by deduplication and picking the last logical combinator, preventing `syntax error near "AND"` / `"OR"`.
  - Safely handles unary leading `NOT` (e.g. `NOT banana` -> `"banana"`) and trailing hanging operators without syntax errors.
- **Automated Test Suite Expansion & Badge Parity**:
  - Added unit test method `test_find_with_compound_boolean_operators_and_negation` and query builder assertions in `tests/test_gardener_core.py`.
  - Synchronized badges and assertions across `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py` to 181 passing tests (100% green).

### FTS5 Boolean Operator Precision Hardening & Three Musketeers Skills Federation (2026-09-20)

- **FTS5 Boolean Operator Query Hardening (`_build_fts_safe_operator_query`, `Gardener.find`)**:
  - Implemented `_build_fts_safe_operator_query` to preserve explicit boolean operators (`AND`, `OR`, `NOT`) while safely quoting and escaping operand terms.
  - Resolves FTS5 syntax errors where unquoted terms containing hyphens, colons, slashes, or special symbols (e.g. `beleg-scanner AND rechnung`, `c++ OR c#`, `rechnung NOT beleg-scanner`, `beleg-scan* AND rechnung`) caused SQLite to abort FTS matching (`no such column: scanner`) and fall back to LIKE OR-matching, restoring strict boolean precision, BM25 ranking, and highlighted snippets.
- **FTS5 Asterisk-Only Token Crash Guard (`_tokenize_query`)**:
  - Filtered out bare tokens consisting solely of asterisks (`*`, `**`, `***`) to prevent SQLite FTS5 from raising `OperationalError: unknown special query: **`.
- **Three Musketeers Skills Federation (`sources.reference.json`, `seed.py`)**:
  - Registered `codex-skills` (`~/.codex/skills/*`) and `gemini-skills` (`["~/.gemini/skills/*", "~/.gemini/antigravity/builtin/skills/*"]`) under `tiers.base` in `sources.reference.json`.
  - Completes cross-source skill observation across the Three Musketeers (Claude, Codex, Gemini) and the central skills library.
- **Automated Test Suite Expansion & Badge Parity**:
  - Added unit tests `test_find_with_boolean_operators_and_special_chars` in `tests/test_gardener_core.py` and `test_referenzset_enthaelt_drei_musketiere_skills` in `tests/test_seed_observe_sources.py`.
  - Updated all badges and contract assertions across `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py` to 180 passing tests (100% green).

### Pfad B: Marketing, Discoverability, Visual Architecture & License Transparency (2026-09-18)

- **18-Point Quick Navigation Parity & Reciprocal Anchor Matrix (`README.md`, `README_de.md`)**:
  - Upgraded Quick Navigation in English and German to 18 numbered sections with reciprocal dual HTML anchor tags (`<a id="..."></a>`).
  - Guaranteed 100% interoperability between English jump links (`#1-features`..`#18-security-policy-sibling-ecosystem--liability`), German jump links (`#1-funktionen`..`#18-sicherheitsrichtlinie-geschwister-oekosystem--haftung`), and legacy anchor targets.
- **Target Personas & Discoverability Query Matrix (`[PERSONA-01]`..`[PERSONA-04]`, `README.md`, `README_de.md`, `llms.txt`)**:
  - Formalized 4 core target personas: Local-First AI Agent Engineers, Privacy-First Researchers & Knowledge Workers, Multi-Agent Fleet Architects, and SQLite & Local-Tool Enthusiasts.
  - Curated high-intent search query matrix for SQLite-based LLM operating systems and deterministic FTS5 memory substrates.
- **10-Dimension Comparative Matrix vs. 4 Alternatives (`README.md`, `README_de.md`)**:
  - Benchmarked Gardener OS against MemGPT/Letta, LangChain/LlamaIndex SQLite, ChromaDB/Pinecone, and Traditional OS Filesystem + Grep across 10 architectural dimensions mapped 1:1 to invariants (`INV-LOCAL-01` to `INV-SLA-10`).
- **Software Inventory & License Transparency Audit (`THIRD_PARTY_LICENSES.md`, `pyproject.toml`)**:
  - Published comprehensive SPDX-compliant software bill of materials (SBOM).
  - Certified zero external runtime dependencies (100% Python standard library).
  - Formally certified `RunAsInvoker` unprivileged user-mode execution and Zero-Copyleft isolation.
  - Enriched `pyproject.toml` with `"Third-Party Licenses"`, `"Umbrella Ecosystem"`, and `license-files = ["LICENSE", "THIRD_PARTY_LICENSES.md"]`.
- **German Statutory Liability Limitation (`README_de.md`)**:
  - Integrated statutory disclaimer according to § 521 BGB (Gefälligkeitsrecht) limiting liability to intent and gross negligence.
- **Automated Contract Test Suite Expansion (`tests/test_metadata.py`)**:
  - Added rigorous automated contract tests verifying 18-point quick navigation parity, personas, comparative matrix, `THIRD_PARTY_LICENSES.md` integrity, and § 521 BGB statutory disclaimer.

### Search Pinning Filter, SQL-Level Priority Promotion & Multi-Path Reference Seeding (2026-09-16)

- **Search Pinning Filter & SQL WHERE Clause (`Gardener.find`, `_fts_query`, `_like_query`, `_source_listing`)**:
  - Added `pinned: Optional[bool] = None` filter parameter to `Gardener.find()`, `_fts_query()`, `_like_query()`, and `_source_listing()`.
  - When `pinned=True` or `pinned=False`, an explicit `WHERE` constraint (`AND e.pinned = ?`) is applied across both system and user SQLite databases prior to query evaluation and limit truncation.
- **SQL-Level Ranking Prioritization (`ORDER BY e.pinned DESC, rank LIMIT ?`)**:
  - Hardened FTS5 and LIKE queries to sort by `e.pinned DESC` before applying `LIMIT ?` directly in SQLite. This ensures pinned items are never cut off by BM25 rank thresholds when match volumes exceed the page limit.
- **CLI & Web GUI Pin Filter Integration (`gardener find --pinned`, `search_gui.py`)**:
  - Added `--pinned`, `--no-pinned`, and `--unpinned` CLI arguments to `gardener find`. Displayed `[PIN]` badge in CLI query results for pinned entries.
  - Added `pinned` query parameter support (`pinned=1` / `pinned=0`) to the HTTP search endpoint `/api/search` in `search_gui.py`.
  - Added bilingual help text (`help.find_pinned`) to `i18n.py` and `locales/translations.json`.
- **Multi-Path Observe Source Seeding in CLI Tool (`apply_reference_sources.py`)**:
  - Fixed path resolution and existence checks in `apply_reference_sources.py`: properly unpacks multi-path list/tuple definitions (e.g. `codex-sessions`) and verifies existence with `any()`.
- **Test Suite Expansion & Badges (`tests/test_gardener_core.py`, `tests/test_search_gui.py`, `tests/test_seed_observe_sources.py`, `tests/test_metadata.py`)**:
  - Added 4 unit tests (`test_find_with_pinned_filter`, `test_find_pinned_cli`, `test_api_search_pinned_filter`, `test_apply_reference_sources_list_and_existence`).
  - Updated all badges and contract assertions across `README.md`, `README_de.md`, `llms.txt`, and `test_metadata.py` to 174 passing tests (100% green).

### Technical Hygiene, CI Matrix Hardening & Multi-Host Defense (2026-09-16)

- **CI Workflow Guardrails & Runaway Defense (`.github/workflows/ci.yml`, `stale.yml`, `welcome.yml`)**:
  - Added explicit `timeout-minutes: 15` runaway protection across all 12 matrix jobs in `ci.yml`. Standardized test runner execution to `python -m pytest -ra -v` under UTF-8 encoding.
  - Added `timeout-minutes: 10` and concurrency cancellation (`cancel-in-progress: true`) to `stale.yml`.
  - Added `timeout-minutes: 5` and concurrency cancellation (`cancel-in-progress: true`) to `welcome.yml`.
- **Multi-Host Sync Conflict & Canonical Lock Defense (`.gitignore`)**:
  - Enforced full coverage for multi-host conflict files (`* (copy)*`, `* (Copy)*`, `* (kopie)*`, `* (Kopie)*`, `*conflicted copy*`, `*-WORKSTATION*`, `*-ASUS*`, `*-LAPTOP*`, `*-Mac Studio*`, `*.sync-temp-*`).
  - Hardened lock isolation against accidental lock commits (`LOCK`, `LOCK*.txt`, `LOCK.*`, `*.lock`, `uv.lock`, with explicit unignore for `!package-lock.json`).
  - Added hygiene masks for merge residue (`*.orig`, `*.rej`) and coverage/test caches (`.coverage.*`, `.hypothesis/`, `.turbo/`, `.nyc_output/`, `wheelhouse/`, `.wheel-smoke/`).
- **PEP 621 Metadata Alignment & Ruff Expansion (`pyproject.toml`, `gardener.py`)**:
  - Enriched `[project.urls]` with `"LLM Ready"` and `"Marketing Log"`.
  - Added standard pytest configuration with `addopts = "-ra -v"`, `minversion = "7.0"`, and `norecursedirs`.
  - Expanded Ruff linter rules to include flake8-bugbear (`B`) and flake8-comprehensions (`C4`), resolving unused loop variables in FTS tokenizers and direct attribute access.
- **Contract Test Suite Expansion (`tests/test_metadata.py`)**:
  - Extended metadata contract tests to verify CI timeouts and concurrency, multi-host and lock defense gitignore patterns, and PEP 621 extended project URLs.

### Phrase-Aware Multi-Word FTS5/LIKE Fallback & Multi-Path Source Seeding (2026-09-13)

- **Phrase-Aware Multi-Word FTS5 OR Query (`Gardener._build_fts_or_query`)**: Upgraded `_build_fts_or_query` from a naive whitespace split to `cls._tokenize_query()`. Mixed queries combining quoted phrases and terms (e.g. `'"beleg-scanner" rechnung'`), prefix wildcards, and hyphenated terms now preserve quoted phrases intact and correctly fall back to FTS5 BM25-ranked OR searches when exact AND matches yield 0 results. Single phrases (e.g. `'"Registry Mitgliedschaft"'`) continue to be preserved as exact units rather than split into OR terms.
- **LIKE Fallback Token Hygiene (`Gardener._like_query`)**: Cleaned token extraction for secondary LIKE fallback using `_tokenize_query()` instead of raw string splitting, ensuring stripped keywords without surrounding double quotes are queried against `name`, `content`, and `tags`.
- **Multi-Path Observe Source Seeding (`seed._seed_observe_sources`)**: Fixed a path resolution bug where multi-path observe sources configured with a list/tuple of patterns (such as `codex-sessions`) were incorrectly converted into string representations (`"['path1', 'path2']"`). Added safe unpacking and `any()` existence checks so multi-location sources are properly registered when at least one candidate directory exists on the host.
- **Transcript Reference Catalog Parity (`sources.reference.json`)**:
  - `gemini-transcripts`: Added multi-path support covering both IDE brain sessions (`~/.gemini/antigravity/brain/*/.../transcript.jsonl`) and CLI brain sessions (`~/.gemini/antigravity-cli/brain/*/.../transcript.jsonl`).
  - `gemini-archive`: Added support for Antigravity's archive naming pattern (`~/.gemini/antigravity/brain_history_older_than_*.zip`) alongside legacy `conversations_archive/*.zip`.
- **Test Suite & Metadata Expansion**: Added 2 unit tests (`test_multiword_phrase_or_fallback_and_like_clean_tokens` in `test_gardener_core.py`, `test_unterstuetzt_listen_in_pfaden` in `test_seed_observe_sources.py`), expanding test coverage to 168 passing tests (100% green).


### Multi-Agent Prompt History & Transcript Noise Reduction (2026-09-12)

- **Claude Code Prompt History Support (`_extract_claude_code_text`)**: Extended Claude Code transcript adapter to recognize and index flat prompt history (`~/.claude/history.jsonl` with `display`, `sessionId`, `project`, `timestamp`), indexing human inputs as user turns with session and line provenance.
- **Gemini Antigravity CLI Prompt History (`_extract_gemini_antigravity_text`)**: Added native recognition for Antigravity CLI prompt history (`~/.gemini/antigravity-cli/history.jsonl` with `display`, `workspace`, `conversationId`, `timestamp`), indexing CLI prompts under role `user` and mapping `conversationId` to session ID.
- **Antigravity Transcript Noise Filtering**: Hardened `PLANNER_RESPONSE` turn extraction to index assistant turns only when user-facing prose (`content`) is present. Tool execution action logs, intermediate steps, and internal chain-of-thought reasoning (`thinking`) are cleanly skipped, maintaining strict noise parity with Claude Code and Kimi adapters.
- **Session ID Extraction Hardening (`_transcript_item`)**: Added `conversationId` resolution in `_transcript_item` session extraction (`entry.get("sessionId") or entry.get("session_id") or entry.get("conversationId")`), ensuring correct session provenance for Gemini Antigravity sessions and history lines.
- **Reference Catalog Extension (`sources.reference.json`)**: Added `claude-history` (`~/.claude/history.jsonl`) and `gemini-history` (`~/.gemini/antigravity-cli/history.jsonl`) to `tiers.base`, making prompt histories standard discoverable observe sources across all systems.
- **Test Suite & Metadata Expansion**: Added 3 unit tests (`test_claude_code_history_format`, `test_gemini_antigravity_history_format`, `test_gemini_antigravity_skips_intermediate_thinking_and_tool_steps`), bringing total test coverage to 166 passing tests (100% green).

### SQLite Connection Lifecycle, Context Manager Hardening & Concurrency Protection (2026-09-11)

- **Connection Context Manager (`Gardener.connection()`)**: Implemented `@contextlib.contextmanager` yielding managed SQLite connections with guaranteed cleanup (`conn.close()`) in `finally` blocks, preventing resource leaks even under unhandled exceptions.
- **Class-Level Lifecycle (`__enter__`, `__exit__`, `close()`)**: Added full context manager support to `Gardener`, allowing clean usage via `with Gardener() as g:`.
- **Configurable `db_timeout` & `PRAGMA busy_timeout`**: Added configurable connection timeout (`db_timeout` / `sqlite_timeout`, default 30.0s) and enforced `PRAGMA busy_timeout = {db_timeout * 1000}` on both system and user database connections to prevent `database is locked` errors during concurrent multi-agent access.
- **Fail-Safe Cross-Database ATTACH**: Hardened cross-database attachment in `_conn()` with proactive `try...except` handling, ensuring connections are closed and not leaked when `ATTACH DATABASE` or initial pragmas fail.
- **Adapter SQLite Hardening (`scan_sqlite_table`)**: Hardened external SQLite table observation adapter with 30s connection timeout, `busy_timeout` pragma, and exception-safe connection termination.
- **Core Refactoring**: Migrated internal database operations across `find()`, `get()`, `put()`, `tasks()`, `recall()`, `consolidate()`, `delete()`, `_set_pinned()`, `list()`, `status()`, and `observe_sources()` to `with self.connection(...) as conn:`.
- **Test Suite Expansion**: Added `TestSQLiteHardeningAndLifecycle` with 6 automated tests, expanding the test suite to 163 passing tests (100% green).

### FTS5 Multi-Word, Special Character & Prefix Search UX Enhancement (2026-09-10)

- **FTS5 Tokenizer & Sanitization (`_tokenize_query`, `_build_fts_and_query`)**: Added query tokenization and safe quoting for special characters (hyphens `-`, colons `:`, slashes `/`, backslashes `\`, parentheses `()`) and unclosed quotes. This prevents SQLite FTS5 syntax errors (such as `OperationalError: no such column: ...` caused by hyphens being interpreted as column operations or column subtractions).
- **Exact Multi-Word AND Matching**: Multi-word queries with hyphens (e.g. `beleg-scanner rechnung`) now reliably evaluate as an FTS5 AND search first, returning precise matches containing all query tokens before falling back to OR search.
- **Prefix Matching with Hyphens (`beleg-scan*`)**: Implemented safe prefix query quoting (`"beleg-scan"*`), allowing wildcard prefix searches on hyphenated names and tools in FTS5 that previously yielded zero results or syntax errors.
- **Highlighted Snippets & BM25 Relevance Retention**: Retained full FTS5 snippet generation (`with_snippets=True`, e.g. for `search_gui.py`) and BM25 ranking on hyphenated queries and file paths (e.g. `C:\Users\lukas`), which previously fell back to LIKE without snippets.
- **Test Suite & Metadata Expansion**: Added 4 unit tests (`test_tokenize_query_and_build_fts_and_query_helpers`, `test_find_with_hyphens_special_chars_and_snippets`, `test_multi_word_and_priority_with_hyphenated_terms`, `test_find_unclosed_quote_tolerance`). Synchronized test badges and metadata across `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py`.

### Targeted freshness for provenance lookup (2026-09-09)

- `gardener find --refresh-source <id>[,<id>] <query>` updates only the
  named observe sources before searching and reports indexed/skipped counts.
  Ordinary `find` remains a read of the existing local index.
- The Codex transcript adapter also reads the current clean
  `event_msg/item_completed` user and agent view items, records their
  `thread_id` as session provenance, and keeps command/tool items excluded.
  This makes a current Codex session ID searchable after its source refresh.
- Codex transcript offset state now carries a parser revision. The first
  refresh after this parser upgrade rewinds only Codex transcript files with
  legacy state, recovering newly supported records from completed, unchanged
  rollouts; subsequent refreshes return to incremental EOF processing.

### Pinning Management API & CLI (`pin()`, `unpin()`, `list --pinned`, `status`) (2026-09-09)

- **Dedicated Pinning API (`pin()`, `unpin()`)**: Added `Gardener.pin(name: str) -> bool` and `Gardener.unpin(name: str) -> bool` to explicitly toggle an entry's `pinned` state (persisting across `user.db` and `system.db`), protecting entries from decay and automatic forgetting in `consolidate()` and boosting relevance in `find()`.
- **CLI Commands (`gardener pin`, `gardener unpin`)**: Added CLI subcommands `gardener pin <name>` and `gardener unpin <name>` with proper German umlauts and i18n support.
- **Filterable Entry Listing (`list(pinned=...)` & `gardener list --pinned`)**: Added optional `pinned: Optional[bool] = None` parameter to `Gardener.list()` and `--pinned` CLI flag to filter by pinned/unpinned entries, with visual `[PIN]` badges displayed next to pinned items.
- **Status Metrics**: Integrated total count of pinned entries (`pinned_entries`) into `Gardener.status()` dictionary and the CLI help header.
- **Contract & Core Test Suite Expansion**: Added 4 unit tests (`test_pin_and_unpin_api_and_persistence`, `test_list_with_pinned_filter`, `test_status_reports_pinned_entries`, `test_pin_and_unpin_cli`), raising the test suite to 151 passing tests (100% green).
- **Metadata & Seed Documentation Parity**: Synchronized test badges, `llms.txt`, `seed.py`, `tests/test_metadata.py`, `ROADMAP.md`, and `ROADMAP_de.md`.

### Marketing, Discoverability, Invariants Matrix & Navigation Modernization (2026-09-08)

- **14-Point Bilingual Quick Navigation**: Added standardized quick navigation sections (`## 🧭 Quick Navigation` / `## 🧭 Schnellnavigation`) across `README.md` and `README_de.md` with complete German/English anchor parity.
- **Dual Mermaid Visualizations**: Added interactive runtime sequence diagram (`### End-to-End Query & Execution Lifecycle`) illustrating pre-ranking namespace filters, FTS5 BM25 match retrieval, and safe workspace materialization alongside the existing architecture flowchart.
- **10-Point Governance & Runtime Invariants Matrix**: Formulated and embedded 10 architectural guarantees (100% Offline / Zero-Egress, FTS5 BM25 Associative Memory, Automated Secret Redaction, Cloud Leak Alerting, Read-Only External Observation, Path Traversal Sanitization, Ephemeral Workspace & Non-Elevation, Multi-OS CI Matrix, Strict CI Concurrency & Bytecode Gate, and Dual-Language & Metadata Parity).
- **Shields.io Badges Modernization**: Added Code style: Ruff badge, updated test metrics to 147 passing tests, and updated security badge to 48h SLA response.
- **Security Policy Hardening (`SECURITY.md`)**: Embedded dual SLA commitments (48h acknowledgment + 5-business-day triage assessment) and added `security@open-bricks.org` in both English and German policy sections.
- **CI Workflow Hardening (`.github/workflows/ci.yml`)**: Added concurrency group with `cancel-in-progress: true` and whole-repository bytecode compilation check (`python -m compileall -q .`).
- **Repository Hygiene & `.gitignore` Hardening**: Added patterns for cloud-sync conflict files (`*.sync-conflict-*`, `*.conflict`), LOCK markers (`LOCK.*`, `*.lock`), and linter/cache files (`.ruff_cache/`, `.pytest_cache/`).
- **PEP 621 Metadata Alignment (`pyproject.toml`)**: Declared `"Parent Organization" = "https://github.com/ellmos-ai"` under `[project.urls]`.
- **Machine-Readable Context (`llms.txt`)**: Updated `Last-checked` timestamp to `2026-09-08` and synchronized test count to 147 passing tests.
- **Local Marketing Log (`MARKETING-LOG.txt`)**: Authored comprehensive Pfad B audit log documenting baseline, enhancements, and strategic next steps.
- **Contract Test Suite Expansion (`tests/test_metadata.py`)**: Added 8 new automated validation tests asserting navigation links, invariant table parity, sequence diagram validity, security SLAs, CI concurrency, bytecode compilation, `.gitignore` patterns, and ecosystem metadata (147/147 tests passing).

- **Workspace Management (`clean_workspace()` & CLI `gardener clean-workspace`)**:
  - Added `Gardener.clean_workspace(name=None, max_age_seconds=None)` to clean up ephemeral tool run scripts and workspaces under `data_dir/workspace/`.
  - Added CLI command `gardener clean-workspace [name] [--older-than <seconds>]` with clean German user feedback using proper umlauts.
  - Added workspace disk usage metrics (`files`, `size_mb`) to `Gardener.status()` and CLI status overview.
  - Added i18n support for workspace command and help strings in `i18n.py` and `locales/translations.json`.
- **Test Suite & Parity Updates**:
  - Expanded test suite to 139 passing tests (100% green).
  - Synchronized test badges and metadata across `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py`.
- Add the existing `_control-center/_PLANS` register as the opt-in system-tier
  `plans-register` observe source. Gardener indexes its three metadata/report
  files read-only and does not become the plan authority or a second plan store.
- Add a contract test for the exact source path, file allowlist, and plan/governance
  tags.

## 2026-08-25 [0.4.2]

- **Configurable Tool Execution Timeouts (`run()` & `config.json`)**:
  - Added optional `timeout: Optional[int] = None` parameter to `Gardener.run()`, falling back to `run_timeout` or `runner_timeout` in `config.json` (default: 60s).
  - Improved timeout error reporting format with exact duration: `Timeout: '{name}' hat länger als {timeout}s gedauert.`.
- **Safe Runner Scope & Parameter Aliasing**:
  - Replaced builtin `input` shadowing in `Gardener.run(name, input_data=None, timeout=None)` signature with full backward compatibility via `input_data` and keyword argument `input`.
  - Upgraded runner script generation (`_build_runner`) to define both `payload` and `input` (`payload = input = json.loads(...)`), cleanly supporting tools executing via `execute(payload)` or `execute(input)`.
- **Configurable Filesystem Exclude Patterns (`exclude_patterns`)**:
  - Added `exclude_patterns` list in `config.json` and upgraded `_is_internal()` to filter out custom fnmatch / glob patterns across `observe()` and `sync()`.
  - Maintained full static and instance method compatibility for `_is_internal()`.
- **Freiwilligkeit der observe-source-Seedung (`seed.py`)** (T-20260825-329696802):
  - Standalone-sicherer Default: `_seed_observe_sources()` seedet ohne explizite Zustimmung nur noch die agentenneutrale `base`-Ebene (Transkripte/Memories/Skills/Commands, gilt fuer jeden Agenten-Nutzer). Die `system`-Ebene (setzt ellmos-Infrastruktur wie USMC/taskplan/policies/tickets voraus) lief zuvor unbedingt mit, sobald ein Pfad zufaellig auf dem Host existierte -- jetzt braucht sie ausdruecklich `GARDENER_SEED_ECOSYSTEM_SOURCES=1`.
  - Voller Abschalter: `GARDENER_SEED_OBSERVE_SOURCES=0` ueberspringt die Seedung komplett, auch die `base`-Ebene -- gilt unbedingt, auch bei explizit uebergebenem `tiers`-Argument.
  - `_default_seed_tiers()` neu extrahiert; 5 neue Tests in `tests/test_seed_observe_sources.py` (Default ohne `system`, explizite Zustimmung, voller Abschalter, Abschalter-Vorrang vor explizitem `tiers`, `_default_seed_tiers()` direkt).
- **Test Suite & Metadata Expansion**:
  - Added comprehensive unit tests in `tests/test_gardener_core.py` and `tests/test_seed_observe_sources.py`.
  - Expanded test suite to 135 passing tests (100% green).
  - Synchronized metadata, documentation, and badges across `pyproject.toml`, `README.md`, `README_de.md`, and `llms.txt`.

## 2026-08-23 [0.4.1]

- **Multi-OS GitHub Actions CI Matrix (`.github/workflows/ci.yml`)**:
  - Implemented multi-OS testing matrix across `ubuntu-latest`, `windows-latest`, and `macos-latest` on Python versions `3.10`, `3.11`, `3.12`, and `3.13`.
  - Added automated `actions/checkout@v4`, `actions/setup-python@v5` with pip caching, Ruff linting gate (`ruff check .`), byte-compilation verification (`compileall`), and `pytest` execution.
- **Bilingual Security Policy (`SECURITY.md`)**:
  - Authored comprehensive English & German security policy defining Local-First & Zero-Egress SQLite substrate guarantees, secret redaction & token masking invariants in `sources.py`, unprivileged User-Mode (Non-Elevation), and coordinated vulnerability disclosure channels (`security@ellmos.ai`, `support@lukasgeiger.com`, `lukas@open-bricks.org`).
- **PEP 621 Standard Classifiers, URLs & Ruff Lint Config (`pyproject.toml`)**:
  - Added standardized PEP 621 metadata classifiers (`Development Status :: 4 - Beta`, `OS Independent`, `POSIX :: Linux`, `Microsoft :: Windows`, `MacOS`, Python 3.10-3.13).
  - Configured complete `[project.urls]` (`Homepage`, `Documentation`, `Repository`, `Issues`, `Changelog`, `Security`, `Umbrella`) and `[tool.ruff]` linting rules.
- **Code Hygiene & Ruff Lint Cleanup**:
  - Removed unused imports and extraneous f-string prefixes in `gardener.py` and `seed.py`.
  - Renamed ambiguous iteration variables (`l` -> `like_param`) in FTS/LIKE multi-word queries.
- **Metadata Contract Test Expansion (`tests/test_metadata.py`)**:
  - Expanded contract test suite with 8 rigorous assertions verifying multi-OS CI workflow integrity, bilingual security policy, PEP 621 metadata, version parity (`0.4.1`), and discovery consistency (119/119 tests passing).

## 2026-08-21

- **Seeded API Reference & Documentation Completeness**:
  - Expanded `gardener-api` system knowledge entry in `seed.py` to cover all core Python methods (`find`, `recall`, `get`, `put`, `delete`, `list`, `run`, `memo`, `lesson`, `session_end`, `consolidate`, `task`, `tasks`, `done`, `task_status`, `absorb`, `materialize`, `observe`, `sync`, `status`, `observe_source_*`, `observe_sources`), CLI commands, and all 10 entry types with authentic German umlauts.
  - Added unit test `test_seeded_api_reference_covers_all_core_capabilities` to verify `gardener-api` in `gardener.db` comprehensively references all core methods and CLI interfaces.
- **CI Modernization & Python 3.13 Matrix**:
  - Modernized GitHub Actions workflow (`.github/workflows/tests.yml`) to test across Python 3.10, 3.11, 3.12, and 3.13.
  - Included `search_gui.py` in CI `compileall` check.
  - Upgraded GitHub Actions steps to `actions/checkout@v4` and `actions/setup-python@v5`.
- **Metadata Parity & Test Suite**:
  - Test suite grew to 116 passing tests (100% green).
  - Synchronized badges and documentation in `README.md`, `README_de.md`, `llms.txt`, and `tests/test_metadata.py`.

## 2026-08-17

`markdown_dir` gained `exclude_patterns`, and BACH's own knowledge base is
now observed alongside its existing `bach-facts`/`bach-lessons`/`bach-working`
memory-table sources.

- **`exclude_patterns` on `markdown_dir`/`remember_files`** drops filenames
  matching an fnmatch pattern back out of what `patterns`/`glob` already
  matched -- e.g. a generated help directory that ships one canonical
  language plus several machine-translated siblings per key, where
  `patterns` alone cannot express "*.txt but not *_en.txt" (fnmatch's
  `[!seq]` only excludes a single character, not a suffix).
- **Six new BACH observe-sources**: `bach-wiki` and `bach-skills`
  (`sqlite_table` against `wiki_articles`/`skills` in `~/.bach/bach.db`,
  read-only), `bach-root-docs`/`bach-system-docs`/`bach-docs`
  (`markdown_dir` over BACH's README/architecture/changelog/roadmap files),
  and `bach-help-de` (BACH's generated per-command help directory, German
  only via the new `exclude_patterns`). BACH itself is never written to.

## 2026-08-16 [0.4.0]

- **Discoverability, README-Design, Badges & Metadata Parity**:
  - Synchronized badges in `README.md` & `README_de.md` across Test Suite (108 passed, 100% green), Version (`0.4.0`), Python (`>=3.10`), License (`MIT`), `ellmos-ai` Ecosystem, `open-bricks` Umbrella, and `llms.txt` Discovery.
  - Added interactive bilingual Mermaid architecture diagrams detailing the `gardener CLI`/Python API/Search GUI layers, Core Engine (FTS5 BM25 search, Materialize & Run execution engine, federated observe engine with secret redaction and cloud-alert gate), Dual-Database Substrate (`gardener.db` system / `user.db` user space), and federated observe sources (`markdown_dir`, `remember_files`, `sqlite_table`, `agent_transcripts`).
  - Added complete sibling tools matrix linking `ellmos-ai`, `dev-bricks`, and `open-bricks` ecosystem modules (`ellmos-core`, `clutch`, `BACH`, `USMC`, `Rinnsal`, `ellmos-controlcenter-mcp`, `ellmos-filecommander-mcp`, `ellmos-codecommander-mcp`, `ellmos-clatcher-mcp`, `n8n-manager-mcp`, `skills`, `DevCenter`, `open-bricks`).
  - Implemented automated metadata and discoverability parity test suite in `tests/test_metadata.py` (5/5 assertions passed).
  - Updated `llms.txt` Last-checked header to `2026-08-16` and test count to 108 passing tests.

## 2026-08-13

`find()` can be restricted to one observe-source, so a small source is no
longer buried by a large one.

- **`--source <id>[,<id>]` / `find(source=...)`** filters on the
  `observed/<source-id>/…` namespace as a `WHERE` condition -- before the
  ranking, and in all three stages of `find()`: exact FTS, the multi-word OR
  fallback, and the LIKE fallback. Wiring it into only the first stage would
  have dropped the filter silently on any multi-word query.
  - Why it was needed: source sizes differ by three orders of magnitude. On
    the reporting machine `codex-sessions` holds 260,623 transcript lines
    against 518 in `usmc-working`, out of 290,902 `observed` entries total.
    BM25 hands the entire first page to the transcripts, so a subject-matter
    search returns nothing usable and reads as "not in the index".
  - A source id matches a whole path segment, so `--source usmc` does not
    pull in `usmc-working`. A leading `observed/` is optional, several ids
    are OR-ed, and `_`/`%` in an id are escaped instead of acting as LIKE
    wildcards.
- **`--source` without a query lists the source**, newest first. FTS5 needs a
  term to match; "show me everything from this source" has none, so that case
  takes a plain `WHERE`/`ORDER BY updated` path instead of returning nothing.
- **`--type` and `--limit` are now reachable from the CLI.** `find()` already
  accepted both; only the command line did not pass them through.
- **The `find` command parses its own flags.** The CLI has no argparse and
  joined everything after `find` into the query, so `--source` would have
  become a search word. `_parse_find_args()` splits options from search terms,
  accepts `--flag value` and `--flag=value`, and reports unknown options and
  missing values instead of silently searching for them.
- Documented in `README.md` and `README_de.md`, including the pre-existing
  workaround for older versions (pass the source id as a search word -- entry
  names are in the full-text index) and the boundary against `extra_tags`,
  which labels a source at registration time rather than narrowing one search.
- Test suite grew from 86 to 108 tests.

Read-only change: no schema migration, no new index, `recall()` untouched, and
existing `find()` callers keep their behaviour (the new parameter is appended
and defaults to `None`). That includes the edge case `find("")` *without* a
source: it still falls through to the LIKE stage, where `%%` matches everything
and the call acts as a browse. Only the combination of an empty query **and** a
source takes the new listing path -- asserted by a test, because guarding the
three search stages on a non-empty query would have turned that browse into an
empty list without anyone noticing.

## 2026-08-05

Fixed: the never-index list missed Windows paths on non-Windows hosts.

- `sources.is_excluded()` split its argument with the host's own path
  rules, so on Linux and macOS a raw `C:\_Local_DEV\CREDENTIALS\x.md`
  arrived as a single segment and never matched `credentials`. Backslashes
  now count as separators everywhere -- the block list fails closed on any
  host. The CI runs on Linux and had been red on exactly these two cases
  since 2026-08-02.

## 2026-08-02 (later)

Secrets are now redacted on the way into the index, a credential found in a
cloud-synced document raises an alert, and archived transcripts are read
straight out of their zip.

- **Secret redaction (`sources.redact_secrets`)**, applied in `scan()` --
  the one gate every adapter's items pass through, so a future adapter
  cannot forget it. The pattern family stays readable
  (`ghp_***REDACTED***`), the value does not survive.
  **Deliberate semantics: an agent that needs the real token must go to
  the source file. The index says where a credential lives, never what it
  is.**
  - 13 families, following the documented formats used by GitHub secret
    scanning, gitleaks and Yelp detect-secrets: Anthropic, OpenAI (legacy
    and project/service/admin keys), GitHub PAT classic + fine-grained,
    AWS access key ids, Slack bot/user/app tokens, Google API keys, GitLab
    PATs, npm tokens, `Authorization: Bearer` headers, and PEM private-key
    blocks.
  - Every pattern anchors on a fixed length, a restricted character class
    and -- where the vendor provides one -- a literal marker (`T3BlbkFJ`,
    the trailing `AA` on Anthropic keys). That anchoring, not the prefix,
    is what keeps prose out: `skalar`, `ghpx_…`, `AKIAA`, `AIzaX`, `npm_install`
    and a bare "Bearer" in a sentence are all left alone (asserted).
  - AWS bodies match `[A-Z0-9]{16}`, not gitleaks' base32 `[A-Z2-7]{16}`:
    the narrower class would let a real key containing 0/1/8/9 through,
    and for a redaction step missing a live secret is the worse error.
  - Deliberately **not** included: entropy heuristics and keyword
    detectors (`password=`). Both are documented high-recall/low-precision
    and would black out hashes, UUIDs and ordinary config prose. A step
    that runs unattended must not guess.
  - Fingerprints stay computed over the original text -- they answer "has
    the source changed", and the source is the unredacted file. Rewriting
    them would invalidate every stored fingerprint and force a full
    re-index.
- **Cloud credential alert.** A signature found in a file under
  `~/OneDrive` (override: `GARDENER_CLOUD_ROOT`) is a security finding in
  its own right -- the value has left the machine. One line per finding is
  appended to `SECURITY-ALERT_TOKEN-IN-ONEDRIVE.md`
  (`GARDENER_CLOUD_ALERT_FILE`) with date, source path and family --
  **never the value and never the surrounding text**, because the alert
  file lives in the very folder it warns about. Idempotent: a finding
  already listed is not appended again. A signature in a *local* transcript
  (`~/.codex`, `~/.claude`) raises no alert -- it never left. Findings are
  also reported in `observe_sources()`' stats and warned about on stderr.
- **Zip archives as a transcript source.** `agent_transcripts` reads JSONL
  members straight out of a `.zip` via `zipfile`; nothing is unpacked to
  disk. `zip_inner` selects members (default `*.jsonl`). Incrementality is
  per archive rather than per byte offset -- an archive is a finished
  thing, so an unchanged (mtime, size) skips the whole file unopened.
  Archives holding no matching member simply yield nothing.
- Refactor: the per-line work of `scan_agent_transcripts` moved into
  `_transcript_item()`, shared by the plain-file and zip paths so the two
  cannot drift apart in how they extract, name and cite a turn.
- Tests: +11 (redaction positives per family, look-alike negatives,
  prefix-stays-readable, redaction reaching the index through both a
  markdown and a transcript source, alert written/idempotent, local path
  raising no alert, zip indexing/incremental-skip/no-matching-member, and
  redaction inside archives). 74 -> 85.

Measured on this machine: retroactive sweep of the existing 284232 entries
found **6** real credentials (4 npm tokens, 2 AWS key ids), all in local
Codex transcripts, all pasted into sessions by hand -- context like
``//registry.npmjs.org/:_authToken=npm_…`` leaves no doubt they were
genuine. All 6 redacted in place; 0 unredacted matches remain. Cloud alert
initial sweep: **0** findings among indexed OneDrive documents.
`gemini-archive` (the Antigravity conversation archives) indexed 3805
entries from 102 `transcript.jsonl` members in 4.3 s; second run 0.2 s.

## 2026-08-02

Every agent provider on the machine is now in one search -- and the three
transcript presets added yesterday are corrected against the formats they
actually claim to read. All three were written from assumption, not from
the files; measured against real transcripts, two indexed nothing at all
and one indexed mostly noise.

- **`codex` preset rewritten.** A Codex rollout carries the same
  conversation twice: `event_msg` (`payload.type` 'user_message' /
  'agent_message', text in a flat `payload.message`) and `response_item`
  (the raw model exchange). The old preset read only the second one --
  duplicating every assistant turn verbatim, pulling injected
  AGENTS.md/skill boilerplate in as "user" text, and missing the clean
  channel entirely. Now only `event_msg` is indexed.
- **`codex` preset also drops sub-agent tool traffic.** When Codex
  delegates, it wraps the sub-agent's tool calls and their output into
  ordinary `agent_message` events prefixed `[external_agent_tool_call:
  Read]` / `[external_agent_tool_result]`. The payload is a verbatim
  file dump, command stderr or diff -- prose everywhere else in this
  module is what gets indexed, and this is not it. Measured on a real
  archive: **49,286 of 309,883 indexed Codex turns (15.9%)** were tool
  traffic.
- **`kimi` preset rewritten.** It looked for a `TurnBegin` wrapper and
  flat top-level `role`/`content` strings; neither exists in a real
  `wire.jsonl`, so the preset returned nothing for every line of every
  file. Kimi's wire log is an event stream: agent prose arrives as
  `context.append_loop_event` -> `content.part` (`part.type='text'`,
  while `'think'` parts are internal reasoning), user turns as
  `context.append_message` with `message.origin.kind='user'`. That
  origin check matters -- roughly two thirds of user-role messages are
  injected reminders, cron firings and hook results.
- **`gemini_antigravity` preset narrowed.** It treated any
  `source == "MODEL"` step as an assistant turn, which also matches
  VIEW_FILE, RUN_COMMAND, LIST_DIRECTORY, GREP_SEARCH and CODE_ACTION --
  file dumps, command output and diffs, i.e. exactly the tool noise the
  Claude Code extractor skips on purpose. Only `PLANNER_RESPONSE` counts
  now.
- **`path` may be a list of glob patterns**, and `agent_transcripts`
  takes **`key_by: 'name'`**. Together they solve transcript rotation:
  Codex moves finished rollouts from `sessions/` to
  `archived_sessions/`, and with a path-keyed state the same file came
  back as a new key, was re-read from offset 0 and landed in the index a
  second time under a second name. One source spanning both directories,
  keyed on the (globally unique) filename, keeps a moved file's identity.
- **Never-index list (`sources.EXCLUDED_PATH_SEGMENTS` /
  `EXCLUDED_FILENAMES` / `EXCLUDED_SUFFIXES`, `sources.is_excluded()`)**,
  enforced per file inside the adapters, so an over-broad or mistyped
  glob cannot pull credentials into the index: `CREDENTIALS/`, `.ssh`,
  `.gnupg`, `.gardener` itself, `node_modules`, `.git`, `.venv`,
  `__pycache__`, and files like `.npmrc`, `.env`, `auth.json`, `*.pem`,
  `*.key`. Segments are matched whole, so a sibling named
  `credentials-howto.md` is not caught. `gardener.py` derives
  `INTERNAL_SKIP_PREFIXES` from that same list -- one list to maintain,
  and what a source adapter refuses to read, the home-folder walk
  refuses too.
- **`observe_sources()` batches its writes.** It used to spend three
  connections per item (a `get`, `put`'s own, and `put`'s return `get`),
  each opening the DB, ATTACHing the sibling and committing -- about 20
  items/s, which is days for a six-figure transcript archive. It now
  holds one connection per source and commits every 2000 items. Same
  upsert, same FTS (trigger-maintained), same per-item fingerprint skip.
- **New sources:** `codex-sessions` (rollouts across `sessions/` +
  `archived_sessions/`), `codex-history` (the flat cross-session prompt
  history), `gemini-transcripts` (one `transcript.jsonl` per `brain/`
  session), `gemini-automations` (the `automation.toml` prompts),
  `kimi-transcripts` (`wire.jsonl` per agent per session).
  `decisions-archive` widened to `*.txt` -- the archived decision files
  are mostly `.txt`, so only the `.md` minority was being indexed.
- Deliberately **not** indexed, with reason: Antigravity's
  `conversations/*.db` (content columns are Protobuf BLOBs, not text),
  `agyhub_summaries_proto.pb` and `annotations/*.pbtxt` (binary/Protobuf),
  `brain/*/.git` (code snapshots, not conversation), and
  `transcript_full.jsonl` (same turns as `transcript.jsonl`, ~1.6x the
  bytes -- indexing both would duplicate every session).
- `rinnsal-tasks` stays registered and returns 0: both
  `~/.rinnsal/rinnsal.db` and `scanner_tasks.db` exist, and their
  `rinnsal_tasks` table is genuinely empty. Nothing to fix.
- Tests: +6 (never-index list across segments/filenames/suffixes, the
  two adapters honouring it, the shared list reaching `gardener.py`,
  Gemini tool-step filtering, and a rotation test that moves a file
  between directories and asserts nothing is re-indexed). Corrected the
  two presets' tests, which had asserted the invented formats, and
  extended the Codex one to cover sub-agent tool traffic. 67 -> 73.

Measured on this machine after the change: 43 sources, `everything`
14293 -> 284232, `user.db` 57 MB -> 529 MB. The bulk is
`codex-sessions` (260597) -- 4663 rollouts across `sessions/` and
`archived_sessions/`, 10.4 GB of raw JSONL. First scan 9.6 min; the
second scan of the same 10.4 GB takes **0.7 s**, because every unchanged
file is skipped on offset+mtime without being opened.

## 2026-08-01 (later)

- **`markdown_dir`/`remember_files`: new `extra_tags`** (string or list),
  appended to every item's tags. `type` is always `observed` for anything
  an observe-source indexes, so a consumer going straight at the DB
  (rather than through `recall()`) has no way to tell a rule file apart
  from a rotating registry without it -- both are `observed` alike.
  `extra_tags` adds a source-level axis for exactly that distinction,
  without inventing a second `type`.
- **12 new observe-sources**, all `markdown_dir`, all read-only:
  - `.SYNC/_policies/library` and `/adoption` (`policy-library` 4,
    `policy-adoption` 4), tagged `policy`.
  - Root-level pipeline steering docs (`CLAUDE.md`, `README.md`,
    `MASTER-REGISTRY.md`, `POLICY-REG.md`, `STATUS_UEBERSICHT*.md`) for
    six pipeline roots (`pipeline-docs-topics` 1, `-ai` 1, `-research` 13,
    `-roblox` 3, `-software` 4, `-umbruch` 2), tagged `pipeline-doc`. Root
    level only, deliberately not recursive -- a pipeline root can hold
    thousands of per-project files below it.
  - Root-level `CHECKS-REG.md` on the four pipeline roots where a plain
    (non-host-suffixed) copy actually exists (`register-log-ai`,
    `-research`, `-roblox`, `-software`, 1 each), tagged `register-log`.
    Deliberately excludes host-suffixed rotation copies
    (`CHECKS-REG-<HOST>-<N>.md`) and the large rotating `CHECKS-LOG*.txt`
    raw logs -- those are exactly the "thousands of files" scope this
    layer has always avoided.
  - `AUTOMATIONS-MEMORY.md` was searched for too, but not newly
    registered: the two canonical copies are already indexed by the
    pre-existing `gemini-rules` and `gemini-antigravity` sources.
  - `everything` count: 14257 -> 14293 (+36), matching the sum of what
    each new source reported indexed.
- **Two disabled-by-default source-config templates for cross-host
  federation** via a separate transit-sync mechanism that mirrors another
  host's databases to read-only `~/.republica/<host>/<namespace>.sqlite` (Republica showcases)
  snapshots: `usmc_replica_source_configs(host)` (facts/lessons/working/
  sessions, the same four-way split as this machine's own `usmc-*`
  sources) and `gardener_replica_source_config(host)` (the foreign
  `everything` table). Both raise for the current machine's own hostname
  -- a replica directory named after the current host is that host's
  replica of *itself*, and indexing it would duplicate every row under a
  second source_id. Neither is registered anywhere by default; arming one
  is a two-line call once a real other-host snapshot exists (see
  `sources.py`'s module note above `usmc_replica_source_configs`).
- Tests: +10 (`extra_tags` on/off/single-string; the two template
  builders' self-host guard and disabled-by-default shape; a disabled
  replica, an enabled-but-absent replica, and an enabled replica against
  a real foreign snapshot are all clean, exception-free paths). Suite:
  54 -> 64.

## 2026-08-01

- **README language parity:** Synchronized `README_de.md` with the canonical
  English structure and restored byte-identical code blocks across the
  maintained EN/DE pair.
- **Every agent's memory in one search**: the observe-source layer now covers
  the other coding agents on the machine, not just Claude Code. Newly indexed
  (all read-only, originals untouched): Codex/GPT memories and rule file
  (`codex-memories` 4, `codex-rollouts` 256 run summaries, `codex-rules` 1),
  Gemini/Antigravity (`gemini-rules` 4, `gemini-antigravity` 3), Kimi's prompt
  history (`kimi-prompts` 515), and the USMC memory database
  (`usmc-facts` 9, `usmc-lessons` 8, `usmc-working` 95, `usmc-sessions` 4).
  All of it lands as `observed`, never as `memory`/`lesson`: foreign material
  belongs in `find()`, and must not crowd out what `recall()` was curated for.
- **`sqlite_table`: `content` may now name several columns**, joined in order.
  A row whose meaning is split over two text fields was only half searchable
  before — whichever column was not configured simply was not in the index.
  This was live: `bach-lessons` had been indexing `solution` while every
  lesson's `problem` text stayed invisible. Both BACH and USMC lessons are now
  indexed as problem + solution (174 BACH lessons re-indexed).
- **`agent_transcripts`: new `default_role`** for single-role archives that
  carry no role field at all. Without it such a file indexed nothing, because
  an absent role never matches the `roles` filter — which is exactly what a
  bare prompt history looks like. A missing role without `default_role` is
  still skipped rather than indexed under an invented one.
- **Fixed a source pointing at a path that no longer exists**:
  `memoryhooker-docs` still referenced the module's pre-2026-07-26 location.
  A source can go stale silently — it keeps reporting success while indexing
  an empty directory.
- Tests: +4 (multi-column content incl. an unknown-column refusal,
  `default_role`, and the unchanged no-role-no-default guard). Together
  with the search GUI landed the same day, the suite stands at 54.

## 2026-07-31

- **Search GUI for humans (`search_gui.py`, `gardener gui`)**:
  - New dependency-free, read-only web UI over the FTS5 search core:
    search box, type filter, BM25-ranked results with match snippets and
    an entry detail view. Pure standard library (`http.server`), binds to
    127.0.0.1 only, GET endpoints exclusively — no writes against
    `gardener.db`/`user.db` (privacy per design: local, read-only).
  - Follows the BACH `unified_search` pattern (FTS5 `snippet()` markers
    `>>>`/`<<<` rendered as highlighted matches in the browser).
  - `find()` gained an optional `with_snippets=True` parameter returning
    an FTS5 `snippet()` context per hit (LIKE-fallback hits carry no
    snippet; default behaviour unchanged).
  - CLI: new command `gui [--port N] [--no-browser]`; help text and
    translations (`cmd.gui`) added; `pyproject.toml` ships the new
    `search_gui` module.
  - 11 new tests (`tests/test_search_gui.py`): snippet API, index page,
    search/entry/status endpoints, type filter, 404 handling, read-only
    enforcement. Suite verified at 50/50 passing.

## 2026-08-01 (multi-agent transcripts)

- **Multi-Agent Transcript Format Support**:
  - Added native format extractor presets for **Gemini Antigravity** (`gemini_antigravity`), **Codex** (`codex`), and **Kimi** (`kimi`) in `scan_agent_transcripts` (`sources.py`).
  - Added support for indexing Gemini transcript logs (`~/.gemini/antigravity/brain/*/.system_generated/logs/transcript.jsonl`), Codex session & history JSONLs (`~/.codex/history.jsonl`, `~/.codex/archived_sessions/*.jsonl`), and Kimi wire transcripts (`~/.kimi/sessions/*/*/wire.jsonl`).
  - Extended metadata mapping (`session`, `uuid`, `timestamp`, `step_index`) across all supported agent formats while retaining 100% backward compatibility for `claude_code` and `generic`.
  - Added 3 new unit tests in `test_observe_sources.py` (`test_gemini_antigravity_format_preset`, `test_codex_format_preset`, `test_kimi_format_preset`).
  - Suite nach Integration in den aktuellen Stand: 64 -> 67 grün. (Die Arbeit
    entstand parallel auf einem OneDrive-Checkout gegen einen 42er-Stand und
    wurde am 2026-08-01 im Zuge der Plan-D-Migration hierher übernommen.)

## 2026-07-30

- **Multi-Word Query UX Improvement & FTS5 BM25 Ranking**:
  - Implemented automatic FTS5 OR query decomposition (`_build_fts_or_query`) for multi-word queries in `find()` when strict AND search yields 0 results.
  - Multi-word searches (e.g. `"Registry Mitgliedschaft"`) now match documents containing individual terms while automatically ranking documents containing all terms higher via FTS5 BM25 relevance. Preserves explicit quotes (`"..."`) and boolean operators (`AND`, `OR`, `NOT`).
  - Hardened SQLite connection handling across `find()` and `get()` with strict `try...finally: conn.close()` resource protection.
  - Added unit test cases (`test_multi_word_query_ux_or_fallback_and_ranking` and `test_build_fts_or_query_helper`) verifying 39/39 passing tests green.
- **Maintenance & Technical Hygiene**:
  - Updated `llms.txt` `Last-checked` timestamp to `2026-07-30`.
  - Re-verified full test suite execution (39/39 passed) and clean repository working tree.

## 2026-07-25 (later)

- **Documentation clean-up (repo after-care)**:
  - Removed references to internal, non-resolvable directory names from the
    public documents (`ROADMAP.md`, `docs/decisions/knowledge-index.md`,
    `locales/translations.json`). They meant nothing to outside readers.
  - `ROADMAP.md` is English again: the trailing sections had drifted back into
    German and carried internal migration notes. Replaced by a short,
    publicly meaningful "Gardener as a memory module" section, and the German
    counterpart added to `ROADMAP_de.md` — both roadmaps now cover the same
    ground.
  - Architecture tree in both READMEs completed (`sources.py`, `i18n.py`,
    `locales/`, `tests/` were missing); header now states the version instead
    of a stale date.
  - Corrected observe-source test count 15 → 17 in both roadmaps (counted at
    the source); full suite verified at 37 passing.
  - Module manifest `visibility` set to `public` (the repository has been
    public for a while); `_after-care/` added to `.gitignore`.

## 2026-07-25

- **Maintenance & Technical Hygiene**:
  - Added `[tool.pytest.ini_options]` with `pythonpath = "."` in `pyproject.toml` for standard pytest resolution.
  - Updated `llms.txt` Last-checked header to 2026-07-25 and test suite count to 37 passing tests.
  - Added Shields.io status badges and LLM integration note callout to `README.md` and `README_de.md`.
  - Verified 37/37 unit and integration tests passing green.

## 2026-07-23

- **New (v0.3.0): Cross-source federated index.** `observe()`'s read-only,
  "look outside" principle is extended to knowledge that lives in *other*
  tools, not just Gardener's own home folder. New module `sources.py` with
  four adapter kinds:
  - `markdown_dir` -- a directory (or wildcard glob of directories) of
    markdown files, one entry per file.
  - `remember_files` -- `.remember`-style note files below a root, via
    recursive glob.
  - `sqlite_table` -- a single table in a foreign SQLite database, opened
    strictly read-only (`mode=ro`); path/table/column-mapping come entirely
    from config, so it can index any foreign schema without Gardener
    knowing it in advance. Table and column names are whitelisted against
    the live schema before use in SQL.
  - `agent_transcripts` -- JSONL chat transcripts, indexed line by line,
    text turns only (tool calls/results and "thinking" blocks are
    skipped). Ships a built-in field mapping for Claude Code's own
    transcript format, plus a generic dotted-path role/text mapping for
    other line-based JSON transcripts. Large, growing files are tailed
    from a saved byte offset (`~/.gardener/observe_sources_state.json`) --
    a refresh never re-reads bytes it already indexed.
  - Every indexed entry carries a `source_ref` in `meta` (file/DB path,
    table+row, or transcript line+uuid) so a search hit always cites back
    to where it actually lives. `find()` already searched `gardener.db` +
    `user.db` in one query, so cross-source hits (stored as ordinary
    `observed` entries in `user.db`) show up alongside your own entries
    automatically -- no new search API needed.
  - New `Gardener` methods: `observe_source_add`, `observe_source_remove`,
    `observe_source_list`, `observe_sources`. New CLI: `gardener
    observe-source add/list/remove/refresh`. Configuration lives in
    `config.json` under `observe_sources`; nothing is hardcoded to a
    specific machine, user, or tool.
  - Deliberately out of scope for this release: adapter presets for the
    Codex/Gemini/Kimi transcript formats (only Claude Code ships a
    built-in mapping; other formats route through the generic
    `role_field`/`text_field` mapping) and the v0.2 decay/usage-tracking
    items (unrelated roadmap section, not touched here).
  - Added 15 regression tests with synthetic fixtures (test suite: 19 ->
    34), covering all four adapters, incremental refresh behavior,
    federated search across own + observed entries, and observe-source
    config CRUD across a simulated restart.

- **New (v0.3.1): `patterns` config for `markdown_dir`.** The
  `markdown_dir` observe-source adapter can now match more than one
  filename pattern per directory via an optional `patterns` list in
  config (default `["*.md"]`), e.g. `patterns=["*.md", "*.txt"]` to
  index plain-text notes alongside markdown in the same source. Files
  matching more than one pattern are only indexed once. Backward
  compatible: the older singular `glob` key keeps working unchanged
  for existing configs; `patterns` takes precedence if both are set.
  List-valued config like `patterns` has to go through the Python API
  (`af.observe_source_add(...)`) -- the CLI's plain `key=value` form
  only accepts strings, not JSON.
  - Added 3 regression tests (test suite: 34 -> 37) covering the
    default markdown-only behavior, the new `patterns` list, and the
    legacy single-`glob` backward-compatibility path.

## 2026-07-11

- Release hygiene: `i18n.py` now carries built-in German/English CLI help fallbacks, so non-editable installs that miss `locales/translations.json` still show readable help text instead of raw translation keys.
- Added a regression test that runs `gardener.py` from a wheel-like copy without the `locales/` directory.

## 2026-07-03

- **Security:** `materialize()` sanitizes `filename`/`original_name` from entry meta to their base name. Previously, meta set via `put()` could contain `..` or absolute paths and make `materialize()` write outside the destination directory (path traversal).
- **Security docs:** new "Security Model" section in README/README_de documenting that `run()` and the seeded `shell` tool execute code without a sandbox, and that any layer exposing `put()`/`run()` must bring its own authorization.
- `sync()` in `always_absorb` mode no longer absorbs and deletes its own `config.json` (which silently reset the mode to `selective` on the next start). `config.json` is now part of the shared internal skip list.
- `_is_internal()` compares whole path segments instead of string prefixes: sibling names like `.absorber-notes.txt` or `.outputs/` are no longer wrongly skipped; internal dirs are now also skipped at any nesting depth.
- `observe()`/`sync()` build `observed/...` entry names with POSIX separators (`rel.as_posix()`), so the same file yields the same entry name on Windows and Unix (previously Windows produced `observed/sub\file.txt`, causing duplicates in cross-system setups).
- `absorb()` raises a clean `FileNotFoundError` for directories instead of crashing later in `_hash_file()` with `IsADirectoryError`/`PermissionError`.
- CLI: `stdout`/`stderr` are reconfigured to UTF-8 with replacement errors in `main()`, so umlauts no longer crash on Windows consoles without `PYTHONIOENCODING=utf-8`.
- CLI: `gardener absorb <path>` prints a clean error message for missing or unreadable files instead of an unhandled traceback.
- CLI: renamed the task loop variable that shadowed the i18n translation function `t`.
- Added 6 regression tests for the above (test suite: 13 -> 19).

## 2026-06-22

- Hardened entry deserialization so invalid `meta` JSON is normalized to an empty object instead of leaking as a string and crashing `recall()` sorting.
- Added a regression test for `recall()` on memory entries with invalid `meta` JSON.

## 2026-06-12

- Removed the never-populated `blobs` table from the schema: blob metadata (`blob_path`, `blob_hash`, `size`, `mimetype`, `original_name`) deliberately lives in the entry's `meta` JSON, which is what `absorb()`/`materialize()` and the design docs already use. Deliberate decision, see DESIGN.md/KONZEPT.md.
- `absorb()` now stores `original_name` in `meta` (was only `original_path`), matching what `materialize()` reads and what the design docs document.
- `observe()` now skips the internal runtime dirs `.absorber/`, `.output/`, `.gardener/`, `__pycache__/` via a skip list shared with `sync()` (previously it skipped a stale `export` prefix and indexed absorber/output files).
- Tasks are now sorted by semantic priority (critical > high > normal > low) instead of alphabetical string order.
- `find()` now preserves FTS5 relevance (bm25 rank) for full-text hits; LIKE-fallback results are ordered newest first. Previously the final sort discarded the rank and listed oldest entries first.
- `consolidate()` no longer decays or forgets pinned entries.
- Documentation: corrected the local data directory to `~/.gardener` (env `GARDENER_DATA`) in README, README_de, KONZEPT and DESIGN; the previously documented `AppData/Local/Gardener/` path was never used by the code.
- Added regression tests for all fixes above (test suite: 5 -> 10 tests).
- Added a minimal `pyproject.toml` (distribution `gardener-os`, since `gardener` is taken on PyPI; console script `gardener = gardener:main`, requires-python >=3.10, zero runtime dependencies). Verified with an editable install in a throwaway venv.
- Replaced romanized German umlaut spellings in seeded user-facing knowledge and bridge-tool descriptions with real umlauts.
- Updated German runtime error messages for tool execution failures to use real umlauts.
- Added a regression test that verifies seeded German texts no longer contain the old `ae`/`oe`/`ue` spellings.

## 2026-06-11

- Added README and `llms.txt` discovery context for the canonical `ellmos-ai/gardener` repository path.
- Added audience, preferred search phrases, disambiguation, and `Last-checked: 2026-06-11` metadata to `llms.txt`.
- Fixed `llms.txt` documentation links to use the repository's actual `master` branch.

## 2026-06-06

- Updated the Gardener test workflow to `actions/checkout@v6` and `actions/setup-python@v6`.
- Documented the CI hygiene refresh without changing runtime behavior.
