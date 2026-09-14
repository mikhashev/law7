# Glossary

v3 — 2026-09-14. Rows by Ark (v1–v2), rules and checker alignment by CC; reviewed in the Law7 group chat.

One row per word this project uses in a specific sense. The file **points, it does not define**:
the **Meaning** column paraphrases the document that owns the word, the **Defined by** column names
that document, and **the owner wins whenever the two disagree**. A row that cannot name its owner
does not belong in §1–§3 — it belongs in §4, unresolved and visible.

## Three kinds of row, and why they are not mixed

| Owner | For words about | Where the authority lives | Who may change the meaning |
|---|---|---|---|
| **The state** | law itself — publication, force, retroactivity, reading | an official act, cited by type, date, number and title | nobody in this repository. Ever. |
| **An outside document** | identifiers, formats, integrity machinery — standards and literature | that document: a specification, a standard, a paper | a new version of that document |
| **This repository** | our pipeline, our schema, our words for our own artefacts | a document in this repository, linked | us, by editing that document |

A project whose premise is *the authority is outside* may not paraphrase "entry into force" in its
own words — that is the failure it exists to prevent. So a legal row names the **act**.

## Three rules this file obeys

1. **It carries no number that describes our own coverage.** Counts of documents, codes, articles,
   tools, vectors, tests or rows live in [SCOPE.md](SCOPE.md) and nowhere else, so that they drift in
   one place. The criterion is the frame of reference, not the size of the number: "22 codes" is a
   count of ours and is forbidden here; a date, an act number, an article number, a version of a
   standard or the year of a paper is part of someone else's object and is allowed.
2. **A link that resolves to nothing is a bug**, not a style issue. Links are checked mechanically
   (§5). Anchors are deliberately not used: an anchor nobody has opened is the same bug as a URL
   nobody has opened.
3. **Every row is self-contained.** "Same as above" is not a citation: a row must be readable and
   checkable on its own, in any order.

---

## 1. Law, in the words of the state

Russian terms are the lookup key, because that is what a reader will actually search the corpus
for. Where an official URL exists it is given; where it does not, the row says so instead of
inventing one.

| Term | Meaning | Defined by |
|---|---|---|
| **official publication** (официальное опубликование) | The first publication of an act in an outlet designated as official. It is the moment the text becomes public and the reference point every other date is measured from. Distribution by third parties — including this project — is derivative of it, never a substitute for it. | Federal Law of 14.06.1994 No. 5-FZ "On the procedure for the publication and entry into force of federal constitutional laws, federal laws, and acts of the chambers of the Federal Assembly", art. 4 |
| **entry into force** (вступление в силу) | The date from which an act binds. **The default differs by type of act**, so it is not one rule: acts of the chambers, federal laws and federal constitutional laws are covered by 5-FZ; acts of the President, of the Government and of federal executive bodies by a separate decree. The act's own date is therefore a field of the act, not something this project may infer. | Federal Law of 14.06.1994 No. 5-FZ "On the procedure for the publication and entry into force of federal constitutional laws, federal laws, and acts of the chambers of the Federal Assembly", art. 6; Decree of the President of 23.05.1996 No. 763 "On the procedure for the publication and entry into force of acts of the President, the Government and normative legal acts of federal executive bodies" |
| **retroactive effect** (обратная сила) | An act reaching relations that arose before it came into force. The prohibition and the exception are two different provisions of one article: part 1 forbids retroactivity for a law that establishes or aggravates liability; part 2 applies the more lenient law where liability has been removed or mitigated. In criminal law the same rule is restated in the code. Because this is law and not policy, the pipeline stores the interval an article was in force and never assumes "current". | Constitution of the Russian Federation, art. 54(1) and 54(2); Federal Law of 13.06.1996 No. 63-FZ "Criminal Code of the Russian Federation", art. 10 |
| **official interpretation** (письменное разъяснение) | A written explanation of the application of tax law, given by the finance authority on a request from a taxpayer or a tax agent. For this project it is a second kind of change: the text is unchanged, the reading is not. What such an explanation *does* to liability is a separate question and has no owner here yet (see §4). | Tax Code of the Russian Federation, art. 34.2 |

### 1.1. The one legal fact that decides the product's shape

The official machine-readable consolidated channel in Russia carries **changes from 01.07.2022
onward**. Before that window there is no official machine-readable consolidation, so "what was in
force on 2015-01-01" cannot be answered by pointing at the state — it has to be computed from
primary publications. That window, not the corpus, is where the project's non-substitutability
lives.

*Status of this paragraph:* read from the portal's own wording on 2026-09-14; its re-measurable form
belongs in [SCOPE.md](SCOPE.md), not here.

## 2. Our own words — this repository

Every row links to the document that owns it. If that document does not exist yet, the word is in
§4 — a word we intend to define is not a word we have defined.

| Term | Meaning | Defined by |
|---|---|---|
| **snapshot** | A frozen, dated state of the corpus that can be named, hashed and restored. The unit of distribution and of argument: every claim about the data is a claim about a named snapshot. | [SCOPE.md](SCOPE.md); [BACKUP_RESTORE.md](BACKUP_RESTORE.md) |
| **source hash** | The hash of the **official artefact** the text was derived from — the state's own object, not our extraction of it. Distinct from `text hash`; conflating the two is the mistake this project can least afford. Not a column in the schema yet: `docker/postgres/init.sql` has no `source_sha256` today. | [SCOPE.md](SCOPE.md); [`../docker/postgres/init.sql`](../docker/postgres/init.sql) |
| **text hash** | The hash of **our** copy of the text, used to detect that our own extraction changed. It proves nothing about the state's artefact and must never be presented as provenance. It is not on `documents`: the column exists on three other tables. | [`../docker/postgres/init.sql`](../docker/postgres/init.sql) — `text_hash` on `document_content`, `code_article_versions`, `court_decisions` |
| **provenance chain** | The ordered set of arrows from the official artefact to the answer a client receives: official artefact → extracted text → article version. Each arrow needs an author and a version (`extractor_id@version`, `consolidator_id@version`); without them "verifiable" covers only the first hop. | [VISION.md](VISION.md) |
| **manifest** | The published index of a snapshot — identifier → source hash → text hash → versions — signed as one object, so a stranger can mirror the corpus and re-derive the check without trusting the publisher. | [SCOPE.md](SCOPE.md); [VISION.md](VISION.md) |
| **independent verification** | A third party downloads the official artefact and compares it to the manifest, having been given nothing but a URL and a hash. The property that separates this project from a mirror. | [VISION.md](VISION.md) |
| **strict mode** | Verification by hash equality with the official artefact. Cannot be satisfied while the state's own site is unavailable — and is not replaced by voting. | [VISION.md](VISION.md) |
| **soft mode** | Acceptance of an update by community signatures when the official source is temporarily unreachable. A **weaker** claim than strict mode and must be labelled as such in any answer that relies on it — never silently upgraded to "verified". | [VISION.md](VISION.md) |
| **staleness** | The gap between the snapshot and reality, which a client must be able to see. An answer that hides its own age is worse than no answer — the failure mode this project exists to remove, and one it can still commit itself. | [SCOPE.md](SCOPE.md) |
| **unapplied-amendment backlog** | The published list of amendments found but not yet applied to the consolidated text. Publishing it is a safety feature: silent partial consolidation is worse than an admitted backlog. | [SCOPE.md](SCOPE.md); [RESEARCH_SIMILAR_PROJECTS.md](RESEARCH_SIMILAR_PROJECTS.md) |
| **source adapter** (country adapter) | The per-jurisdiction code that knows a country's official outlets and how its acts are shaped — `scripts/country_modules/<country>/`. Not a plugin for a shared data model: the shared thing is the verification protocol, the national thing is the model. | [`../CLAUDE.md`](../CLAUDE.md); `scripts/country_modules/` |
| **consolidation** | Building the text of an act as amended, from the primary publications and the amendatory acts. Our pipeline, our word; what the result is called in law is a separate question (§4). | [README.md](../README.md); [`../CLAUDE.md`](../CLAUDE.md) |
| **amendment application** | One recorded act of applying one amendatory act to one article, with the outcome. The row is the audit trail: without it a consolidation is unauditable, and the table is empty today, which is why any client asking for history receives nothing. | [`../docker/postgres/init.sql`](../docker/postgres/init.sql) — `amendment_applications` |
| **article version** | One dated state of one article, produced by consolidation. The answer to "what was in force on date D" is a row from here, or an explicit refusal. | [`../docker/postgres/init.sql`](../docker/postgres/init.sql) — `code_article_versions` |
| **anchor horizon** | The date before which a jurisdiction offers no official machine-readable artefact of an act, so nothing earlier can be anchored to the source — only assumed. A property of each country adapter, not of the project. | [SCOPE.md](SCOPE.md) |
| **available / signed** (states of an official artefact) | Two independent properties of an official artefact: *available* — its bytes can be fetched from the source and a hash shown (integrity); *signed* — a signature over those bytes can be fetched and checked (authorship). An artefact can be available and unsigned; "anchored" without saying which is a claim without a referent. | [SCOPE.md](SCOPE.md) |
| **`code_id`** | The private identifier of a consolidated code in our schema — the vocabulary `ELI` is meant to replace, because an identifier a stranger cannot resolve makes federation impossible. | [`../docker/postgres/init.sql`](../docker/postgres/init.sql) — `consolidated_codes`; see §3 `ELI` |

## 3. Words borrowed from an outside document

| Term | Meaning | Defined by |
|---|---|---|
| **ELI** | European Legislation Identifier: a URI scheme that puts jurisdiction, act type, date and a point-in-time slot inside the identifier. | ELI ontology — <http://data.europa.eu/eli/ontology> |
| **point-in-time** | A query shape, not a feature: "the text in force on date D". The selector is part of the identifier (`ELI`), so selecting a version is symbolic and exact, never a similarity search. | ELI ontology, point-in-time slot — <http://data.europa.eu/eli/ontology> |
| **ECLI** | The same idea for case law — the identifier a court decision can be cited by. | **citation unresolved** — the introducing instrument is not cited in this repository yet |
| **Akoma Ntoso (LegalDocML)** | The OASIS XML vocabulary for legislative text, with amendment effects as typed objects rather than prose. Our target internal shape for amendments. Version 1.0. | OASIS LegalDocML, Akoma Ntoso v1.0, Part 2: Specifications — <https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/os-part2-specs.html> |
| **`textualMod`, active and passive modifications** | Akoma Ntoso's representation of an amendment: what kind of change, what it affects, and the old and the new text. The reason an amendment is modelled as an object and not as a stored diff. | OASIS LegalDocML, Akoma Ntoso v1.0, Part 2: Specifications — <https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/os-part2-specs.html> |
| **FRBR** | The work / expression / manifestation / item distinction, which is what lets one act have many dated versions without duplicating the act. Superseded as a model by IFLA LRM (2017). | IFLA, *Functional Requirements for Bibliographic Records* (1998); **URL citation unresolved** — ifla.org refuses this agent (HTTP 403), so the address is neither confirmed nor denied here |
| **TAF / TUF** | The update framework and its metadata layer: signed snapshots, an explicit list of what changed, and a client that refuses an unsigned rollback. A candidate mechanism for the manifest; not our invention, and already deployed for a statute corpus. | TUF — The Update Framework specification, latest — <https://theupdateframework.github.io/specification/latest/> |
| **transparency log** | An append-only, publicly auditable log. The other candidate for "anyone can mirror and audit" without asking permission. | Sigstore, transparency log overview — <https://docs.sigstore.dev/logging/overview/> |
| **temporal misgrounding** | Answering a legal question from a version that was not in force — confidently and invisibly. The named failure mode this project addresses; the term comes from outside, the measurement does not yet exist in Russian. | arXiv 2605.23497 (2026), cited here via [RESEARCH_SIMILAR_PROJECTS.md](RESEARCH_SIMILAR_PROJECTS.md); the paper itself was not opened by this file's author |

## 4. Words that have no owner yet

These are used in the project and cannot be attributed. Each is a task, not a definition. A row
leaves this section when someone can name the act, the outside document, or the repository document
that owns it.

| Word | Why it has no owner |
|---|---|
| **signed control copy** (контрольный экземпляр) | Described by the portal as an electronic image accompanying the publication, signed with a qualified signature. Measured on 2026-09-14: the signature exists as a *detached* artefact (`/file/sig?eoNumber=…`, CAdES-BES over the PDF bytes) for the sampled regional documents and was not served for the sampled federal ones — see [SCOPE.md](SCOPE.md), Provenance. What remains without an owner: no act defining the format of the "control copy" is cited here, it is not established that the observed object *is* that copy, and whether federal publications have any retrievable signed artefact is unknown. |
| **amendatory act** (акт о внесении изменений) | The category is real and used; no act defining the term is cited in this repository. Its text is typically an instruction in prose ("in part 2, replace the word X with Y"), not a diff. |
| **transitional provisions** (переходные положения) | There is no general act defining them; they live inside the act that introduces them, which is why the project **stores** them and does not **resolve** them. The word cannot be attributed to a single act, so it stays here until the rule for attributing it is written. |
| **редакция / revision / consolidated text** | One decision, three names. The domain's word is *редакция*; the schema says `version`; the research literature says *consolidated text*; and the official machine-readable channel that would settle it is windowed (§1.1). Which of them owns the meaning is decided with the identifier scheme (`ELI`), not row by row. |
| **"why an amendment happened"** | The subject of the initiative and the explanatory note are real, official and public — but the rule that connects an act to its draft is not written down in this repository. Until it is, the word stays here. |
| **verification coverage** | The share of units extracted against the number the source itself declares. Named in the reconnaissance of 2026-09-14 and needed by the manifest, but no document in this repository defines how it is computed — so its re-measurable form has to land in `SCOPE.md` before it becomes our word. |
| **effect of a written clarification** | Whether a written explanation changes liability, and with what force. Practitioners rely on them; no citation to that effect is written down here. |
| **`PoC`** | Used as a unit of scope in decisions ("this repository is a PoC"), with no acceptance criterion written anywhere — so it currently means whatever the speaker does. A candidate criterion exists in the working plan (a checkout on a date for one codex, with a verifiable chain to the source); until the project owner confirms it, the word stays here. |
| **`Phase 1` / `Phase 2`** | Two incompatible phase vocabularies coexist in this repository: the vision's `Phase 1 → Phase 2` and the code's `Phase 0 / 1 / 7A / 7C`. A glossary cannot hold two meanings for one word; this is resolved by the project owner, not by this file. |

## 5. How this file is checked

`scripts/tools/check_glossary.py` runs on this file (`uv run python scripts/tools/check_glossary.py docs/GLOSSARY.md`, also in the test suite). It checks **shape**, never truth or liveness:

- A **Defined by** cell may hold **several citations, separated by `;`** (for example: one act for
  publication, a second for entry into force). Each `;`-separated segment is checked **on its
  own**: a segment that carries a date, a `No.`, an `art.`, an act-type word, a URL or a markdown
  link must independently match one of the forms below — one valid citation elsewhere in the same
  cell does not cover a broken one next to it. A segment with none of those markers (plain
  connective text, e.g. `see §3 `ELI``) is not a citation and is not held to this standard.
- Every citation segment must match the citation form of its owner:
  - **the state** — *type + date + number + title*: the type **written out**, not abbreviated —
    `Federal Law`, `Federal Constitutional Law`, `Presidential Decree` (or `Decree of the President
    of the Russian Federation` / `Decree of the President`), `Government Decree` (or `Decree of the
    Government of the Russian Federation` / `Decree of the Government`) — the date as `DD.MM.YYYY`
    or `YYYY-MM-DD`, the number as `No. …`, the title in quotation marks; for the Constitution and
    the codes an article reference (`art. N`) is required and the title is optional; or the literal
    `citation unresolved`. An abbreviation of the type (`FZ`, `ФЗ`, …) is rejected even when the
    date, number and title are all otherwise present — the type must be spelled out, not stand in
    for the word;
  - **an outside document** — *name + version + URL*: the name must be one the checker knows and
    the URL's host must be one of the known homes of that document (the two lists are data at the
    top of the checker; a new standard is added there, not by loosening the rule); or the literal
    `citation unresolved`;
  - **this repository** — a relative link that resolves in the repository, without an anchor.
- A row in §1 may not cite a repository document in place of an act, segment by segment: a §1
  citation segment must be an act citation or say `citation unresolved`, not a repository link. A
  row that cannot produce its form moves to §4. That is the rule working, not the rule failing.
- Run the checker with `--verbose` to see, row by row, which form each citation segment matched
  (`a` = link, `b` = act citation, `c` = unresolved, `d` = standard) — the tool a human uses to see
  which citation actually carried the row.
- The **Meaning** column may not contain a count of our own coverage (rule 1): an integer followed
  by a counted noun, an "N of M", a percentage, or a bare large number outside a citation is a
  violation; digits inside dates, act and article numbers, versions and years of cited documents
  are not.
- **Liveness of a URL is not checked and is not promised.** Which official links survive is what
  the anchor reconnaissance measures; the checker validates the form of a citation, never that the
  link opens. The URLs in §3 answered on 2026-09-14; that is a measurement, not a guarantee.
- **Numbers are checked where numbers live** — [SCOPE.md](SCOPE.md), re-derived by running the
  commands in it, never by reading this file.
