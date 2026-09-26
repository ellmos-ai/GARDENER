# Third-Party Licenses & Software Inventory

- **Project:** `Gardener OS` (`gardener-os` / `gardener`)
- **Description:** Database-centric operating system for LLMs: find, get, put, run on a single SQLite substrate.
- **License:** [MIT License](LICENSE)
- **Attribution:** [NOTICE](NOTICE)
- **Audit Date:** 2026-09-26
- **Repository:** [ellmos-ai/gardener](https://github.com/ellmos-ai/gardener)
- **Organization:** [ellmos-ai](https://github.com/ellmos-ai)
- **Umbrella Collective:** [open-bricks](https://github.com/open-bricks)

---

## Runtime Architecture & Zero-Dependency Guarantee

`Gardener OS` is designed from the ground up to guarantee **100% unprivileged, local-first, zero-egress execution**.

The core engine (`gardener.py`), federated ingestion adapters (`sources.py`), reference seeding (`seed.py`, `apply_reference_sources.py`), local web GUI companion (`search_gui.py`), and CLI internationalization (`i18n.py`) execute **exclusively using the Python Standard Library**.

### Runtime Dependencies: Zero External Packages

| Package / Library | Version Constraint | License | SPDX Identifier | Upstream URL | Purpose |
|---|---|---|---|---|---|
| **Python Standard Library** | `>=3.10` | Python-2.0 (PSF) | `PSF-2.0` | [python.org](https://www.python.org/) | Core language runtime, `sqlite3` FTS5 database substrate, `http.server` for local read-only GUI, `json`, `pathlib`, and `argparse`. |

`Gardener OS` ships with **0 external runtime dependencies**, eliminating supply-chain attack vectors, unpinned binary surprises, and external telemetry brokers.

---

## Development, Tooling & Verification Dependencies

The following tools are utilized strictly for local development, code quality enforcement, static analysis, bytecode validation, and continuous integration:

| Tool / Framework | Version Floor | License | SPDX Identifier | Project / Organization | Purpose |
|---|---|---|---|---|---|
| **pytest** | `>=7.0.0` | MIT | `MIT` | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | Automated Python contract, regression, and unit testing framework. |
| **ruff** | `>=0.9.0` | MIT OR Apache-2.0 | `MIT OR Apache-2.0` | [astral-sh/ruff](https://github.com/astral-sh/ruff) | High-performance Python linter and code style enforcement engine. |
| **setuptools** | `>=61.0.0` | MIT | `MIT` | [pypa/setuptools](https://github.com/pypa/setuptools) | PEP 517 / PEP 621 build backend and package packaging. |

---

## Licensing Architecture, Dynamic Linking & Unprivileged Execution

### Permissive Licensing & Zero-Copyleft Contamination
- **Gardener OS Core:** All application code, SQLite schema blueprints, FTS5 BM25 tokenizers, federated ingestion adapters, and the local search GUI are licensed under the permissive [MIT License](LICENSE) with formal copyright attribution in [NOTICE](NOTICE).
- **Standard Library Independence:** Because Gardener relies exclusively on the standard library, no external GPL, AGPL, or restrictive copyleft libraries are statically or dynamically linked into the runtime.
- **Zero-Copyleft Contamination:** The codebase contains no proprietary-restricting or viral copyleft source code. Developers and organizations can safely embed or bundle Gardener OS into autonomous agent stacks without license pollution.

### Unprivileged User-Mode Operation (`RunAsInvoker`)
- All Gardener OS commands (`gardener find`, `gardener get`, `gardener put`, `gardener run`, `gardener gui`, `gardener observe`) execute strictly in **unprivileged user mode** (`RunAsInvoker`).
- No administrative elevation, UAC elevation prompt, or root capabilities are ever required or requested.
- State is partitioned into unprivileged user data (`~/.gardener/user.db` or `$GARDENER_DATA/user.db`) and system blueprints (`~/.gardener/gardener.db`), completely separated from system directories.
- Ephemeral tool executions in `workspace/` operate in unprivileged sandboxes with timeout protection and automated cleanup (`clean_workspace`).

---

## Governance & Runtime Invariants

Gardener adheres to ten foundational governance and runtime invariants:

| Invariant | Category | Description | Verification Method |
|---|---|---|---|
| `INV-LOCAL-01` | Local-First & Zero Egress | 100% offline-first execution; zero telemetry, tracking scripts, or outbound network calls. | `tests/test_metadata.py` & `SECURITY.md` |
| `INV-RUNAS-02` | Unprivileged User Mode (`RunAsInvoker`) | Strictly unprivileged execution; no UAC or root prompts required. | `SECURITY.md` & `pyproject.toml` |
| `INV-FTS-03` | Deterministic FTS5 BM25 Memory | Deterministic SQLite FTS5 BM25 ranking, snippet extraction, and prefix filtering without vector-drift or remote embedding APIs. | `tests/test_gardener_core.py` |
| `INV-SEC-04` | Pre-Index Secret Redaction | 13 credential families (GitHub tokens, AWS keys, Anthropic/OpenAI keys, Bearer tokens, private keys) are redacted in `sources.py` before indexing. | `tests/test_observe_sources.py` |
| `INV-CLOUD-05` | Cloud Leak Alerting | Signatures discovered in cloud-synced roots (`~/OneDrive`) trigger idempotent alerts in `GARDENER_CLOUD_ALERT_FILE` without storing values. | `tests/test_observe_sources.py` |
| `INV-RO-06` | Read-Only External Observation | Foreign sources (BACH wiki, agent transcripts, markdown directories) are queried read-only (`mode=ro`). The host DB never mutates them. | `tests/test_observe_sources.py` |
| `INV-TRAV-07` | Path Traversal & Workspace Isolation | `materialize()` and `absorb()` sanitize target filenames, rejecting directory traversal attempts (`../`, absolute paths) to prevent escapes. | `tests/test_gardener_core.py` |
| `INV-SUB-08` | Unified Everything Substrate | Dual SQLite database substrate (`gardener.db` / `user.db`) unifying memory, tools, tasks, and documents in a single typed table. | `tests/test_gardener_core.py` |
| `INV-DOCS-09` | 1:1 Bilingual Parity & Machine-Readable Spec | Symmetrical 18-point documentation parity across English (`README.md`) and German (`README_de.md`) backed by `llms.txt`. | `tests/test_metadata.py` |
| `INV-SLA-10` | Open Source Governance & SLA | MIT License, public GitHub issues, and committed 48h initial response / 5d triage security SLA. | `SECURITY.md` & `tests/test_metadata.py` |

---

## License Texts & Attribution

### MIT License (`Gardener OS`, `pytest`, `ruff`, `setuptools`)

```text
MIT License

Copyright (c) 2026 Lukas Geiger / ellmos-ai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Python Software Foundation License (Python Standard Library)

```text
PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
--------------------------------------------

1. This LICENSE AGREEMENT is between the Python Software Foundation ("PSF"), and
the Individual or Organization ("Licensee") accessing and otherwise using this
software ("Python") in source or binary form and its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works,
distribute, and otherwise use Python alone or in any derivative version,
provided, however, that PSF's License Agreement and PSF's notice of copyright,
i.e., "Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023,
2024, 2025, 2026 Python Software Foundation; All Rights Reserved" are retained in
Python alone or in any derivative version prepared by Licensee.
```
