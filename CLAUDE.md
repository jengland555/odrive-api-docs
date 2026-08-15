# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ODrive Docs ContentOps Quality Engine & AI Sanitizer** — a Python docs-as-code pipeline that lints, validates, chunks, and enriches the ODrive Robotics API reference documentation (`docs/valid/*.md`). It is a portfolio project demonstrating how technical writers build automated governance tooling with software-engineering rigor. See `README.md` for the full pitch and `interview_case_study.html` for a presentation walkthrough.

There is no package manager beyond pip and no test suite — validate changes by running `doc_health_check.py` against the fixture docs (see Commands below).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the linter against the production docs (used in CI, strict + offline)
python doc_health_check.py --path docs/valid --strict --offline

# Run against intentionally-broken fixtures to sanity-check detection
python doc_health_check.py --path docs/invalid --offline

# Auto-fix inclusive-language / weak-phrase violations in place
python doc_health_check.py --path docs/invalid --fix

# Lint a single file
python doc_health_check.py --path docs/valid/axis_states.md --offline

# Generate H2/H3 semantic chunks for RAG indexing -> data/rag_semantic_chunks.json
python doc_health_check.py --chunk --path docs/valid

# Mine ODrive Discourse forum knowledge -> data/forum_scraped_errors.json
python doc_health_check.py --scrape-forum --offline

# Run the Gemini-backed AI tone/passive-voice review (requires GEMINI_API_KEY; falls back to a heuristic engine offline)
python doc_health_check.py --path docs/valid --ai-review

# Export a JSON report (used by CI to upload as a build artifact)
python doc_health_check.py --path docs/valid --strict --offline --json-output lint-report.json
```

There is no `--path` restriction on file type beyond `.md`/`.mdx` — `collect_markdown_files()` in `doc_health_check.py` walks directories recursively.

CI (`.github/workflows/doc-ci.yml`) runs on every push/PR to `main`: strict+offline lint → chunk generation → forum scrape → uploads `lint-report.json` and the two `data/*.json` artifacts.

## Architecture

`doc_health_check.py` is the sole CLI entrypoint. It orchestrates a fixed pipeline of independent, stateless-per-call checker classes from `src/`, each returning a list of issue dicts shaped `{file, line, rule, severity, message}`. `Reporter` (in `src/reporter.py`) is the only place that renders output (Rich terminal tables, or plain-text fallback when `rich` isn't installed) or exits non-zero — checkers themselves never print or raise on lint failures.

Per-file pipeline order in `main()`:
1. **`FrontmatterValidator`** (`frontmatter_checker.py`) — parses the YAML frontmatter block, strips it from the returned markdown body (everything downstream operates on body text only, with `line_offset` tracking so reported line numbers stay accurate), and validates required fields / `category` / `status` / date format against `rules/style_rules.json`.
2. **`LinkChecker`** (`link_checker.py`) — validates `#anchor` links against headings slugified in-document, relative file links against disk, and (unless `--offline`) pings remote `http(s)://` URLs with caching.
3. **`StyleLinter`** (`style_linter.py`) — regex-driven inclusive-language and weak-phrase rules loaded from `rules/style_rules.json`, plus heading-hierarchy-skip and code-block-language checks. Also owns `auto_fix()` for `--fix`.
4. **`EnumValidator`** (`enum_validator.py`) — cross-checks ODrive firmware enum names/values referenced in markdown tables (e.g. `` `AXIS_STATE_IDLE` | `1` ``) against `rules/odrive_enum_reference.json`, a vendored ground-truth extracted from the official [ODriveArduino](https://github.com/odriverobotics/ODriveArduino) library headers. Flags `unknown_odrive_enum` (name doesn't exist, with a fuzzy-match suggestion) and `odrive_enum_value_mismatch` (name exists, value is wrong). This exists because docs can silently drift from the real hardware/firmware API — see Session Log below.
5. **`AISanitizer`** (`ai_sanitizer.py`, only with `--ai-review`) — Gemini API call (`GEMINI_API_KEY` env var) for passive-voice/tone critique; falls back to a regex heuristic engine offline or on API error. Never blocks the exit code — findings are appended as `warning` severity.

Two standalone tasks bypass the per-file pipeline entirely and can be run alongside or instead of it:
- **`SemanticChunker`** (`chunker.py`, `--chunk`) — slices each doc at H2/H3 boundaries (not arbitrary character counts) into RAG-ready chunks with slugified anchors, category/tag metadata inherited from frontmatter, and estimated token counts.
- **`ODriveForumScraper`** (`forum_scraper.py`, `--scrape-forum`) — merges a hardcoded `COMMUNITY_KNOWLEDGE_BASE` of curated real error threads with a live Discourse search when not `--offline`.

**Rules are data, not code**: `rules/style_rules.json` (frontmatter schema, inclusive-language/weak-phrase regex + replacements, structural thresholds) and `rules/odrive_enum_reference.json` (firmware enum ground truth) are both loaded at runtime — adding a new lint rule or enum usually means editing JSON, not Python, unless it needs new detection logic.

**Severity semantics**: `error` always fails the run; `warning` only fails under `--strict` (CI uses `--strict`). This is enforced centrally in `Reporter.render_results()`.

## Session Log

Chronological record of substantive changes made via Claude Code, kept so future sessions have context without re-deriving it from git history alone.

- **2026-08-14 — Verified doc accuracy against the real ODrive Arduino library.** Installed `arduino-cli` (Homebrew) + the official `ODriveArduino` library (v0.10.9) and compiled test sketches referencing every enum name used in `docs/valid/axis_states.md` and `docs/valid/troubleshooting_errors.md`. `axis_states.md` compiled clean (all 9 `AXIS_STATE_*` names/values correct). `troubleshooting_errors.md` failed to compile — all 7 of its error enum names (`ERROR_DRV_FAULT`, `ERROR_PHASE_RESISTANCE_OUT_OF_RANGE`, `ERROR_PHASE_INDUCTANCE_OUT_OF_RANGE`, `ERROR_DC_BUS_OVER_VOLTAGE`, `ERROR_INDEX_NOT_FOUND_YET`, `ERROR_CPR_POLEPAIRS_MISMATCH`, `ERROR_UNSTABLE_GAIN`) were stale/nonexistent against the current library, and its bitfield table had internally-conflicting duplicate values.
- **2026-08-14 — Fixed `docs/valid/troubleshooting_errors.md`.** Rewrote the error catalog to reflect the current library's real three-way split — `ODRIVE_ERROR_*` (bitfield, `odrv0.axis0.active_errors`), `PROCEDURE_RESULT_*` (calibration outcome, `odrv0.axis0.procedure_result`), `COMPONENT_STATUS_*` (per-component health, `odrv0.axis0.encoder.status`) — with correct names and values for each. `ERROR_UNSTABLE_GAIN` has no current equivalent; documented as removed rather than mapped to something incorrect. Also corrected a stale inline error-code reference in the "Playbook 1" troubleshooting steps.
- **2026-08-14 — Added a permanent enum-accuracy CI gate.** New `src/enum_validator.py` (`EnumValidator`) + `rules/odrive_enum_reference.json` (~90 enum members vendored from `ODriveEnums.h`, offline/pure-Python — no Arduino CLI dependency in CI). Wired into `doc_health_check.py` as pipeline step 4, running by default (no new flag), so `.github/workflows/doc-ci.yml`'s existing strict-mode run now enforces it automatically. Regression-tested by re-running the linter against the original (broken) error table content in a scratch copy — confirmed it correctly flags both the wrong value and the nonexistent enum name.
- **Known gap (not yet fixed):** `src/forum_scraper.py`'s hardcoded `COMMUNITY_KNOWLEDGE_BASE` still uses the same legacy error names (`ERROR_DRV_FAULT`, `ERROR_PHASE_RESISTANCE_OUT_OF_RANGE`, `ERROR_INDEX_NOT_FOUND_YET`) as the pre-fix `troubleshooting_errors.md` did. `EnumValidator` only scans markdown docs, not this Python data structure, so it won't catch drift there. Worth aligning if the forum knowledge base is ever surfaced directly into rendered docs.
- **2026-08-14 — Confirmed `docs.html`** (the interactive API reference portal referenced in `README.md`) already exists, is complete (covers all 5 `docs/valid/` files with sidebar nav + search), and was up to date with the *pre-fix* markdown at the time of that check.
- **2026-08-14 — `docs.html`'s troubleshooting table corrected to match the fix, then reverted, then re-corrected.** First pass rewrote the "Critical System & Axis Error Catalog" section to mirror the corrected markdown (split into three tables) plus an explanatory "Corrected" callout box describing the fix. User asked to undo this and move the explanatory content into `interview_case_study.html` instead — reverted via `git checkout -- docs.html` (it had no other pending changes, so this was a clean revert). After the interview case study update landed, user asked for `docs.html`'s data to be corrected too (separately from the narrative) — re-applied the same three-table split (Hardware & Electrical `ODRIVE_ERROR_*`, Calibration `PROCEDURE_RESULT_*`, Sensor & Encoder `COMPONENT_STATUS_*`) but **without** the callout box, since `docs.html` is meant to stay a clean production reference and the "why it changed" narrative now lives in the interview case study instead. All three surfaces — `docs/valid/troubleshooting_errors.md`, `docs.html`, `interview_case_study.html` — are now consistent with each other and with `rules/odrive_enum_reference.json`.
- **2026-08-14 — Added a new pipeline step to `interview_case_study.html`.** Inserted "Firmware Enum Validator" as pipeline step 6 (between "Link & Anchor Integrity" and "AI Tone Pipeline" in both the sidebar nav and section order; renumbered all downstream step tags/nav numbers and the JS `stepOrder` keyboard-nav array accordingly). The new section shows the before/after enum table from the Arduino CLI finding and explains `enum_validator.py`. Also updated the architecture flowchart from "5-Stage" to "6-Stage Modular Validation Suite," and added a new STAR-method interview card ("Tell me about a documentation bug you found and how you verified it") to the existing Q&A section, turning the real debugging session into a ready-to-use interview answer.
