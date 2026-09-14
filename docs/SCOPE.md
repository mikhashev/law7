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
| Documents | 1,136,605 metadata records from publication.pravo.gov.ru, publish dates 2019-06-13 → 2026-02-06. 47,871 (4.2%) have a `document_content` row — but that text is short: median 447 characters, 94% under 1,000, maximum 5,565. It is the annotation/heading layer, **not** the body of the act. The official PDFs are raster scans (only ~8–9% carry a text layer), so no document body has been extracted from pravo.gov.ru at all. The only real legal text in the database is the 6,232 code articles (median 914 characters, up to 128 k). | Body text for every act that consolidation needs, extracted or OCR'd from the official artifact and hash-linked to it; daily sync that actually runs. |
| Data freshness | Frozen at 2026-02-06. No sync has run since. Tools do **not** expose the age of the data. | `get-statistics` reports snapshot date, last sync and newest publish date; a client can always tell how old the data is. |
| Consolidated codes | 22 codes, 6,232 article texts (`code_article_versions`), one version per article. KAS_RF not imported. | All federal codes, every article with its full version history. |
| Article history | **None.** `amendment_applications` has 0 rows. The consolidation engine (`amendment_parser`, `diff_engine`, `version_manager`) has never been run on real data. `get-article-version` with a past date returns the current text; `trace-amendment-history` returns one version. | Point-in-time: the text of an article as in force on any date, with the chain of amending acts (who, when, what changed), transitional provisions stored as data, and a published backlog of amendments not yet applied. |
| Provenance | `text_hash` is the MD5 of the stored text (`document_content.full_text`, `code_article_versions`) for change detection. No hash of the official source artifact, no captured signature, no manifest. Measured 2026-09-14 on 200 documents from both epochs: every source URL is alive on publication.pravo.gov.ru (400/400), `pdf_file_size` matches the download in 199/200, but none of the PDFs carries an embedded digital signature and the API exposes none. | Every document carries the SHA256 of the official signed artifact it was derived from, retrieval date, extractor and consolidator versions; a signed manifest of the whole snapshot that anyone can mirror and re-verify against the official publication. |
| Verification by others | Not possible. The only public artifact is a backup with a SHA256 in the README; nothing to pin to (no tags, no releases). | Anyone can download N random documents from the official source and check them against the manifest without trusting us. Releases are tagged; consumers pin a tag or a manifest hash. |
| Court practice and interpretations | 32,263 official interpretations and 619 court decisions loaded; `search-interpretations`, `search-court-decisions`, `get-supreme-court-resolution` work. Reference tables (`courts`, `legal_positions`, `practice_reviews`) are empty. | Interpretations linked to the articles they read differently; "text unchanged, reading changed" treated as its own kind of change. |
| Regional law | Schema exists; all `regional_*` tables are empty. `search-regional-law` returns nothing; `get-regional-koap-article` fails on a schema mismatch. | Regional adapters after the federal history layer works. |
| Search | Keyword search over PostgreSQL trigrams works. Semantic/hybrid search is **not** implemented: 265 test vectors exist in Qdrant, no tool reads them, `use_hybrid` is ignored. | Hybrid search where version selection is symbolic (by date and identifier) and embeddings only rank within the selected version. |
| MCP tools | 13 registered, 10 return correct results, 2 return empty (no data), 1 errors (`get-regional-koap-article`). Input schemas are declared but not enforced. | Every tool validates input, refuses honestly when data is missing, and returns provenance with every answer. |
| Caching | Redis is provisioned in docker-compose but **not used** by the server. | Either used or removed. |
| Identifiers | Private vocabulary: `code_id` (`GK_RF`, `UK_RF`, …) + article number. Not resolvable outside law7. | ELI/Akoma Ntoso-style canonical URIs with a point-in-time slot; Akoma Ntoso export. |
| Tests and CI | 227 Python tests collected, 50 fail (mocks target modules that became compatibility shims); 104 TypeScript tests, 6 fail; `tsc` reports 30 type errors in test files. CI workflow added 2026-09-14, known failures marked non-blocking. | Green CI on every commit; a schema test that fails when a documented number drifts from the database. |
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
