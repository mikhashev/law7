# Law7 — Scope: what we claim today vs. where we are going

**Snapshot date:** database backup `law7_backup_20260211_014519.tar.gz` (SHA256 `70a1d8fc6b27b67ad7f12f03f017d02b5f68a0c895447159039800965895f8b2`), data up to 2026-02-06.
**Measured:** 2026-09-14, by restoring the backup and running every MCP tool against it.
**Rule:** the numbers in the left column are updated by re-running the measurements, never by editing this text. If a number here disagrees with `get-statistics` on a live instance, the tool is right and this file is stale.

This file exists because the project's other documents were written at the scale of the goal (a global, decentralized, verifiable statute base) while the code exists at the scale of a proof of concept. Readers — including anyone who restores the public backup — need to know which is which.

---

## 1. Two columns

| Area | **What we claim today** (measured 2026-09-14) | **Where we are going** (design goal, not yet true) |
|---|---|---|
| Jurisdictions | Russia only. One source adapter (`scripts/country_modules/russia/`). | International: one verification protocol, one adapter per country. Russia is the first adapter, not the product. |
| Documents | 1,136,605 metadata records from publication.pravo.gov.ru, publish dates 2019-06-13 → 2026-02-06. 47,871 (4.2%) have a `document_content` row — but that text is short: median 447 characters, 94% under 1,000, maximum 5,565. It is the annotation/heading layer, **not** the body of the act. This was never otherwise: the parser was written knowing the official PDFs are raster scans (`use_ocr=False` by default) — the body was never extracted, while the documentation claimed full text. Only ~8–9% of the PDFs carry a text layer. The only real legal text in the database is the 6,232 code articles (median 914 characters, up to 128 k). | Body text for every act that consolidation needs, extracted or OCR'd from the official artifact and hash-linked to it; daily sync that actually runs. |
| Data freshness | Frozen at 2026-02-06. No sync has run since. Tools do **not** expose the age of the data. | `get-statistics` reports snapshot date, last sync and newest publish date; a client can always tell how old the data is. |
| Consolidated codes | 22 codes, 6,232 article texts (`code_article_versions`), one version per article. KAS_RF not imported. | All federal codes, every article with its full version history. |
| Article history | **None.** `amendment_applications` has 0 rows. The consolidation engine (`amendment_parser`, `diff_engine`, `version_manager`) has never been run on real data. Since 2026-09-14 the tools say so: `get-article-version` with a date refuses with `history_available: false` and names the oldest version held instead of returning the current text; `trace-amendment-history` reports "1 version, 0 amendments applied — history not generated". | Point-in-time: the text of an article as in force on any date, with the chain of amending acts (who, when, what changed), transitional provisions stored as data, and a published backlog of amendments not yet applied. |
| Provenance | `text_hash` is the MD5 of the stored text (`document_content.full_text`, `code_article_versions`) for change detection. No hash of the official source artifact, no captured signature, no manifest. Measured 2026-09-14 on 200 documents from both epochs: the publication URL scheme (`file/pdf?eoNumber=…`) has not changed since 2019 and every reconstructed URL answers (400/400) — for 2019–2022 the database stores no URL at all, they were rebuilt from `eo_number`. `pdf_file_size` from the crawl matches the download in 199/200 — an indirect anchor only (a size survives byte-for-byte substitution). No embedded digital signature was observed in the sampled PDFs by three probes (PDF markers, API fields, static HTML); a detached signature or a viewer-side endpoint has not been ruled out — status `signature: not_observed`, not `none`. | Every document carries the SHA256 of the official signed artifact it was derived from, retrieval date, extractor and consolidator versions; a signed manifest of the whole snapshot that anyone can mirror and re-verify against the official publication. |
| Verification by others | Not possible. The only public artifact is a backup with a SHA256 in the README; nothing to pin to (no tags, no releases). | Anyone can download N random documents from the official source and check them against the manifest without trusting us. Releases are tagged; consumers pin a tag or a manifest hash. |
| Court practice and interpretations | 32,263 official interpretations and 619 court decisions loaded; `search-interpretations`, `search-court-decisions`, `get-supreme-court-resolution` work. Reference tables (`courts`, `legal_positions`, `practice_reviews`) are empty. | Interpretations linked to the articles they read differently; "text unchanged, reading changed" treated as its own kind of change. |
| Regional law | Schema exists; all `regional_*` tables are empty. `search-regional-law` returns nothing; `get-regional-koap-article` fails on a schema mismatch. | Regional adapters after the federal history layer works. |
| Search | Keyword search over PostgreSQL trigrams works. Semantic/hybrid search is **not** implemented: 265 test vectors exist in Qdrant and no tool reads them; the dead `use_hybrid` parameter was removed on 2026-09-14 and `query-laws` declares itself keyword-only. | Hybrid search where version selection is symbolic (by date and identifier) and embeddings only rank within the selected version. |
| MCP tools | 13 registered. As of 2026-09-14: 10 return correct results, 3 return an explicit "no data" or "no history" refusal (`search-regional-law`, `get-regional-koap-article`, `get-article-version` with a date), none crash. Input is validated against each tool's zod schema before execution, so defaults apply and bad arguments are rejected. `get-statistics` reports snapshot date, last sync, body-text count, amendments applied and `history_available`. | Every tool validates input, refuses honestly when data is missing, and returns provenance with every answer. |
| Caching | Redis removed 2026-09-14; add back when a cache is actually implemented (service deleted from `docker-compose.yml`, `ioredis` uninstalled, `REDIS_*` dropped from config and `.env.example`). | A cache added back only when there is a measured need for one. |
| Identifiers | Private vocabulary: `code_id` (`GK_RF`, `UK_RF`, …) + article number. Not resolvable outside law7. | ELI/Akoma Ntoso-style canonical URIs with a point-in-time slot; Akoma Ntoso export. |
| Tests and CI | As of 2026-09-14: 226 Python tests pass, 23 skipped (22 OCR-pending, 1 known production bug in `VersionInfo`); 118 TypeScript tests pass; `tsc` reports 0 errors. CI runs tsc, vitest, ruff and pytest behind gate scripts with known-failure allowlists (currently empty except a ruff baseline of 200 findings); any new failure fails the build. | Green CI on every commit; a schema test that fails when a documented number drifts from the database. |
| Distribution | Source on GitHub (AGPL-3.0 with a section-7 linking exception, see `LICENSE-EXCEPTION.md`). Data as a Google Drive backup. No release, no tag, no package, no registry listing. | Tagged releases; data as backup + signed manifest; MCP server listed in registries. Free. No paid tier, ever. |

## 2. What this project is not

- Not a legal advice system. It stores what the official publication said and what text results from applying published amendments. It does not decide which rule applies to a situation; transitional provisions are stored, not resolved.
- Not a replacement for the official source. The official publication is the only authority; law7 is a verifiable, machine-readable derivative of it.
- Not tied to any transport or network. Federation means "a node near the source extracts, anyone verifies by hash"; how bytes move is out of scope.

## 3. How to re-measure

```bash
docker compose -f docker/docker-compose.yml up -d
docker/restore.sh law7_backup_20260211_014519           # or a newer backup
npm ci && npm run build
npx @modelcontextprotocol/inspector --cli node dist/index.js --method tools/call --tool-name get-statistics
docker exec law7-postgres psql -U law7 -d law7 -c "SELECT count(*) FROM amendment_applications;"
```

Update the left column from the output. Do not update it from memory.
