# Similar Projects, Standards and Prior Art for law7

**Date:** 2026-09-14
**Audience:** project owner and AI agents working on law7
**Status:** research snapshot, not a roadmap

## 1. Method and TL;DR

Five web-research passes were run on 2026-09-14 (three primary, two sub-passes):

1. Open-source "law as git" / consolidated-law projects worldwide.
2. Legal MCP servers, RAG assistants and agent-facing legal APIs (worldwide + Russia).
3. Standards and data models, government point-in-time (PIT) services.
4. Academic landscape 2022–2026: consolidation automation, temporal models, temporal legal QA benchmarks, hallucination and currency studies (24 searches, 20 primary fetches).
5. Decentralized and cryptographically verifiable law (~89 fetches).

Every GitHub project cited was checked live against the GitHub REST API on 2026-09-14; "last activity" is `pushed_at` on the default branch. Government services and standards were checked against their own sites. "Dead" = no push in more than two years. Anything that could not be confirmed is marked **(unverified)**. Nothing in this document is carried over from older law7 docs; the law7 numbers below were measured on 2026-09-14 against the live database.

**law7 as measured today:** 1,136,605 documents crawled from pravo.gov.ru (snapshot dated 2026-02-11), 47,871 of them with full text, 22 consolidated codes holding 6,232 article versions, `amendment_applications` **empty** (the consolidation engine has never been run against real data), 265 test vectors in Qdrant, 13 MCP tools of which 10 work, Russia only, AGPL-3.0, development paused Feb–Sep 2026.

**law7's six design claims**, used as the comparison axes throughout:

| # | Claim |
|---|---|
| 1 | **PIT** — point-in-time article versions (text as in force on date D) |
| 2 | **Chain** — amendment chain: who/when/what changed, queryable |
| 3 | **Hash** — hash provenance against the official source artifact |
| 4 | **Multi** — multi-country adapters |
| 5 | **Decentral** — decentralized/federated distribution with verification (transport-neutral; not tied to any specific P2P product) |
| 6 | **AI-API** — AI-agent API (MCP) |

Legend in tables: ✓ = present and working, ◐ = partial / claimed / inherited from an upstream source, ✗ = absent.

---

### TL;DR (RU)

- Из шести заявленных свойств law7 четыре уже реализованы другими: PIT-версии статей и MCP-доступ — массово, цепочка поправок и мультиюрисдикционность — на уровне стандартов (Akoma Ntoso, ELI) и госсервисов (UK, Канада, Италия, Франция).
- Хеш-провенанс — **уже реализован один раз**: Кодекс округа Колумбия ([DCCouncil/law](https://github.com/DCCouncil/law)) заверен через TAF/TUF от Open Law Library (AGPL-3.0, подписанный хеш-манифест поверх git, живые коммиты 11.09.2026), юридическая основа — UELMA. Эстония хеширует Riigi Teataja через KSI, но это внутренняя проверка, публичного верификатора не найдено. Не занято: провенанс, **протянутый через консолидацию**, и такой манифест в **любой** юрисдикции ЕС/Великобритании/России. Sigstore/Rekor и IPFS к законодательству не применялись никогда.
- Но в самом law7 эти свойства не реализованы: `text_hash` в схеме — это хеш *производного текста* для сравнения, а не хеш официального PDF/контрольного экземпляра; таблица `amendment_applications` пуста, движок консолидации ни разу не запускался на реальных данных.
- Ближайшие аналоги: **lex-corpus (SFHAJJI)** — SHA-256 + подписанный манифест + MCP; **Legalize.dev** — 32 страны, зрелый продукт; **LawVM** — пересчёт консолидации из текстов поправок, нашёл реальную ошибку в официальной базе Эстонии; **korean-law-mcp** (2581★) — «право на дату» через официальный портал.
- По России: открытой, проверяемой, point-in-time базы законодательства **не существует** — ни государственной, ни открытой. `actual.pravo.gov.ru` даёт только текущую редакцию и только по изменениям после 01.07.2022, без API. «Машина времени» есть только у Гаранта/КонсультантПлюс, платно и без API.
- Сильнейший аргумент спроса — не «git для законов» (эта ниша занята: Канада публикует свод законов прямо в git), а **«temporal misgrounding»**: статья arXiv 2605.23497 (2026) прямо пишет, что для исследования этой проблемы нужны исторические датированные консолидированные тексты — и их нет. Stanford RegLab: 58-88% галлюцинаций у LLM, 17-33% даже у Lexis+ AI и Westlaw с RAG.
- Рекомендация в одну строку: перестать защищать пункты 1, 2, 4, 6 как новизну, перейти на ELI/Akoma Ntoso как схему идентификаторов и экспорта, закрыть пункт 3 в его узкой части (хеш источника + манифест через консолидацию) и переписать позиционирование на устранение temporal misgrounding для LLM.

### TL;DR (EN)

- Of law7's six claims, four are already occupied: PIT article versions and MCP access are widespread; amendment chains and multi-jurisdiction design exist in stronger form as standards (Akoma Ntoso, ELI) and as production government services (UK, Canada, Italy, France, NZ, Australia).
- Hash provenance is **precedented, not unprecedented**: a cryptographically verifiable statute book exists — the DC Council's [DCCouncil/law](https://github.com/DCCouncil/law), authenticated with Open Law Library's [TAF](https://github.com/openlawlibrary/taf) (TUF signed hash manifest over git, AGPL-3.0, live commits 2026-09-11), driven by UELMA. Estonia's KSI hash-chaining of Riigi Teataja is internal with no public verifier found. What is still absent: provenance carried **through consolidation**, and any such manifest in **any EU, UK or Russian jurisdiction**. Sigstore/Rekor, Trillian/CT and IPFS have never been applied to law.
- law7 does not currently implement either of those. The schema's `text_hash` columns are annotated "for change detection" — a hash of derived text, not of the official artifact — and `amendment_applications` is empty.
- Closest analogues: **lex-corpus/lex** (SHA-256 + signed manifest + MCP), **Legalize.dev** (32 countries, mature product), **LawVM** (replays amendment acts, already caught a confirmed bug in Estonia's official consolidation), **korean-law-mcp** (2,581★, official-source time travel).
- For Russia: no free, machine-readable, point-in-time, hash-verified statute database exists — official, commercial-open, or open source. That gap is real and is law7's actual differentiator.
- The strongest demand-side argument is not "git for laws" (that niche is occupied — Canada publishes its statute book in git) but **temporal misgrounding**: the 2026 paper [arXiv 2605.23497](https://arxiv.org/pdf/2605.23497) states that studying it "required historical time-stamped consolidated versions of statutory law" and that this resource was lacking. Stanford RegLab measured 58-88% hallucination in raw LLMs and 17-33% even in Lexis+ AI and Westlaw's RAG products.
- The market shifted under law7 while it was paused: Anthropic's "Claude for Legal" (May 2026), MCP donated to the Agentic AI Foundation (Dec 2025), and a wave of per-country legislation MCP servers built Mar–Sep 2026. Shipping an MCP server is now table stakes, not differentiation.

---

## 2. Landscape

Claim columns are scored *for that project*, not for law7.

| Project / service | Jurisdiction | Type | License | Last activity | Alive? | PIT | Chain | Hash | Multi | Decentral | AI-API |
|---|---|---|---|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| **law7** (baseline, measured) — [mikhashev/law7](https://github.com/mikhashev/law7) | Russia | OSS project | AGPL-3.0 | paused Feb 2026 | Paused | ◐ (6,232 art. versions, 22 codes) | ✗ (`amendment_applications` empty) | ✗ (hashes are for diffing only) | ✗ (design only) | ✗ (design only) | ✓ (13 tools, 10 work) |
| [DCCouncil/law](https://github.com/DCCouncil/law) + [openlawlibrary/taf](https://github.com/openlawlibrary/taf) | Washington DC, USA | Gov service + OSS tooling | TAF: AGPL-3.0 | law: 2026-09-11 (`oll-bot`); taf: 2026-09-12 | Alive | ✓ | ✓ (enactments as commits) | ✓ (**TUF signed hash manifest over git**: root/targets/snapshot/timestamp, SHA-256+SHA-512 per target) | ✗ | ◐ (updater validates before cloning; anyone can mirror and verify) | ✗ |
| [legalize-dev/legalize](https://github.com/legalize-dev/legalize) · [legalize.dev](https://legalize.dev) | 32 countries (31 per SPEC) | OSS project + API | MIT (tooling); content public domain | 2026-08-28 (`legalize-es` 2026-09-11) | Alive, very active | ✓ | ✓ | ✗ (`SPEC.md` v0.4 has **no hash/checksum/signature field**; "commit SHAs" verify against its own repo only) | ✓ | ✗ | ✓ ([legalize-dev/mcp](https://github.com/legalize-dev/mcp)) |
| [SFHAJJI/lex](https://github.com/SFHAJJI/lex) · [lex-corpus-lu-legilux](https://github.com/SFHAJJI/lex-corpus-lu-legilux) · [lex-corpus-eu-eurlex](https://github.com/SFHAJJI/lex-corpus-eu-eurlex) | Luxembourg + EU | OSS project | CC-BY-4.0 (content); code license TBC | 2026-08-26 → 2026-09-14 | Alive, very active | ✓ | ✓ | ✓ (SHA-256 + signed manifest) | ◐ (one repo per country, growing) | ◐ (git copies, no verification network) | ✓ |
| [eliask/lawvm](https://github.com/eliask/lawvm) | Finland (ref.) + EE/UK/NO/SE/EU/US | OSS research preview | check repo **(unverified)** | 2026-07-12 | Alive (alpha) | ✓ | ✓ (typed amendment ops + lineage) | ✓ (replay-vs-witness evidence) | ◐ | ✗ | ✗ |
| [chrisryugj/korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp) | South Korea | OSS project | MIT | 2026-09-12 (2,581★) | Alive, most-adopted legal MCP found | ✓ (`time_travel`, 행위시법) | ✓ (신구대조표) | ◐ (citation check, not crypto) | ✗ | ✗ | ✓ |
| [jonashertner/opencaselaw](https://github.com/jonashertner/opencaselaw) · [mcp.opencaselaw.ch](https://mcp.opencaselaw.ch) | Switzerland (case law) | OSS project | Code MIT / data CC0 | 2026-09-13 | Alive | ✗ (nightly index swaps) | ✗ | ✓ (MD5 `content_hash` + canonical_key) | ✗ | ✗ | ✓ (42 tools) |
| [matematicsolutions/it-eli-mcp](https://github.com/matematicsolutions/it-eli-mcp) + ~30 siblings | ~30 countries via ELI portals | OSS project (network) | check per-repo **(unverified)** | 2026-08-24 → 2026-09-08 | Alive | ◐ (inherits source PIT) | ◐ | ◐ (ELI URNs) | ✓ | ◐ | ✓ |
| [Ansvar-Systems](https://github.com/Ansvar-Systems) `*-law-mcp` (~30 repos) | EU + UK | OSS project (network, commercial-leaning) | Apache-2.0 | 2026-07-07 / 2026-07-22 (templated batch) | Alive but low organic activity | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| [leyabierta/leyabierta](https://github.com/leyabierta/leyabierta) | Spain (national + 17 CCAA) | OSS project | AGPL-3.0 (code) | 2026-09-09 | Alive | ✓ | ✓ (one commit per reform) | ✗ | ✗ | ✗ | ✗ |
| [AlsKozlov/ru-legal](https://github.com/AlsKozlov/ru-legal) | Russia | OSS project | Apache-2.0 | 2026-05-26 (30★) | Alive | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (8 MCP servers, 145 skills) |
| [shodenis/Russian-Law-MCP](https://github.com/shodenis/Russian-Law-MCP) | Russia | OSS project | Apache-2.0 | 2026-03-30 (2★) | Barely | ◐ **(unverified)** | ✗ | ✗ | ✗ | ✗ | ✓ |
| [irlcode/RusLawOD](https://github.com/irlcode/RusLawOD) · [HF dataset](https://huggingface.co/datasets/irlspbru/RusLawOD) | Russia | Dataset (academic) | MIT/Other | 2026-09-06 (70★) | Alive | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| [justicedao/ipfs_russia_laws_ir](https://huggingface.co/datasets/justicedao/ipfs_russia_laws_ir) | Russia (+ series) | Dataset | unspecified | unclear **(unverified)** | Unclear | ✗ | ✗ | ◐ (IPFS content addressing) | ◐ (sibling per-country sets) | ◐ (IPFS) | ✗ |
| [legislation.gov.uk](https://www.legislation.gov.uk) · [github.com/legislation](https://github.com/legislation) | UK | Gov service | OGL v3.0 | ongoing | Alive | ✓ (best-in-class; dated URIs) | ✓ ("effects" dataset, typed) | ◐ (canonical URIs, no hashes) | ✗ | ✗ | ◐ (3rd-party MCP wrappers) |
| [Justice Laws / laws-lois-xml](https://github.com/justicecanada/laws-lois-xml) | Canada | Gov service + dataset (git) | Gov of Canada open | ongoing (~fortnightly) | Alive | ✓ (PIT bulk XML from 2003) | ✓ (amendment notes) | ◐ | ✗ | ✗ | ✗ |
| [Normattiva](https://www.normattiva.it) · [dati.normattiva.it](https://dati.normattiva.it) | Italy | Gov service | open data | ongoing | Alive | ✓ ("multivigenza") | ✓ | ◐ (URN:NIR + ELI) | ◐ (AKN+ELI adopted) | ✗ | ◐ (via eli-mcp) |
| [Fedlex](https://fedlex.data.admin.ch/) | Switzerland | Gov service | open reuse | ongoing | Alive | ✓ | ✓ (JOLux relations) | ◐ (ELI/RS URIs) | ◐ (ELI, JOLux shared with LU) | ✗ | ◐ (3rd-party MCPs) |
| [Légifrance / LEGI](https://www.legifrance.gouv.fr) · [bulk dump](https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides) | France | Gov service | Etalab OL 2.0 | ongoing | Alive | ✓ (article statuses + dates) | ✓ | ◐ (ELI) | ✗ | ✗ | ◐ (mcp-legifrance, JusticeLibre) |
| [EUR-Lex / CELLAR](https://eur-lex.europa.eu) | EU | Gov service | open reuse | ongoing | Alive | ✓ | ✓ (CELEX graph, ELI props) | ◐ (eIDAS-signed OJ PDFs; no hash manifest) | ✓ (EU-wide) | ✗ | ◐ (eur-lex MCPs) |
| [Federal Register of Legislation](https://www.legislation.gov.au) | Australia | Gov service | Cth open | ongoing | Alive | ✓ ("compilations") | ✓ (endnotes) | ◐ (legally authoritative register) | ✗ | ✗ | ◐ ([australian-law-mcp](https://github.com/ChangkeunJ/australian-law-mcp), 2026-09-12) |
| [NZ Legislation API](https://api.legislation.govt.nz/docs/) | New Zealand | Gov service | Crown | ongoing | Alive | ✓ ("as at" versions) | ✓ | ◐ | ✗ | ✗ | ✗ |
| [publication.pravo.gov.ru](http://publication.pravo.gov.ru) | Russia | Gov service | open data section | ongoing | Alive | ✗ (publication of record only) | ✗ | ◐ (PDFs are unsigned raster scans, but a detached CAdES-BES/GOST signature over the PDF bytes is served at `/file/sig?eoNumber=` for regional documents — 30/31 sampled, verified in pure Python; federal documents return 404 — 0/12; see audit RECON −1.1b) | ✗ | ✗ | ◐ ([mcpgate.ru/servers/pravo](https://mcpgate.ru/servers/pravo), key-gated) |
| [actual.pravo.gov.ru](http://actual.pravo.gov.ru/) | Russia | Gov service | — | ongoing | Alive | ◐ (current text only, changes after 2022-07-01) | ✗ | ◐ (officially authoritative since 2022) | ✗ | ✗ | ✗ (no documented API) |
| [КонсультантПлюс](https://www.consultant.ru) · [Гарант](https://www.garant.ru) · [Кодекс](https://kodeks.ru/) | Russia | Commercial | proprietary | ongoing | Alive | ✓ (Гарант "машина времени") | ✓ (full редакция chains) | ✗ (editorial, no crypto link to source) | ✗ | ✗ | ✗ (no public API; Гарант reachable only via BotHub resale) |
| [Akoma Ntoso / OASIS LegalDocML](https://www.oasis-open.org/standard/akn-v1-0/) | — | Standard | OASIS | v1.0 (2018); revision slated ~Jul 2026 **(unverified whether approved)** | Current | ✓ (`FRBRExpression`, `temporalGroup`) | ✓ (`activeModifications`/`passiveModifications`, `textualMod`) | ◐ (defers to XML-DSig; no hash manifest) | ✓ | ✗ | n/a |
| [ELI](https://op.europa.eu/en/web/eu-vocabularies/eli) | — | Standard | EU | ontology v1.4 | Current | ✓ (`version_date`, PIT URI slot) | ✓ (`amends`/`amended_by`/`consolidates`) | ◐ (canonical IDs only, no hash vocabulary) | ✓ (25+ implementers) | ✗ | ◐ (RDFa/JSON-LD + SPARQL) |
| [bundestag/gesetze](https://github.com/bundestag/gesetze) (org name squatted by activist Stefan Wehrmeyer — **not the parliament**) | Germany | OSS dataset | mixed | data repo **2022-11-25** (tools 2026-05-04) | Data mirror stalled | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| [Legilibre/Archeo-Lex](https://github.com/Legilibre/Archeo-Lex) | France | OSS project | WTFPL | **2019-03-10** | **Dead** | ✓ (was) | ✓ (was) | ✗ | ✗ | ✗ | ✗ |

---

## 3. Closest analogues to law7

### [Legalize.dev](https://legalize.dev) — [legalize-dev/legalize](https://github.com/legalize-dev/legalize)

A Python pipeline that converts official legislation into per-country Git repositories under the slogan "every law a file, every reform a commit", plus a REST API (free and paid tiers) and an official MCP connector. 32 countries; the Spanish repo alone has 1,908 stars. Pushed 2026-08-28, with `legalize-es` as recent as 2026-09-11. Tooling is MIT, content is public domain.

**Has that law7 lacks:** working scale (32 jurisdictions vs 1), a shipped hosted API and MCP connector with real users, and an actually-populated amendment history. **law7 has that it lacks:** nothing on features — but Legalize's own disclaimer says its reproduction of official text is "automated… not verified", with no cryptographic hash. Its architecture is a single centralized pipeline run by one org, so there is no decentralization or independent-verification story at all. law7's claims 3 and 5, if implemented, would be genuinely differentiating against it. Also: Legalize does not cover Russia.

### [lex-corpus / lex](https://github.com/SFHAJJI/lex) (SFHAJJI)

The single closest match to law7's *combined* six claims. Archives every consolidated version of a law as verbatim files plus a dated `meta.json`, SHA-256-hashes the content, and publishes a canonical manifest signed via Azure Key Vault; the stated philosophy is "the tree is the legislative history". Has an MCP endpoint. Active 2026-08-26 through 2026-09-14. Content CC-BY-4.0; repo code license TBC **(unverified)**.

**Has that law7 lacks:** exactly the thing law7 calls its strongest differentiator — SHA-256 content hashing with a cryptographically signed manifest — already shipped and running, alongside PIT, chain, and MCP. **law7 has that it lacks:** depth and scale in a jurisdiction lex-corpus does not touch. lex-corpus is young (first commit Aug 2026) and currently only deep on Luxembourg and EU/EUR-Lex, both jurisdictions whose official sources already publish consolidated PIT text — i.e. it is archiving an existing consolidation, not computing one. law7's harder problem (Russia has no PIT source to archive) is not one lex-corpus has solved. Note also that a signed manifest is not the same as an append-only public log: the signer is still a single trusted party.

### [LawVM](https://github.com/eliask/lawvm)

A research-preview "legal virtual machine": it compiles human-written amendment acts into typed operations and replays them to produce auditable point-in-time legal text-state, carrying evidence and provenance for each step. It has already found — and had confirmed — a real consolidation bug in Estonia's official Riigi Teataja. Finland is the reference frontend; Estonia, UK, Norway, Sweden, EU and US exist at varying maturity. Last push 2026-07-12. License **(unverified)**.

**Has that law7 lacks:** the amendment-chain claim actually working, and the strongest possible proof of it — divergence between its replay and the official witness text, surfaced as a finding. This is precisely the "verify against the official source" value proposition law7 described but never ran. **law7 has that it lacks:** a production data pipeline at corpus scale (1.1M documents crawled), an MCP interface, and a Russian frontend. LawVM is alpha and CLI/Python-only.

### [korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp)

By a wide margin the most adopted legal MCP server found anywhere: 2,581 stars, 522 forks, MIT, v4.13.0, Docker support, actively pushed 2026-09-12 — built by a single local-government official. Wraps 42 official Korean government APIs (법제처 국가법령정보센터) into 10 MCP tools, including explicit "law in force at the time of the act" (행위시법) semantics, a `time_travel` date-comparison tool, amendment tracking and old/new comparison tables (신구대조표).

**Has that law7 lacks:** proof that the "official source + MCP + point-in-time" product shape gets real adoption, and a far better tool surface for temporal queries. **law7 has that it lacks:** nothing technical — except that korean-law-mcp is a thin client over a government portal that already publishes point-in-time law. Korea's 법제처 does the consolidation; law7 would have to do it itself, because Russia's does not. It also has no article-level hash or tamper-evidence.

### [opencaselaw](https://github.com/jonashertner/opencaselaw)

Swiss case law: 1M+ court decisions from 118 official court sites plus Fedlex SPARQL, 21k laws, a 10M-edge citation graph, 42 MCP tools, live at `mcp.opencaselaw.ch`. Code MIT, data CC0, pushed 2026-09-13. Each decision carries an MD5 `content_hash` and a `canonical_key`, and it ships a five-rail citation-auditing tool (`attest_response`) that checks existence, quote fidelity, date and grounding.

**Has that law7 lacks:** a deployed integrity layer — per-document content hashing plus an agent-facing verification tool that catches hallucinated citations. That is the operational form of law7's claim 3. **law7 has that it lacks:** legislative version history. opencaselaw does nightly full-index swaps with no per-decision rollback and no article-level temporal model. The emphases are opposite and complementary: opencaselaw is strong on provenance and weak on time; law7's design is the reverse (and currently weak on both in practice).

### Per-country ELI MCP networks — [matematicsolutions](https://github.com/matematicsolutions/it-eli-mcp) and [Ansvar-Systems](https://github.com/Ansvar-Systems)

Two "one MCP server per country" fleets. matematicsolutions ships ~30 keyless servers (`it-eli-mcp`, `de-eli-mcp`, `fr-eli-mcp`, `us-eli-mcp`, `ch-eli-mcp`, [`gb-eli-mcp`](https://glama.ai/mcp/servers/matematicsolutions/gb-eli-mcp), …) wrapping each country's own ELI/Akoma-Ntoso register — including Italy's multivigenza. Ansvar-Systems ships ~30 templated `*-law-mcp` servers (Apache-2.0) over official portals like gesetze-im-internet.de, legislation.gov.uk, Legifrance and wetten.overheid.nl; most were batch-pushed on 2026-07-07 / 2026-07-22 with little organic activity since, and star counts are mostly 0–20.

**Have that law7 lacks:** claim 4 (multi-country) actually delivered, as ~30 live connectors each. **law7 has that they lack:** any datastore of its own. These are thin passthroughs that inherit whatever the official source offers; none builds a consolidation engine, none documents article-level historical snapshots, none computes hashes. They work only where the government already publishes PIT law — which is exactly why the pattern does not transfer to Russia. One notable data point: Ansvar's `@ansvar/russian-law-mcp` exists on npm (Apache-2.0, v0.1.0, ~3 months old, claiming 12,369 federal statutes / 77,647 provisions ingested from pravo.gov.ru + RusLawOD), but its GitHub repo returned 404 on 2026-09-14 while all ~30 siblings are public — so its code and claims are currently unauditable **(unverified)**.

### [AlsKozlov/ru-legal](https://github.com/AlsKozlov/ru-legal)

The most complete and most active Russian open-source analogue: 30 stars, 5 forks, Apache-2.0, pushed 2026-05-26. 145 AI "skills" (Markdown/YAML, ported from Anthropic's own claude-for-legal) plus 8 MCP servers covering pravo.gov.ru, ЕГРЮЛ/ФНС, kad.arbitr.ru, ЕФРСБ/Федресурс, Роспатент/ФИПС, госзакупки and Росреестр, with an aggregator server on top. Six of eight need no API key. Same author publishes [legalbench-ru](https://huggingface.co/datasets/AlsKozlov/legalbench-ru).

**Has that law7 lacks:** breadth across Russian registries (company records, arbitration case law, insolvency, patents, procurement, cadastre — none of which law7 touches), a skills layer, and actual recent momentum. **law7 has that it lacks:** depth in time. ru-legal is a passthrough with no point-in-time mechanism, no version history and no hash provenance. It answers "what does the law say now" across many registries; law7's design answers "what did this article say on date D" in one. They are complementary, not substitutes — and ru-legal is the most plausible integration partner or reference implementation in the Russian ecosystem.

---

## 4. Russia specifically

### Official

| Service | What it gives | Gaps |
|---|---|---|
| [publication.pravo.gov.ru](http://publication.pravo.gov.ru) ([API help](http://publication.pravo.gov.ru/help), [Open Data](http://publication.pravo.gov.ru/OpenData)) | Official publication of record: signed electronic images of control copies ("контрольные экземпляры"), FSO-operated. Read-only REST API (publication blocks, document lists, PDFs). Open Data section explicitly permits reuse including in software. Third-party catalogue: [data.apicrafter.ru](https://data.apicrafter.ru/packages/pubpravogovru) | **No point-in-time at all** — it publishes acts as published, not consolidated text. No documented public hash/signature verification endpoint. |
| [actual.pravo.gov.ru](http://actual.pravo.gov.ru/) ([content list](http://www.actual.pravo.gov.ru/content/content.html)) | Consolidated текущая редакция, officially authoritative since 2022 (see [ГАРАНТ note](https://www.garant.ru/news/1531144/)); prepared by НТЦ «Система» ФСО and УОПИ Спецсвязи ФСО | **Current text only, and only for amendments made after 2022-07-01.** No historical redaction-on-date browsing. **No documented public API.** This post-2022 window is the single most important fact about Russian official PIT data. |
| [ips.pravo.gov.ru](http://pravo.gov.ru/ips/) | ИПС «Законодательство России»: full-text bank from 1917, texts carry official status | Redaction handling weak and opaque. Export to DOC/Word/DOS only. **No API.** |
| [sozd.duma.gov.ru](https://sozd.duma.gov.ru) + [api.duma.gov.ru](http://api.duma.gov.ru/) ([docs](http://api.duma.gov.ru/pages/dokumentatsiya/spravochnik-po-api)) | Bill cards with full legislative lifecycle stages, bill → adopted FZ linkage. **Open REST API with key.** | Bills, not consolidated text. But this is *the* source of amendment provenance in Russia — the who/when half of claim 2. |

### Commercial

[КонсультантПлюс](https://www.consultant.ru), [Гарант](https://www.garant.ru) and [Кодекс/Техэксперт](https://kodeks.ru/) all have mature editorial consolidation: Гарант ships a "машина времени" (document as at any date) plus [visual redaction comparison](https://www.garant.ru/products/solution/sravnenie/); КонсультантПлюс has "Сравнить редакции". All three have full редакция chains with amending-act links. All three are proprietary, editorially produced, **not** cryptographically linked to the official source, and **have no public API**. AI products on top: Гарант «Искра» (closed beta), [BotHub «Нейроюрист»](https://bothub.chat) reselling Гарант's official API, Yandex «Нейроюрист» (B2B Tech, Nov 2025), Sber «GigaLegal», ExplainLaw. No КонсультантПлюс MCP server, connector or public agent API was found.

### Open source and datasets

- [AlsKozlov/ru-legal](https://github.com/AlsKozlov/ru-legal) — 8 MCP servers over official registries; no PIT, no hash.
- [shodenis/Russian-Law-MCP](https://github.com/shodenis/Russian-Law-MCP) — claims 100% federal coverage from pravo.gov.ru; 2 stars, one commit burst, nothing since 2026-03-30; claims undocumented **(unverified)**.
- `@ansvar/russian-law-mcp` on npm — source repo 404s **(unverified)**.
- [«Портал правовой информации» (Союзтелеком)](https://mcpgate.ru/servers/pravo) — live pravo.gov.ru MCP, © 2025, API-key gated, no evidence of PIT support.
- [irlcode/RusLawOD](https://github.com/irlcode/RusLawOD) — 70★, ~304k federal act texts 1991–2025 with CoNLL-U NLP annotations, pushed 2026-09-06, actively maintained and widely reused. A static corpus: no versioning, no consolidation, no hash verification.
- [justicedao/ipfs_russia_laws_ir](https://huggingface.co/datasets/justicedao/ipfs_russia_laws_ir) — IPFS-addressed corpus, part of a multi-country `ipfs_*_laws_ir` series. IPFS content addressing gives implicit hashing and immutability, making this the only thing found anywhere that touches law7's decentralized-verifiability ambition — but it is a raw dataset with no agent-facing layer, and its provenance and freshness are unclear **(unverified)**.
- Other RU activity is RAG assistants, not consolidation: [DrobyshevDev/praxis](https://github.com/DrobyshevDev/praxis) (NLI citation verification, pushed today), [kobzevvv/legal-ai-platform](https://github.com/kobzevvv/legal-ai-platform) (11 codexes, 4,741 articles, dormant since 2026-02-25), [gitmaxlla/jurask](https://github.com/gitmaxlla/jurask) (dormant since 2025-05-15), [leadpioneer/russianlawbattle](https://github.com/leadpioneer/russianlawbattle) (multi-agent debate simulator calling a `pravo-mcp` for citation verification), [atomno-mcp/mcp-sudact](https://github.com/atomno-mcp/mcp-sudact) (court case law via a hosted paid backend).

### Finding

**No open-source, point-in-time, hash-verified consolidated Russian law database exists besides law7.** The official services give either publication-of-record without consolidation, or consolidation without history and without an API. The commercial consolidators give history without an API and without a verifiable link to the source. The open-source projects give agent access without history. The gap law7 targets is real, it is Russia-shaped, and as of 2026-09-14 nobody else is in it.

Legal caveat to check before bulk redistribution: Russian law excludes texts of legal acts from copyright, so redistributing the texts is permissible, but wholesale copying of a *compiled database* can implicate database-maker (`sui generis`) rights **(unverified — not legal advice; verify with counsel)**.

---

## 5. Standards law7 should adopt or map to

The entire mature landscape has converged on **FRBR** (Work / Expression / Manifestation / Item) as the model for point-in-time law. law7's `code_id` + `article_number` + `version_date` is an ad-hoc re-derivation of Work/Expression with a private vocabulary.

### FRBR levels

`FRBRWork` = the abstract act ("Гражданский кодекс РФ, часть 1"). `FRBRExpression` = a specific version in a language — **this is where point-in-time lives**. `FRBRManifestation` = a format (XML, PDF, HTML). `FRBRItem` = a specific copy. law7 conflates Work and Expression under `code_id`, and has no concept of Manifestation or Item — which is exactly why it has nowhere to hang the hash of the official PDF.

### [ELI](https://op.europa.eu/en/web/eu-vocabularies/eli) — European Legislation Identifier

Four pillars: a templated self-describing HTTP URI (jurisdiction / agent / year / natural identifier / **point in time** / version / language / format), an [OWL ontology](https://data.europa.eu/eli/ontology) (v1.4), publication by embedding RDFa or JSON-LD inside the law's own HTML page, and harvesting. `eli:LegalExpression` carries `version`, `version_date`, `first_date_entry_in_force`, `date_no_longer_in_force`, `in_force`. Amendment relations: `eli:changes`/`changed_by`, `amends`/`amended_by`, `repeals`/`repealed_by`, `consolidates`/`consolidated_by`, `corrects`. ~25+ implementers including EUR-Lex, France, Italy, Luxembourg, Switzerland, Ireland, Denmark, Spain, Portugal, Finland, Norway, Greece.

**What it solves that `code_id` does not:** resolvable, globally unique, jurisdiction-scoped identifiers that other systems can dereference and cite. `GK_RF` means nothing outside law7's own database; an ELI-style URI with a point-in-time slot is a citation anyone can resolve. This is also the prerequisite for claim 4 — you cannot federate on a private vocabulary.

### [Akoma Ntoso / OASIS LegalDocML](https://www.oasis-open.org/standard/akn-v1-0/)

OASIS Standard v1.0, approved 2018-08-29, still current; a revision was slated for approval around end of July 2026 **(unverified whether it was approved)**. [Naming Convention v1.0](https://docs.oasis-open.org/legaldocml/akn-nc/v1.0/akn-nc-v1.0.html); [XSD repo](https://github.com/oasis-open/legaldocml-akomantoso).

- `<temporalData>` holds `<temporalGroup>` elements of `<timeInterval>`; any body element can carry `@period` — so **one XML file can carry multiple coexisting versions of individual articles, each valid over a declared interval.** `@contains` declares `originalVersion` | `singleVersion` | `multipleVersions`.
- `<lifecycle>` lists `<eventRef>` entries, each with a date, a type, and a **required identifier of the instrument responsible**.
- `<analysis>` carries `<activeModifications>` (what this act does to others) and `<passiveModifications>` (what others did to it), with `textualMod` (`@type` = insertion / substitution / repeal / renumbering), `meaningMod`, `scopeMod`, `forceMod`, `efficacyMod`, `legalSystemMod` — each with `<source>`, `<destination>`, `<old>`/`<new>` quoted text, and `<force>`/`<efficacy>` periods.

**What it solves that law7's scheme does not:** `amendment_applications` records *that* an amendment was applied; AKN records *what kind* of modification, to *which* provision, with the exact old and new text. That is the difference between an audit row and a reversible, auditable, replayable consolidation. ELI and AKN are complementary — ELI identifies and describes at document level, AKN structures the internals; there is a published [mapping between the two ontologies](https://dl.acm.org/doi/fullHtml/10.1145/3614321.3614327).

### What neither solves

**No legislation standard defines a content-integrity primitive.** AKN mentions XML-DSig in passing; ELI has no hash or signature vocabulary; CLML, USLM and JOLux have none. Official gazettes rely on eIDAS qualified e-signatures on the published PDF (EU OJ authentic since 2013 under Reg. 216/2013; German BGBl. electronic since 2023; Austria RIS; France JORF) — signature of the *manifestation*, never a hash manifest of the corpus, never a transparency log.

### Concrete recommendation

1. Keep PostgreSQL as storage. Do not rewrite the pipeline around XML.
2. Add an **ELI-style canonical URI** as a first-class column alongside `code_id`, with a resolver endpoint. Cost: a naming convention plus a route. Payoff: citable identifiers and a path to claim 4.
3. Add an **Akoma Ntoso export format** (`data.akn`) for codes and article versions, mirroring what legislation.gov.uk does with CLML→AKN. Cost: one serializer. Payoff: law7's output becomes consumable by existing legal tooling without anyone integrating law7's private schema.
4. Restructure `amendment_applications` to carry `textualMod`-shaped rows: modification type, source instrument, destination provision, old text, new text, force/efficacy periods. Do this **before** first running the consolidation engine on real data, not after.
5. Adopt legislation.gov.uk's **effect vocabulary** (words substituted / inserted / repealed / restricted / applied with modifications — roughly 20 types) instead of the current three-way additions/repeals/modifications split.
6. Publish the **"effects not yet applied" backlog** per code, as legislation.gov.uk does. A silent consolidation is worse than no consolidation for legal use.
7. For claims 3 and 5 there are two proven, transport-neutral implementation paths, neither requiring a blockchain:
   - **[TAF / TUF](https://github.com/openlawlibrary/taf)** ([spec](https://github.com/openlawlibrary/taf/blob/master/specification/taf-spec.md)) — AGPL-3.0, the same licence as law7, and designed for precisely "git repos of law + signed hash manifest + safe updater". It is in production on the DC Code. This is the **shortest path**: the design problem is already solved and the reference implementation is licence-compatible.
   - **[Sigstore Rekor](https://github.com/sigstore/rekor)** (v2 GA October 2025, tile-based [Trillian-Tessera](https://github.com/transparency-dev/trillian-tessera)) plus `rekor-monitor` for the independent-auditor role — append-only, cheap to mirror, no single trusted signer. Nobody has applied it to law; transparency.dev explicitly pitches this use case.
   Anchor either to the pravo.gov.ru control-copy image as published (the portal states it is signed via its own CA at [pravo.gov.ru/uc/](https://pravo.gov.ru/uc/), but our 2026-09-14 probe found no embedded signature in 220 PDFs and no signature field in the API — record `artifact_type: pdf_scan_of_control_copy`, `signature: not_observed` until a detached signature or viewer endpoint is found). Do **not** build on a blockchain, and do not cite "government blockchain law" precedents: Georgia's NAPR (Bitfury/Exonum 2016, Hedera MoU Dec 2025) is land titles, Dubai's is property title deeds on XRPL, and China's judicial chains are evidence preservation — none is legislation.

---

## 6. Academic prior art (2022–2026)

Condensed from a dedicated sub-pass (24 searches, 20 primary fetches, 2026-09-14). This section matters because it tells law7 both how hard its core engineering problem is and what the measured demand for its output actually is.

### 6.1 Automated amendment consolidation — how good does it get?

Not very. This is the single most important calibration for law7's claim 2.

- **[Etcheverry, Real, Chavallard (Doctrine.fr), NLLP@EMNLP 2024](https://aclanthology.org/2024.nllp-1.13/)** — the first LLM-based amendment-application system: **63.2% correct, but only 49.8% of real consolidations were even processable** (context limits). Effective yield ≈ 31%.
- **[Silber, *Towards an Automatic Consolidation of French Law* (2023)](https://arxiv.org/abs/2301.06469)** — a reproducible pipeline from JORF + LEGI open data, framing consolidation as an auditable transformation. The closest published design to what law7's consolidation engine is supposed to be.
- The ITTIG-CNR line (Spinosa et al. ICAIL 2009; [TULSI, AI&Law 2012](https://link.springer.com/article/10.1007/s10506-012-9127-6)) extracts *amendment metadata* (repeal/substitute/insert) and feeds Normattiva; its xmLeges parser is used by the Italian Senate. [Fabrizi et al., CLiC-it 2021](https://aclanthology.org/2021.clicit-1.24/) classify modification types and call full consolidation "out of reach". Garofalakis/Plessas (JURIX 2016, Greek) require mandatory human confirmation. MetaVex (de Maat/Boer, JURIX 2009) named *clashing amendments* and *amendments-of-amendments* as open problems; they are still open.
- The **only public supervised dataset** is [`DoctrineAI/legal_consolidation`](https://huggingface.co/datasets/DoctrineAI/legal_consolidation) — 3,124 (article, modification, amended article) triplets, French only. No multilingual dataset, no shared task, no leaderboard.
- Every deployed system is semi-automatic. EUR-Lex states its consolidated text has ["no legal effect"](https://eur-lex.europa.eu/content/intro/collection/Methodology-on-Consolidation.pdf). Spain's BOE Legislación Consolidada publishes every intermediate version with an open API at 1–3 day latency.
- **[legislation.gov.uk publishes a backlog of ~100,000 unapplied effects](https://www.legislation.gov.uk/changes)**, applying ~10,000/yr against ~15,000/yr incoming. The best-resourced PIT service in the world is permanently losing to its own inflow.
- Unsolved classes everywhere: tables, renumbering and split/join, amendments-of-amendments, conditional or deferred commencement, implicit modifications, retroactive amendments. **No legally authoritative gold standard for consolidated text exists.**

**Implication for law7:** a fully automatic, legally reliable consolidation of the Russian codes is not achievable, and nobody has achieved it anywhere. Design for ~60% automation with a published backlog and human confirmation, not for completeness.

### 6.2 Temporal models

- [Palmirani, *Legislative Change Management with Akoma-Ntoso* (Springer 2011)](https://link.springer.com/chapter/10.1007/978-94-007-1887-6_7) is the AKN temporal model — active/passive modifications, and the three-way distinction between **in-force time, efficacy time and transaction time**. There has been no post-2019 revision of the temporal model. law7's schema has one date column where AKN has three time axes.
- The Brazilian Senate line (de Martim, 2025–2026) is the most active research directly on law7's problem: [LRMoo component-level versioning](https://arxiv.org/abs/2506.07853) (critiquing AKN for lacking constructs to formally model a *component's* diachronic version history — i.e. exactly article-level versioning); [SAT-Graph RAG, JURIX 2025](https://arxiv.org/abs/2505.00039) (legislative events as first-class nodes, causal-provenance reconstruction); **[SAT-Graph API](https://arxiv.org/abs/2510.06002) — typed deterministic primitives for LLM agents with an auditable log, which is a directly usable blueprint for law7's MCP tool design**; and [*Beyond Probabilistic Similarity*](https://arxiv.org/abs/2606.09724) on the structural, temporal and causal limits of legal RAG.
- [Zilli, Corazza, Palmirani, Sapienza, JURIX 2025](https://ebooks.iospress.nl/volume/legal-knowledge-and-information-systems-jurix-2025-the-thirty-eighth-annual-conference-turin-italy-9-11-december-2025) (doi:10.3233/FAIA251593) — agentic RAG over multilingual legislation with point-in-time filtering. [Semantic Finlex change-history KG, JURIX 2025](https://link.springer.com/chapter/10.1007/978-3-032-13109-6_18).

### 6.3 Temporal legal QA benchmarks — the field exploded May–Aug 2026

- **[Prior, Schultz, Grabmair (TUM), *Asking For An Old Friend*, ICAIL 2026](https://arxiv.org/abs/2605.23497)** — 312 expert-validated QA pairs over 6 German codes. Vanilla LLMs score 0.08–0.21 on post-cutoff questions; web search 0.25–0.67 with a recency skew; **temporal-filtered RAG 0.78–0.88**. The paper states plainly that this "requires curated, versioned statutory databases not universally available."
- **[Cymbler, Guez, Fabre, *Temporal Misgrounding in Legal RAG* (FiscalQA Pro), Aug 2026](https://arxiv.org/abs/2608.09393)** — 32,436 French tax article-versions, 1938–2031. **LLM-only 3.0%; static RAG over a current-version corpus 2.7%; a date-conditioned retriever 98.3%; oracle 99.1%.** Static RAG retrieved *a* version 100% of the time and the *date-applicable* version **0%** of the time. Root causes: article-number aliasing across versions, near-identical cross-version embeddings, parametric recency bias.
- [LexKairos (Chinese statutes)](https://arxiv.org/abs/2608.09106) — "version identifier recall remains the principal bottleneck". [Fan et al., *Can LLMs Time Travel?*](https://arxiv.org/abs/2605.25920) — Legal Article Recitation across 13 amendment versions, 2000–2025. [TIDE (Bangladesh customs, 1969–2025)](https://arxiv.org/abs/2608.08512) — "reading the correct text is necessary but not sufficient": models override supplied authoritative text with parametric priors 26.7% of the time.
- Mainstream benchmarks (LegalBench, LexGLUE, CaseHOLD, SARA, LEXAM, Harvey LAB) are temporally blind frozen snapshots. **No cross-jurisdiction point-in-time benchmark exists, and none covers Russian or any Slavic corpus.**

### 6.4 Hallucination and currency

[Dahl, Magesh, Suzgun, Ho, *Large Legal Fictions* (J. Legal Analysis 2024)](https://arxiv.org/abs/2401.01301): GPT-4 58%, GPT-3.5 69%, Llama 2 88% hallucination on verifiable legal questions. [Magesh et al., *Hallucination-Free?* (JELS 2025)](https://arxiv.org/abs/2405.20362): **17–33% hallucination in Lexis+ AI, Westlaw AI-Assisted Research and Ask Practical Law AI**, preregistered — vendor "hallucination-free" claims overstated. [Blair-Stanek et al. (SSRN 2025)](https://ssrn.com/abstract=5274547): o3 applied *Chevron* after *Loper Bright* overruled it — the clearest currency failure on record. [LegalCiteBench](https://arxiv.org/abs/2605.10186): top models score <7/100 on citation retrieval with a misleading-answer rate above 94%. [Curran et al., *Place Matters*](https://arxiv.org/abs/2511.06700): hallucination rate varies by jurisdiction, ~45% (Los Angeles) to 100% (Australian state law). [Ovcharov, *Citation Grounding* (2026)](https://arxiv.org/abs/2606.00898) builds a Ukrainian decisions graph (100.8M decisions, 21,736 statute nodes) and is the only paper with a **Citation Temporality** metric, which it calls a proxy: "full temporal-aware verification requires a versioned legislation API."

**No peer-reviewed study evaluates any commercial legal AI on currency or point-in-time correctness.** That is an open evaluation gap, and law7's corpus is the kind of thing needed to close it for Russia.

### 6.5 Cryptographic provenance — the thinnest thread in the literature

[UELMA](https://www.aallnet.org/advocacy/government-relations/state-issues/uelma-resources/) (2011, ~20 US states) requires official electronic legal material to be authenticated, preserved and accessible, but is deliberately technology-neutral. Open Law Library's whitepaper describes versioned, digitally signed publication and archival. C2PA (SHA-256 + Merkle + X.509) is mature in media. **No paper applies C2PA, a hash chain, or a transparency log to a statutory corpus.** AI&Law treats provenance as *logical* — which act produced which version — never as cryptographic.

### 6.6 The one-paragraph gap

Diagnosis is settled, infrastructure is not. Date-conditioned retrieval over a versioned corpus moves accuracy from ~3% to ~98%: **the corpus, not the model, is the bottleneck.** Embeddings cannot select versions (article-number aliasing, near-identical cross-version vectors), so **version resolution must be symbolic and metadata-driven, not semantic**. Static RAG fails silently and confidently. Consolidation automation tops out around 63% on the half of cases it can attempt, with no gold standard and a 100k-item backlog in the UK. Provenance-as-cryptography is unstudied. And the consolidation community (IT/FR/GR, 2009–2016) and the temporal-benchmark community (DE/FR/CN/BD, 2026) barely cite each other — which is itself an opening.

---

## 7. Verdict per claim

| # | Claim | Verdict | Where |
|---|---|---|---|
| 1 | **Point-in-time article versions** | **Solved in mature form**, in ≥8 jurisdictions and two standards. Novel only *within Russia*. | UK dated URIs, Canada PIT bulk XML (Acts from 2003-01-01), NZ "as at" API versions, Australian compilations, Italian multivigenza, French article statuses (`VIGUEUR`/`MODIFIE`/`ABROGE`), US release points back to 1994, EUR-Lex consolidated texts. Standardized by AKN `temporalGroup`/`FRBRExpression` and ELI `version_date`. In OSS: Legalize, Ley Abierta, lex-corpus, LawVM, korean-law-mcp. |
| 2 | **Amendment chain (who/when/what)** | **Solved as a data model; partially solved in practice; unimplemented in law7.** AKN `activeModifications`/`passiveModifications`/`textualMod` and ELI `changes`/`changed_by` are strictly richer than law7's design. UK's "effects" dataset is a production implementation. Automated *application* of amendments remains hard everywhere — LawVM is the state of the art and is still alpha. | §1.1, UK effects, LawVM |
| | | **In law7 itself: absent.** `amendment_applications` is empty; the consolidation engine has never run on real data. The 6,232 article versions present are imported base text, not the output of applying amendments. | measured 2026-09-14 |
| 3 | **Hash provenance vs official source** | **Partial — precedented once, still open where it matters.** A cryptographically verifiable statute book **does exist**: [DCCouncil/law](https://github.com/DCCouncil/law) is a **TUF repository inside a git repository**, authenticated with Open Law Library's [TAF](https://github.com/openlawlibrary/taf) (AGPL-3.0) — versioned roots 1..11, delegated roles, targets = git commit SHAs of the content repos, SHA-256 + SHA-512 per target, automated `oll-bot` commits as recent as 2026-09-11, driven legally by **UELMA**. It signs the *corpus over time*, not just documents at publication. (Caveat: `targets.json` on `master` showed `expires: 2025-07-08` — check the default branch before citing it as fully valid.) Estonia's Riigi Teataja hashes texts into a Guardtime KSI hash-chain, but this is used for **internal** periodic integrity validation and **no public citizen-facing verifier was found (unverified)**. EU/DE/AT/IT/ES/PT/RU gazettes carry per-document qualified e-signatures. **Still absent everywhere:** (a) integrity carried **through consolidation** — nobody except DC proves a derived text is the correct composition of a signed source plus amendments, and DC does not do point-in-time consolidation of a foreign corpus; (b) any such manifest in **any EU, UK or Russian jurisdiction**; (c) any application of Sigstore/Rekor, Trillian/CT-style transparency logs or IPFS to law — nothing of significance exists. No standard defines a content-integrity primitive; Гарант/КонсультантПлюс/Кодекс offer no cryptographic link to the official text; the academic literature has never applied C2PA or a hash chain to a statutory corpus. Weaker partials: lex-corpus (SHA-256 + signed manifest, one trusted signer, LU/EU only), opencaselaw (MD5 content hash, case law). | §6b of standards pass; verifiable-law digest §1-§6; §6.5 above |
| | | **In law7 itself: absent.** Every `text_hash VARCHAR(64)` in `docker/postgres/init.sql` (lines 128, 301, 416) is annotated "Hash for change detection" / "for comparison" — a hash of *derived* text for diffing, which is the opposite direction from proving descent from an official artifact. `documents` has `pdf_url` but no `pdf_sha256`, no `source_retrieved_at`, no captured signature, no manifest, no log. | schema inspection 2026-09-14 |
| 4 | **Multi-country** | **Solved at the identifier/format layer, not as a corpus.** ELI, AKN, N-Lex and WorldLII solve identification and federated search; the ~30-country MCP fleets (matematicsolutions, Ansvar) solve connector breadth; Legalize solves 32-country ingestion. **Nobody serves point-in-time text across jurisdictions through one interface.** | §1.2, §5 of standards pass |
| | | **In law7 itself: design only.** Russia only; `code_id` is a private vocabulary that cannot federate. | measured |
| 5 | **Decentralized verification** | **Nearly absent — one partial precedent.** DC/TAF comes closest: because the authentication repo is a valid TUF repo at every commit and its updater validates before cloning, **anyone can mirror the DC Code and verify it independently**, defending against compromised maintainer accounts, hosting compromise and SHA-1 collisions. That is the "one node extracts, everyone else verifies" topology, working, in one US jurisdiction. Otherwise: unofficial git mirrors (legalize-*, bundestag/gesetze, the US Code mirrors) verify against *their own* repo and not the official source; Canada's official git repo is centralized; lex-corpus's signed manifest has one trusted signer; justicedao's IPFS datasets have content addressing but no agent layer and no maintenance signal. **eIDAS 2.0 (Reg. (EU) 2024/1183) Art. 45k/45l created "qualified electronic ledgers"** — unique sequential chronological ordering, any change immediately detectable, operated by QTSPs — as a legal vehicle for exactly this, with **zero instances applied to legislative publication**. Sigstore/Rekor and Trillian/CT have never been applied to law; transparency.dev pitches this use case and nobody has taken it. | §4, §6 of standards pass; verifiable-law digest §1, §5, §6 |
| | | **In law7 itself: absent.** No implementation of any kind exists in the repository. | measured |
| 6 | **AI-agent API (MCP)** | **Already exists, widely, including for Russia.** ≥11 legislation MCP servers found across jurisdictions, plus ~60 across the two country fleets, plus a live pravo.gov.ru one at mcpgate.ru. MCP was donated to the Agentic AI Foundation (Linux Foundation) in Dec 2025; spec revision 2026-07-28. **Building on MCP is table stakes, not differentiation.** | §5 of standards pass |
| | | **In law7 itself: present but partial.** 13 tools, 10 working, over 265 test vectors. | measured |

**Summary.** Two claims (1, 6) are fully occupied by others. Two (2, 4) exist in stronger form as standards and weaker form as services, and are unimplemented or design-only in law7. Two (3, 5) have exactly one live precedent between them — the DC Code authenticated with Open Law Library's TAF — and are otherwise open; both are also unimplemented in law7.

law7's defensible novelty is the *combination* of (3) + (5) applied where it has never been applied: a hash-verified, independently reproducible consolidation pipeline whose output anyone can check against the official source. The honest framing is **not "first in the world"** but **"first outside the US DC Code, first for Russia, and first to carry integrity through *consolidation* rather than only at publication"**. Three facts support it:

- **Russia has no free, machine-readable, point-in-time statute service at all.**
- **pravo.gov.ru states that its "electronic images of control copies" carry a qualified electronic signature and runs its own CA** ([pravo.gov.ru/uc/](https://pravo.gov.ru/uc/)). Measured 2026-09-14: the PDFs are raster scans with no embedded signature, but the portal serves a **detached CAdES-BES (GOST R 34.10-2012 / Streebog-256) signature** at `/file/sig?eoNumber=` whose digest matches the PDF bytes and verifies in pure Python — for regional documents (30 of 31 sampled, ~94% of the corpus), while federal documents (`0001…`) return 404 (0 of 12). So law7's `source_sha256` anchors to the *published bytes* (`pdf_scan_of_control_copy`) and, for the regional majority, to a state-signed artifact (`signature: retrievable`); for federal acts the status is `asserted_by_portal, not_retrievable`. Note its correction convention "Взамен разосланного", which keeps publication details while replacing the image: law7 must capture and retain both.
- **The 2026 temporal-legal-QA literature names time-stamped consolidated statute text as its blocking missing resource.**

Both halves of the novelty are currently aspirational in law7 itself.

---

## 8. What changed since February 2026

- **Anthropic launched "Claude for Legal" on 2026-05-12**: 20+ MCP connectors and 12 practice-area plugins for law firms, with partners including Thomson Reuters, Box, Legal Quants and Lawve AI. Thomson Reuters' CoCounsel was **rebuilt on Anthropic's Claude Agent SDK** (beta April 2026) and ships as a Claude for Legal connector. LexisNexis relaunched Lexis+ AI / Protégé in Feb 2026 with 300+ agentic workflows. OpenAI is reported to be building "Codex for Legal" (hired Jason Boehmig of Ironclad, June 2026), not shipped as of the scan **(unverified)**. **No Russia-specific or pravo.gov.ru connector exists in Claude for Legal.**
- **MCP became infrastructure, not a differentiator.** Donated to the Agentic AI Foundation (Linux Foundation) in Dec 2025; current spec revision 2026-07-28. Registries and directories now exist (Anthropic's connector directory, mcpservers.org, glama.ai, lobehub, mcpgate.ru). CourtListener shipped a **first-party remote MCP** at `mcp.courtlistener.com` with OAuth in May 2026, listed in Anthropic's directory — the most institutionally-backed open legal-data MCP found.
- **A wave of per-country legislation MCP servers was built Mar–Sep 2026**: ~30 from matematicsolutions, ~30 from Ansvar-Systems, plus independents for the UK, US, EU, Switzerland, Austria, Australia and Korea. Nearly all were created after law7 paused. All of them lean on the official source already publishing point-in-time data.
- **Two serious new open-source entrants appeared in the exact space law7 occupies**: lex-corpus/lex (from Aug 2026, with the hash+manifest layer law7 claimed) and LawVM (with the replay-and-verify layer law7 claimed). Legalize.dev scaled to 32 countries. Ley Abierta shipped Spain with per-reform commits.
- **Germany's NeuRIS** ([ris.bund.de](https://ris.bund.de/)) published an open API in April 2025 with 1M+ documents migrated, going live through 2025-2026 — the most significant new national PIT entrant, replacing the weak gesetze-im-internet.de.
- **A whole research field appeared around law7's output.** Between May and August 2026 the temporal legal QA literature went from nothing to a cluster: [*Asking For An Old Friend*](https://arxiv.org/abs/2605.23497) (ICAIL 2026), [FiscalQA Pro](https://arxiv.org/abs/2608.09393), [LexKairos](https://arxiv.org/abs/2608.09106), [*Can LLMs Time Travel?*](https://arxiv.org/abs/2605.25920), [TIDE](https://arxiv.org/abs/2608.08512). They converge on one finding and one complaint. The finding: date-conditioned retrieval over a versioned corpus takes statutory QA accuracy **from 2.7–3.0% to 98.3%** (FiscalQA Pro; static RAG over a current-version corpus retrieved the date-applicable version **0%** of the time while confidently returning *a* version 100% of the time). The complaint: this "requires curated, versioned statutory databases not universally available."

**The demand-side argument.** Stanford RegLab measured 58–88% hallucination in raw LLMs ([*Large Legal Fictions*](https://arxiv.org/abs/2401.01301)) and **17–33% even in Lexis+ AI, Westlaw AI-Assisted Research and Ask Practical Law AI** ([*Hallucination-Free?*](https://arxiv.org/abs/2405.20362)) — RAG over a current-text corpus does not fix it. No peer-reviewed study evaluates any commercial legal AI on *currency*. There is no cross-jurisdiction point-in-time benchmark, and **none covering Russian or any Slavic corpus**. The blocking resource named by the people studying the problem is exactly what law7 produces.

**What it means for law7's positioning.** The "MCP server for laws" slot is filled, several times over, in most jurisdictions. "Git for laws" is occupied too — Canada publishes its statute book in git, Legalize covers 32 countries, and neither claim is available. The parts of law7's pitch that were merely early (PIT, MCP) are now late.

The reframe is from **"git for laws"** to **"eliminating temporal misgrounding for LLMs"**: law7 is the corpus that makes date-conditioned retrieval possible for Russian law, plus a verifiable chain back to the official signed source so the answer can be audited. That framing is specific, measurable against a published benchmark, currently unserved for Russia, and aligned with where both the research and the platform money went in 2026. Russia-specific and integrity-specific — not "git for laws".

---

## 9. Recommendations

1. **Implement claim 3 first: add `source_sha256`, `source_retrieved_at`, `source_bytes_len` to `documents` and publish a signed manifest, using [TAF/TUF](https://github.com/openlawlibrary/taf) as the reference implementation.** It is the cheapest remaining work, it anchors to an artifact pravo.gov.ru already signs with a qualified signature, and TAF is AGPL-3.0 like law7 and purpose-built for signed git repositories of law.
2. **Make version resolution symbolic and metadata-driven, never embedding-based.** FiscalQA Pro showed static semantic RAG retrieves the date-applicable version 0% of the time because article numbers alias across versions and cross-version embeddings are near-identical. Date filtering must happen in SQL before the vector search, not after.
3. **Run the consolidation engine on real data and publish the result — or drop claim 2 from the project description.** `amendment_applications` being empty means claim 2 is currently a design document, and the gap between claimed and actual is the largest credibility risk in the repo. Budget for ~60% automation, which is the published state of the art (Etcheverry: 63.2% correct on 49.8% of cases).
4. **Restructure the amendment schema to AKN `textualMod` shape (type, source, destination, old, new, force/efficacy) and carry AKN's three time axes — in-force, efficacy, transaction — before the first real consolidation run**, because retrofitting typed modifications onto a populated audit log is far more expensive.
5. **Publish a Russian point-in-time statutory QA benchmark as a wedge.** No cross-jurisdiction PIT benchmark exists and none covers Russian or Slavic corpora; a few hundred expert-validated dated QA pairs in the style of *Asking For An Old Friend* would cost little, be citable, and make law7 the reference corpus for a field that is actively looking for one.
6. **Add ELI-style canonical URIs and an Akoma Ntoso export**, so law7's output is citable and consumable outside law7 — this is also the only credible path to claim 4. Model the MCP tool surface on the [SAT-Graph API](https://arxiv.org/abs/2510.06002): typed deterministic primitives with an auditable log, rather than free-form search.
7. **Publish the "effects not yet applied" backlog per code**, as legislation.gov.uk does with its ~100,000 unapplied effects; a consolidation that silently omits unapplied amendments is unusable for legal work and indefensible if challenged.
8. **Reframe the narrative from "git for laws" to "eliminating temporal misgrounding for LLMs".** "Git for laws" is occupied (Canada publishes its statute book in git; Legalize covers 32 countries) and "MCP for law" is table stakes since the Claude for Legal / MCP-registry shift. Claim "first outside the US DC Code, first for Russia, first to carry integrity through consolidation" — not "first in the world".
9. **Talk to [AlsKozlov/ru-legal](https://github.com/AlsKozlov/ru-legal) rather than competing with it** — it covers registry breadth law7 does not and lacks the temporal depth law7 is built for; and use [irlcode/RusLawOD](https://github.com/irlcode/RusLawOD) as a cross-validation corpus for the crawl.

---

## 10. Dead, abandoned, or misattributed — do not propose these again

| Project | Status |
|---|---|
| [Legilibre/Archeo-Lex](https://github.com/Legilibre/Archeo-Lex) | Dead since 2019-03-10. Converted France's LEGI into Git+Markdown with full amendment history — the original of this whole idea, unmaintained for 7 years. |
| [Legilibre](https://github.com/Legilibre) DuraLex / SedLex | Dead, same org and era as Archéo-Lex. |
| [bundestag/gesetze](https://github.com/bundestag/gesetze) | Data repo stalled at 2022-11-25 (tools repo still maintained). 1,920★ but the law-text mirror has not been repushed in ~4 years; the original goal of full amendment history was never completed. **The `bundestag` org name is squatted by activist Stefan Wehrmeyer (Bundes-Git, 2012) — it is not the German parliament.** Its README disclaims any guarantee of correctness. Do not cite it as an official source. |
| "Government blockchain legislation" — Georgia NAPR (Bitfury/Exonum 2016; Hedera MoU Dec 2025), Dubai/UAE DLD on XRPL, Chinese judicial blockchains | **All land registries, property title deeds or evidence preservation — none is legislation.** Dubai's "blockchain government by 2025" was not met for legislation and its gazette has no signature or hash verification. Kazakhstan's zan.gov.kz signs each act with an official's EDS (not a chain); Ukraine has none. Every "blockchain for law" precedent checked evaporated on inspection. |
| US Code git mirrors: [nickvido/us-code](https://github.com/nickvido/us-code) (365★, burst Mar–Apr 2026 then silent), CourtGPT/us-code, publicdocs/uscode (dead 2018) | Commits mirror OLRC release points. **None hash-verifies against OLRC.** Superseded by GPO's own USLM. |
| [BonoNetwork/Gitlaw](https://github.com/BonoNetwork/Gitlaw) | Dead toy, 2024-11-07. 0★, 3 commits, YAML skeleton only; "blockchain + AI" planned, nothing built. |
| spartypkp/open-source-legislation | Abandoned by its author once their own AI legal assistant need was served; GitHub API returned nothing for the repo/user on 2026-09-14 **(unverified — likely renamed or deleted)**. |
| "Every Law a Commit" / Dark Factory ([HN #47621591](https://news.ycombinator.com/item?id=47621591), [blog](https://v1d0b0t.github.io/blog/posts/2026-03-29-every-law-a-commit.html)) | One-off 48h AI-built demo, March 2026. Diffs *annual* US Code snapshots, not individual bill edits. No maintained repo confirmed. |
| [divegeek/uscode](https://github.com/divegeek/uscode), [quanglam2807/us-statutes](https://github.com/quanglam2807/us-statutes), [rtblair/git-legislation](https://github.com/rtblair/git-legislation) | ~2013-era hobby scripts converting OLRC US Code XML to git. Superseded by GPO's own USLM. |
| `Ansvar-Systems/Russian-Law-MCP` | npm package exists (Apache-2.0, v0.1.0); GitHub repo 404s while all ~30 siblings are public. Unauditable **(unverified)**. |
| `DCCouncil/dc-law` (old repo) | Stalled 2020-09-13; superseded by the active [DCCouncil/law](https://github.com/DCCouncil/law) family. Do not cite the old name. |
| `conformi-eu/conformi-search-mcp` | 404 on re-check 2026-09-14 **(unverified — renamed or removed)**. |
| [kobzevvv/legal-ai-platform](https://github.com/kobzevvv/legal-ai-platform) | One-day burst 2026-02-25, nothing since. RAG over 11 Russian codexes. |
| [gitmaxlla/jurask](https://github.com/gitmaxlla/jurask) | Dormant since 2025-05-15. |
| [Lexpedite/blawx](https://github.com/Lexpedite/blawx) | Aging: last push 2024-11-01. Rules-as-code authoring, not a versioned corpus. |
| [aidoskz/zakon_kz](https://github.com/aidoskz/zakon_kz), [abitrolly/rulez](https://github.com/abitrolly/rulez) | KZ/BY community efforts, likely small or dormant **(unverified — not checked in depth)**. |
| [Ansvar-Systems/Austrian-law-mcp](https://github.com/Ansvar-Systems/Austrian-law-mcp) | Archived. Other Austrian wrappers are alive. |

---

## 11. Sources

The research scratchpad files backing this document are session-temporary and not shippable. All URLs used:

### Standards
- Akoma Ntoso / OASIS LegalDocML: https://www.oasis-open.org/standard/akn-v1-0/ · http://www.akomantoso.org/ · https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html · https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part2-specs.html · https://docs.oasis-open.org/legaldocml/akn-nc/v1.0/akn-nc-v1.0.html · https://github.com/oasis-open/legaldocml-akomantoso · https://www.oasis-open.org/committees/tc_home.php?wg_abbrev=legaldocml
- ELI: https://op.europa.eu/en/web/eu-vocabularies/eli · https://data.europa.eu/eli/ontology · https://op.europa.eu/documents/3938058/11669184/eli.owl/ · https://op.europa.eu/documents/2050822/2138819/ELI+-+A+Technical+Implementation+Guide.pdf/ · https://eur-lex.europa.eu/eli-register/about.html · https://interoperable-europe.ec.europa.eu/collection/eli-european-legislation-identifier/solution/eli-i · https://eur-lex.europa.eu/content/eli-register/switzerland.html
- Others: ECLI https://e-justice.europa.eu/175/EN/european_case_law_identifier_ecli · USLM https://github.com/usgpo/uslm · https://xml.house.gov/schemas/uslm/1.0/USLM-User-Guide.pdf · CLML https://github.com/legislation · https://research.legislation.gov.uk/node/58 · JOLux https://swiss.github.io/fedlex-jolux/introduction.html · FRBR https://www.ifla.org/publications/functional-requirements-for-bibliographic-records/

### Government point-in-time services
- UK: https://www.legislation.gov.uk · https://legislation.github.io/data-documentation/api/overview.html · https://www.legislation.gov.uk/changes/affecting/uksi/2022/884 · https://github.com/legislation
- EU: https://eur-lex.europa.eu · https://op.europa.eu/en/web/cellar/cellar-data · http://publications.europa.eu/webapi/rdf/sparql · https://op.europa.eu/en/advanced-sparql-query-editor · https://eur-lex.europa.eu/content/help/data-reuse/webservice.html · https://n-lex.europa.eu
- Switzerland: https://www.fedlex.admin.ch · https://fedlex.data.admin.ch/ · https://fedlex.data.admin.ch/sparqlendpoint · https://int.lindas.admin.ch/data-usage/fedlex/
- Canada: https://laws-lois.justice.gc.ca/eng/ · https://github.com/justicecanada/laws-lois-xml · https://open.canada.ca/data/en/dataset/4d277b82-c4af-4431-b31d-48fcece6dd8a · https://open.canada.ca/data/en/dataset/2f4bb174-b2e7-4fb2-a7a1-a313507acbc6
- Australia: https://www.legislation.gov.au · https://www.opc.gov.au/FRL · https://www.austlii.edu.au · https://lawcite.org/ · https://legislation.nsw.gov.au/view/xml/inforce/2008-02-01/epi-2008-0025/lh
- New Zealand: https://www.legislation.govt.nz · https://api.legislation.govt.nz/docs/
- Italy: https://www.normattiva.it · https://dati.normattiva.it
- France: https://www.legifrance.gouv.fr · https://piste.gouv.fr · https://www.data.gouv.fr/dataservices/legifrance · https://www.data.gouv.fr/datasets/legi-codes-lois-et-reglements-consolides · https://huggingface.co/datasets/AgentPublic/legi
- Germany: https://www.gesetze-im-internet.de · https://ris.bund.de/ · https://testphase.rechtsinformationen.bund.de/ · https://digitalservice.bund.de/en/projects/new-legal-information-system
- USA: https://uscode.house.gov · https://www.govinfo.gov/app/collection/uscode · https://uscode.house.gov/download/priorreleasepoints.htm · https://datafoundation.org/news/blogs/335/335-Version-Control-for-Law-Tracking-Changes-in-the-US-Congress
- Austria: https://www.ris.bka.gv.at/

### Russia
- http://publication.pravo.gov.ru · http://publication.pravo.gov.ru/help · http://publication.pravo.gov.ru/OpenData · http://government.ru/open_data/ · https://data.apicrafter.ru/packages/pubpravogovru
- http://actual.pravo.gov.ru/ · http://www.actual.pravo.gov.ru/content/content.html · https://www.garant.ru/news/1531144/
- http://pravo.gov.ru/ips/
- https://sozd.duma.gov.ru · http://api.duma.gov.ru/ · http://api.duma.gov.ru/pages/dokumentatsiya/spravochnik-po-api
- https://www.consultant.ru · https://www.garant.ru · https://www.garant.ru/products/solution/sravnenie/ · https://kodeks.ru/
- https://mcpgate.ru/servers/pravo
- https://github.com/irlcode/RusLawOD · https://huggingface.co/datasets/irlspbru/RusLawOD · https://huggingface.co/datasets/AlsKozlov/legalbench-ru · https://huggingface.co/datasets/justicedao/ipfs_russia_laws_ir
- https://github.com/AlsKozlov/ru-legal · https://github.com/shodenis/Russian-Law-MCP · https://github.com/atomno-mcp/mcp-sudact · https://github.com/DrobyshevDev/praxis · https://github.com/kobzevvv/legal-ai-platform · https://github.com/gitmaxlla/jurask · https://github.com/leadpioneer/russianlawbattle · https://www.npmjs.com/package/@ansvar/russian-law-mcp

### Open-source law-as-git projects
- https://github.com/legalize-dev/legalize · https://legalize.dev · https://github.com/legalize-dev/legalize-uk · https://ubos.tech/news/archiving-spanish-laws-in-git-open-source-legal-tech-for-transparency/
- https://github.com/leyabierta/leyabierta
- https://github.com/SFHAJJI/lex · https://github.com/SFHAJJI/lex-corpus-lu-legilux · https://github.com/SFHAJJI/lex-corpus-eu-eurlex
- https://github.com/eliask/lawvm
- https://github.com/bundestag/gesetze · https://github.com/bundestag/gesetze-tools
- https://github.com/Legilibre/Archeo-Lex · https://github.com/Legilibre
- https://github.com/openlawlibrary/open-law · https://github.com/DCCouncil/law
- https://github.com/unitedstates/congress · https://github.com/divegeek/uscode · https://github.com/quanglam2807/us-statutes · https://github.com/rtblair/git-legislation · https://github.com/nickvido/us-code
- https://news.ycombinator.com/item?id=47621591 · https://v1d0b0t.github.io/blog/posts/2026-03-29-every-law-a-commit.html
- https://github.com/BonoNetwork/Gitlaw · https://github.com/aidoskz/zakon_kz · https://github.com/abitrolly/rulez

### Legal MCP servers and agent tooling
- https://github.com/chrisryugj/korean-law-mcp
- https://github.com/jonashertner/opencaselaw · https://mcp.opencaselaw.ch
- https://github.com/matematicsolutions/it-eli-mcp · https://glama.ai/mcp/servers/matematicsolutions/gb-eli-mcp
- https://github.com/Ansvar-Systems/UK-law-mcp · https://github.com/Ansvar-Systems/Luxembourg-law-mcp · https://github.com/Ansvar-Systems/Austrian-law-mcp
- https://github.com/paulieb89/uk-legal-mcp · https://github.com/busybusybussiness/uk-legislation-changes · https://github.com/JamesANZ/us-legal-mcp · https://github.com/Mahender22/legal-mcp · https://github.com/agentic-ops/legal-mcp
- https://github.com/cyanheads/courtlistener-mcp-server · https://mcp.courtlistener.com · https://github.com/freelawproject/courtlistener
- https://github.com/cyanheads/eur-lex-mcp-server · https://github.com/damankaur-dev/openlaw-mcp · https://github.com/TCoder920x/open-legal-compliance-mcp
- https://github.com/malkreide/fedlex-mcp · https://github.com/ribeaud/fedlexplorer · https://github.com/JayTheSkier/fedlex-connector · https://mcpservers.org/servers/loicvuilliomenet-boop/fedlex-mcp
- https://github.com/Honeyfield-Org/ris-mcp-ts · https://github.com/cyanheads/ris-austria-mcp-server
- https://github.com/ChangkeunJ/australian-law-mcp · https://glama.ai/mcp/servers/Ktulu-Analog/mcp-legifrance · https://github.com/Dahliyaal/justicelibre
- MCP governance: https://blog.modelcontextprotocol.io/posts/2026-07-28/

### Rules as code (adjacent)
- https://www.oecd.org/gov/cracking-the-code-3afe6ba5-en.htm · https://openfisca.org/doc/ · https://github.com/openfisca · https://github.com/openfisca/openfisca-core · https://github.com/BetterRules/openfisca-aotearoa · https://catala-lang.org · https://book.catala-lang.org · https://github.com/CatalaLang/catala · https://github.com/Lexpedite/blawx · https://github.com/BetterRules · https://www.digital.govt.nz/blog/what-is-better-rules

### Verifiable / authenticated law
- DC Council + TAF: https://github.com/DCCouncil/law · https://github.com/openlawlibrary/taf · https://github.com/openlawlibrary/taf/blob/master/specification/taf-spec.md · https://github.com/openlawlibrary/open-law
- UELMA: https://www.aallnet.org/advocacy/government-relations/state-issues/uelma-resources/
- Estonia KSI: https://e-estonia.com/solutions/cyber-security/ksi-blockchain/ · https://e-estonia.com/blockchain-security-control-for-government-registers/ · https://e-estonia.com/fighting-fake-news-with-blockchain/ · https://en.wikipedia.org/wiki/Riigi_Teataja · https://academic.oup.com/policyandsociety/article/41/3/386/6566828
- eIDAS 2.0 qualified electronic ledgers (Art. 45k/45l): https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A02014R0910-20241018
- Russian publication CA: https://pravo.gov.ru/uc/
- Transparency logs: https://github.com/sigstore/rekor · https://docs.sigstore.dev/logging/overview/ · https://github.com/transparency-dev/trillian-tessera · https://openssf.org/blog/2025/10/15/announcing-the-sigstore-transparency-log-research-dataset/
- Debunked "blockchain law" claims: https://www.financemagnates.com/trending/georgia-advances-land-registry-and-real-estate-tokenization-following-dubai/ · https://u.ae/en/about-the-uae/digital-uae/digital-technology/blockchain-in-the-uae-government · https://www.mdpi.com/2071-1050/14/11/6576

### Academic — temporal models and versioning
- https://dl.acm.org/doi/fullHtml/10.1145/3614321.3614327 (ELI ↔ AKN ontology mapping)
- https://link.springer.com/chapter/10.1007/978-94-007-1887-6_7 (Palmirani, Legislative Change Management with Akoma-Ntoso, 2011)
- https://www.balisage.net/Proceedings/vol24/html/Palmirani01/BalisageVol24-Palmirani01.html
- https://www.semanticscholar.org/paper/0e5ca381d0dfd3c95cdb2b30847440f4594db73e (Palmirani & Vitali, Akoma-Ntoso for Legal Documents)
- https://arxiv.org/abs/2506.07853 · https://arxiv.org/html/2506.07853v3 · https://arxiv.org/html/2506.07853v1 (LRMoo component-level versioning)
- https://arxiv.org/abs/2505.00039 (SAT-Graph RAG, JURIX 2025) · https://arxiv.org/abs/2510.06002 (SAT-Graph API) · https://arxiv.org/abs/2606.09724 (Beyond Probabilistic Similarity)
- https://link.springer.com/chapter/10.1007/978-3-032-13109-6_18 (Semantic Finlex change-history KG)
- https://zenodo.org/records/17129539 (Akoma Ntoso: Powering Legal AI with Open Data Standard, 2025)
- https://www.popvox.org/blog/when-law-becomes-data (Brazil LexML/AKN retrospective)

### Academic — consolidation automation
- https://aclanthology.org/2024.nllp-1.13/ (Etcheverry et al., Doctrine.fr, NLLP@EMNLP 2024)
- https://arxiv.org/abs/2301.06469 (Silber, Towards an Automatic Consolidation of French Law)
- https://link.springer.com/article/10.1007/s10506-012-9127-6 (TULSI, ITTIG-CNR)
- https://aclanthology.org/2021.clicit-1.24/ (Fabrizi et al., CLiC-it 2021)
- https://arxiv.org/abs/2406.14935 (Colombo, Bernasconi, Ceri, Modelling Legislative Systems into Property Graphs)
- https://huggingface.co/datasets/DoctrineAI/legal_consolidation
- https://eur-lex.europa.eu/content/intro/collection/Methodology-on-Consolidation.pdf · https://www.legislation.gov.uk/changes
- https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/LLM+Graph/LLMGraph-2.pdf · https://arxiv.org/html/2503.12100v1 · https://arxiv.org/pdf/2308.09341

### Academic — temporal legal QA, hallucination, currency
- https://arxiv.org/abs/2605.23497 · https://arxiv.org/pdf/2605.23497 (Asking For An Old Friend, ICAIL 2026)
- https://arxiv.org/abs/2608.09393 (Temporal Misgrounding in Legal RAG / FiscalQA Pro)
- https://arxiv.org/abs/2608.09106 (LexKairos) · https://arxiv.org/abs/2605.25920 (Can LLMs Time Travel?) · https://arxiv.org/abs/2608.08512 · https://arxiv.org/html/2608.08512v1 (TIDE)
- https://arxiv.org/pdf/2601.09523 (TEMPO) · https://arxiv.org/pdf/2505.20243 (It's High Time) · https://arxiv.org/pdf/2506.07270 (QA under Temporal Conflict)
- https://arxiv.org/abs/2401.01301 · https://arxiv.org/pdf/2401.01301 · https://academic.oup.com/jla/article/16/1/64/7699227 · https://reglab.stanford.edu/publications/hlarge-legal-fictions-profiling-legal-hallucinations-in-large-language-models/
- https://arxiv.org/abs/2405.20362 · https://law.stanford.edu/wp-content/uploads/2024/05/Legal_RAG_Hallucinations.pdf · https://reglab.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/ · https://www.llrx.com/2026/02/what-the-science-says-about-hallucinations-in-legal-research/
- https://ssrn.com/abstract=5274547 (AI Gets Its First Law School A+s) · https://arxiv.org/abs/2606.00898 (Citation Grounding) · https://arxiv.org/abs/2605.10186 (LegalCiteBench) · https://arxiv.org/abs/2511.06700 (Place Matters) · https://arxiv.org/abs/2605.31338 (Bundesrecht corpus)
- https://arxiv.org/pdf/2103.03198 (Catala) · https://www.sciencedirect.com/science/article/pii/S2666307425000336
