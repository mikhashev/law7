-- =============================================================================
-- 003_consolidated_codes_official_acts.sql
--
-- Fixes the top edge of the provenance chain: code -> founding official act.
-- Idempotent: safe to re-run (ADD COLUMN IF NOT EXISTS + UPDATE ... FROM VALUES).
--
-- -----------------------------------------------------------------------------
-- What was wrong before
-- -----------------------------------------------------------------------------
--   * `original_eo_number` was commented "Original law number" and holds values
--     like '51-ФЗ'. That is the NUMBER OF THE ACT, not the publication portal's
--     `eoNumber` (the 16-digit identifier accepted by
--     publication.pravo.gov.ru/file/pdf?eoNumber=... and /file/sig?eoNumber=...).
--     The name invited confusion between the two; the comment now says so.
--   * Copy-paste errors in init.sql: GK_RF_2 / GK_RF_3 / GK_RF_4 carried part
--     one's act (51-ФЗ, 1994-11-30) and NK_RF_2 carried part one's act (146-ФЗ).
--   * Wrong dates: NK_RF held 2000-07-31 (mixes part 2's year with part 1's day)
--     instead of 1998-07-31; UK_RF held 1996-05-24, the State Duma ADOPTION date,
--     while the act is cited as "от 13.06.1996 № 63-ФЗ".
--   * In the live DB 8 rows (KONST_RF, GK_RF_2/3/4, NK_RF_2, APK_RF, GPK_RF,
--     UPK_RF) had a NULL act number - and NULL was used both for "there is no
--     number" (Constitution) and for "we never filled it in" (APK/GPK/UPK).
--   * `official_url` was NULL for all 23 rows, so nothing anchored a code to an
--     official publication.
--
-- -----------------------------------------------------------------------------
-- Conventions fixed here (read before adding a row)
-- -----------------------------------------------------------------------------
-- 1. `original_date` = the date the act is CITED BY, i.e. the signing /
--    promulgation date that appears in "от DD.MM.YYYY № N". It is NOT the State
--    Duma adoption date, NOT the first publication date and NOT the entry-into-
--    force date. First publication now lives in `founding_act_published_at`.
--    For KONST_RF the cited date is the referendum date, 12.12.1993.
--
-- 2. `founding_act_status` distinguishes three states that NULL used to blur:
--      'known'   - we verified the act against an official source;
--      'none'    - the act legitimately has no number (Constitution: adopted by
--                  referendum, cited "от 12.12.1993 б/н");
--      'unknown' - not established yet. No row should be left in this state.
--
-- 3. `code` MIXES TWO LEVELS: a whole code (UK_RF) and a PART of a code
--    (GK_RF / GK_RF_2 / GK_RF_3 / GK_RF_4 are four founding acts of ONE code;
--    NK_RF / NK_RF_2 are two). Each part therefore carries its OWN founding act
--    in its own row, which is correct data under an incorrect identifier scheme.
--    The identifier decision (ELI-style work / expression / manifestation, i.e.
--    a separate "code" entity with "part" children) is PENDING - nothing is
--    renamed or restructured by this migration.
--
-- 4. ACT-NUMBER COLLISION INSIDE OUR OWN ROWS: NK_RF (part 1 of the Tax Code) is
--    146-ФЗ of 31.07.1998 and GK_RF_3 (part 3 of the Civil Code) is 146-ФЗ of
--    26.11.2001. Federal law numbers restart every year, so a lookup MUST key on
--    (original_eo_number, original_date) and NEVER on the number alone. The
--    partial unique index below enforces exactly that pair and lets the
--    collision stand. Test query (expects one row, count = 2):
--      SELECT original_eo_number, count(*), array_agg(code ORDER BY code)
--        FROM consolidated_codes
--       GROUP BY original_eo_number HAVING count(*) > 1;
--
-- -----------------------------------------------------------------------------
-- Portal anchoring - verified 2026-09-14, two independent probes
-- -----------------------------------------------------------------------------
--   (a) GET /api/Documents?DocumentDateFrom=<d>&DocumentDateTo=<d>&PageSize=100
--       for each founding act date: itemsTotalCount = 0 for all 22 pre-2011
--       dates; 49 for 08.03.2015 (KAS_RF).
--   (b) GET /api/Documents?Number=<n>&NumberSearchType=0&PageSize=100 for each
--       act number across the whole portal: every result set starts in 2012 and
--       none carries the founding date; only 21-ФЗ returns 0001201503090041.
--   publication.pravo.gov.ru starts in 2011, so pre-2011 founding acts have NO
--   eoNumber and therefore NO portal-signed artifact: the act is known by
--   citation, its official bytes are not machine-retrievable from the portal,
--   and `official_url` points at ИПС «Законодательство России» instead.
--
--   Only KAS_RF has a founding-act eoNumber: 0001201503090041 (published
--   09.03.2015). The Constitution's founding act (12.12.1993) has none; its
--   official text as amended in 2020 was published on the portal on 04.07.2020
--   as eoNumber 0001202007040001, and that is what KONST_RF records, because it
--   is the only portal artifact carrying the current text. (The amendment law
--   itself, 1-ФКЗ of 14.03.2020, is eoNumber 0001202003140001 - not stored here,
--   it is an amendment, not a founding act.)
--
--   `founding_act_published_at` is the earliest official publication date we
--   could verify WITH AN EXACT DAY from ИПС: Российская газета / Парламентская
--   газета / pravo.gov.ru. ИПС dates Собрание законодательства РФ only by year
--   and issue number, so for some rows an СЗ РФ publication may be a few days
--   earlier than the value stored here. Treat it as "first verifiable dated
--   publication", not as a legal statement about the first publication.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Schema: honest comments + new columns
-- ---------------------------------------------------------------------------

ALTER TABLE consolidated_codes
  ADD COLUMN IF NOT EXISTS founding_act_title TEXT,
  ADD COLUMN IF NOT EXISTS founding_act_eo_number VARCHAR(100),
  ADD COLUMN IF NOT EXISTS founding_act_status VARCHAR(20) DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS founding_act_published_at DATE;

COMMENT ON COLUMN consolidated_codes.code IS
  'Identifier that currently mixes a whole code (UK_RF) with a PART of a code (GK_RF/GK_RF_2/3/4 = one code, four founding acts; NK_RF/NK_RF_2 = one code, two). ELI-style work/expression split is pending.';
COMMENT ON COLUMN consolidated_codes.original_eo_number IS
  'Number of the founding act (e.g. 51-ФЗ), not a portal eoNumber. Federal law numbers restart every year, so always key lookups on (original_eo_number, original_date): 146-ФЗ is both NK_RF (31.07.1998) and GK_RF_3 (26.11.2001).';
COMMENT ON COLUMN consolidated_codes.original_date IS
  'Date the founding act is cited by: the signing/promulgation date in "от DD.MM.YYYY № N" - NOT the Duma adoption date, NOT the publication date (see founding_act_published_at), NOT the in-force date. For KONST_RF: the 12.12.1993 referendum date.';
COMMENT ON COLUMN consolidated_codes.official_url IS
  'Canonical official URL of the founding act: publication.pravo.gov.ru when the act has an eoNumber (2011+), otherwise the ИПС «Законодательство России» record at pravo.gov.ru/proxy/ips/. Every URL verified HTTP 200 on 2026-09-14.';
COMMENT ON COLUMN consolidated_codes.founding_act_title IS
  'Full official designation of the founding act in Russian, as it appears in the official source.';
COMMENT ON COLUMN consolidated_codes.founding_act_eo_number IS
  'Real publication.pravo.gov.ru eoNumber (usable with /file/pdf?eoNumber= and /file/sig?eoNumber=); NULL for pre-2011 acts, which the portal does not cover.';
COMMENT ON COLUMN consolidated_codes.founding_act_status IS
  'known = act verified against an official source; none = act legitimately has no number (Constitution, adopted by referendum); unknown = not established yet.';
COMMENT ON COLUMN consolidated_codes.founding_act_published_at IS
  'Earliest official publication date verifiable with an exact day (Российская газета / Парламентская газета / pravo.gov.ru). ИПС dates СЗ РФ only by year+issue, so an СЗ РФ publication may precede this by a few days.';

-- Constrain the three states so a future insert cannot invent a fourth.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'consolidated_codes_founding_act_status_check'
  ) THEN
    ALTER TABLE consolidated_codes
      ADD CONSTRAINT consolidated_codes_founding_act_status_check
      CHECK (founding_act_status IN ('known', 'none', 'unknown'));
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 2. Data: correct all 23 rows
-- ---------------------------------------------------------------------------

UPDATE consolidated_codes c SET
  original_eo_number        = v.act_number,
  original_date             = v.act_date::date,
  official_url              = v.official_url,
  founding_act_title        = v.act_title,
  founding_act_eo_number    = v.eo_number,
  founding_act_status       = v.act_status,
  founding_act_published_at = v.published_at::date
FROM (VALUES
  ('KONST_RF', NULL::varchar, '1993-12-12',
   'Конституция Российской Федерации (принята всенародным голосованием 12.12.1993; официальный текст с изменениями, одобренными в ходе общероссийского голосования 01.07.2020, опубликован 04.07.2020)',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102027595', '0001202007040001', 'none', '1993-12-25'),

  ('GK_RF',    '51-ФЗ',  '1994-11-30',
   'Кодекс Российской Федерации от 30.11.1994 № 51-ФЗ «Гражданский кодекс Российской Федерации. Часть первая»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102033239', NULL, 'known', '1994-12-08'),

  ('GK_RF_2',  '14-ФЗ',  '1996-01-26',
   'Кодекс Российской Федерации от 26.01.1996 № 14-ФЗ «Гражданский кодекс Российской Федерации. Часть вторая»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102039276', NULL, 'known', '1996-02-10'),

  ('GK_RF_3',  '146-ФЗ', '2001-11-26',
   'Кодекс Российской Федерации от 26.11.2001 № 146-ФЗ «Гражданский кодекс Российской Федерации. Часть третья»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102073578', NULL, 'known', '2001-11-28'),

  ('GK_RF_4',  '230-ФЗ', '2006-12-18',
   'Кодекс Российской Федерации от 18.12.2006 № 230-ФЗ «Гражданский кодекс Российской Федерации. Часть четвертая»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102110716', NULL, 'known', '2006-12-21'),

  ('UK_RF',    '63-ФЗ',  '1996-06-13',
   'Кодекс Российской Федерации от 13.06.1996 № 63-ФЗ «Уголовный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102041891', NULL, 'known', '1996-06-19'),

  ('TK_RF',    '197-ФЗ', '2001-12-30',
   'Кодекс Российской Федерации от 30.12.2001 № 197-ФЗ «Трудовой кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102074279', NULL, 'known', '2001-12-31'),

  ('NK_RF',    '146-ФЗ', '1998-07-31',
   'Кодекс Российской Федерации от 31.07.1998 № 146-ФЗ «Налоговый кодекс Российской Федерации. Часть первая»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102054722', NULL, 'known', '1998-08-06'),

  ('NK_RF_2',  '117-ФЗ', '2000-08-05',
   'Кодекс Российской Федерации от 05.08.2000 № 117-ФЗ «Налоговый кодекс Российской Федерации. Часть вторая»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102067058', NULL, 'known', '2000-08-10'),

  ('KoAP_RF',  '195-ФЗ', '2001-12-30',
   'Кодекс Российской Федерации от 30.12.2001 № 195-ФЗ «Кодекс Российской Федерации об административных правонарушениях»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102074277', NULL, 'known', '2001-12-31'),

  ('SK_RF',    '223-ФЗ', '1995-12-29',
   'Кодекс Российской Федерации от 29.12.1995 № 223-ФЗ «Семейный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102038925', NULL, 'known', '1996-01-27'),

  ('ZhK_RF',   '188-ФЗ', '2004-12-29',
   'Кодекс Российской Федерации от 29.12.2004 № 188-ФЗ «Жилищный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102090645', NULL, 'known', '2005-01-12'),

  ('ZK_RF',    '136-ФЗ', '2001-10-25',
   'Кодекс Российской Федерации от 25.10.2001 № 136-ФЗ «Земельный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102073184', NULL, 'known', '2001-10-30'),

  ('APK_RF',   '95-ФЗ',  '2002-07-24',
   'Кодекс Российской Федерации от 24.07.2002 № 95-ФЗ «Арбитражный процессуальный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102079219', NULL, 'known', '2002-07-27'),

  ('GPK_RF',   '138-ФЗ', '2002-11-14',
   'Кодекс Российской Федерации от 14.11.2002 № 138-ФЗ «Гражданский процессуальный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102078828', NULL, 'known', '2002-11-20'),

  ('UPK_RF',   '174-ФЗ', '2001-12-18',
   'Кодекс Российской Федерации от 18.12.2001 № 174-ФЗ «Уголовно-процессуальный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102073942', NULL, 'known', '2001-12-22'),

  ('BK_RF',    '145-ФЗ', '1998-07-31',
   'Кодекс Российской Федерации от 31.07.1998 № 145-ФЗ «Бюджетный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102054721', NULL, 'known', '1998-08-12'),

  ('GRK_RF',   '190-ФЗ', '2004-12-29',
   'Кодекс Российской Федерации от 29.12.2004 № 190-ФЗ «Градостроительный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102090643', NULL, 'known', '2004-12-30'),

  ('UIK_RF',   '1-ФЗ',   '1997-01-08',
   'Кодекс Российской Федерации от 08.01.1997 № 1-ФЗ «Уголовно-исполнительный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102045146', NULL, 'known', '1997-01-16'),

  ('VZK_RF',   '60-ФЗ',  '1997-03-19',
   'Кодекс Российской Федерации от 19.03.1997 № 60-ФЗ «Воздушный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102046246', NULL, 'known', '1997-03-26'),

  ('VDK_RF',   '74-ФЗ',  '2006-06-03',
   'Кодекс Российской Федерации от 03.06.2006 № 74-ФЗ «Водный кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102107048', NULL, 'known', '2006-06-08'),

  ('LK_RF',    '200-ФЗ', '2006-12-04',
   'Кодекс Российской Федерации от 04.12.2006 № 200-ФЗ «Лесной кодекс Российской Федерации»',
   'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102110364', NULL, 'known', '2006-12-08'),

  ('KAS_RF',   '21-ФЗ',  '2015-03-08',
   'Федеральный закон от 08.03.2015 № 21-ФЗ «Кодекс административного судопроизводства Российской Федерации»',
   'http://publication.pravo.gov.ru/document/0001201503090041', '0001201503090041', 'known', '2015-03-09')
) AS v(code, act_number, act_date, act_title, official_url, eo_number, act_status, published_at)
WHERE c.code = v.code;

-- ---------------------------------------------------------------------------
-- 3. Guard rails
-- ---------------------------------------------------------------------------

-- A founding act is identified by (number, date), never by the number alone.
-- This index permits the expected 146-ФЗ collision (NK_RF 1998 vs GK_RF_3 2001)
-- while blocking a genuine duplicate of the same act on two rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_consolidated_codes_founding_act
  ON consolidated_codes (original_eo_number, original_date)
  WHERE original_eo_number IS NOT NULL;

-- Report the expected collision and fail loudly if any row is left 'unknown'.
DO $$
DECLARE
  rec         RECORD;
  unknown_cnt INTEGER;
BEGIN
  FOR rec IN
    SELECT original_eo_number AS num, count(*) AS n, array_agg(code ORDER BY code) AS codes
      FROM consolidated_codes
     WHERE original_eo_number IS NOT NULL
     GROUP BY original_eo_number
    HAVING count(*) > 1
  LOOP
    RAISE NOTICE 'expected act-number collision: % used by % rows %', rec.num, rec.n, rec.codes;
  END LOOP;

  SELECT count(*) INTO unknown_cnt
    FROM consolidated_codes
   WHERE founding_act_status = 'unknown' OR official_url IS NULL;
  IF unknown_cnt > 0 THEN
    RAISE EXCEPTION 'consolidated_codes: % row(s) still lack a verified founding act', unknown_cnt;
  END IF;
END
$$;

COMMIT;
