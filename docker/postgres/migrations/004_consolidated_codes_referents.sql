-- =============================================================================
-- 004_consolidated_codes_referents.sql
--
-- Follow-up to 003. 003 anchored every code to a founding act; the review of
-- 2026-09-14 12:04 found that three of its columns silently change REFERENT
-- from row to row - the column says nothing about WHICH OBJECT it describes.
-- This migration makes the referent explicit instead of implied.
-- Idempotent: ADD COLUMN IF NOT EXISTS + UPDATE ... FROM VALUES.
--
-- -----------------------------------------------------------------------------
-- 1. official_url pointed at two different objects
-- -----------------------------------------------------------------------------
--   KAS_RF  -> publication.pravo.gov.ru/document/0001201503090041, i.e. the
--              official PUBLICATION OF THE ACT that enacted the code.
--   22 rows -> pravo.gov.ru/proxy/ips/?docbody=&nd=..., i.e. the ИПС RECORD OF
--              THE CODE, which shows the CURRENT CONSOLIDATED text, not the act
--              as enacted.
--   One column, two kinds of thing. A reader who follows official_url for GK_RF
--   expecting "the act of 30.11.1994" gets the code as amended to today.
--   Fix: `official_url_kind` ('act_publication' | 'code_record') now states which
--   object the URL identifies. No new URL columns are invented: there is exactly
--   one official_url per row and the kind column says what it points at.
--
-- -----------------------------------------------------------------------------
-- 2. KONST_RF mixed the act with the official text of the current edition
-- -----------------------------------------------------------------------------
--   The row carried founding_act_status = 'none' (correct: the Constitution was
--   adopted by referendum and has no number) together with
--   founding_act_eo_number = '0001202007040001'. That eoNumber is the portal id
--   of the OFFICIAL TEXT WITH THE 2020 AMENDMENTS, published 04.07.2020 - not of
--   any founding act. Storing it in a founding_act_* column asserted the exact
--   thing the status column denied.
--   Fix: new column `official_text_eo_number` holds it; founding_act_eo_number is
--   set NULL for KONST_RF. "Act" and "official text of the current edition" are
--   two different objects and now live in two different columns.
--
-- -----------------------------------------------------------------------------
-- 3. founding_act_title had two conventions at once
-- -----------------------------------------------------------------------------
--   KAS_RF read  «Федеральный закон от 08.03.2015 № 21-ФЗ "..."» (the act type),
--   22 rows read «Кодекс Российской Федерации от 30.11.1994 № 51-ФЗ "..."».
--   "Кодекс" is the ИПС DOCUMENT-TYPE CLASSIFICATION of the code record, not the
--   type of the adopting act: the act that enacted part one of the Civil Code is
--   a federal law. Two conventions in one column make the field unusable for
--   citation.
--
--   ONE CONVENTION, all 23 rows:
--       <act type> от DD.MM.YYYY № <number> «<official name of the code>»
--   where <act type> is «Федеральный закон» (or «Федеральный конституционный
--   закон» if a future code is enacted by one), the date and number are exactly
--   original_date / original_eo_number, and the name in guillemets is the code's
--   own official designation - the acts are titled simply «Гражданский кодекс
--   Российской Федерации (часть первая)», «Уголовный кодекс Российской
--   Федерации», «Кодекс Российской Федерации об административных
--   правонарушениях», with no "О введении в действие ..." wrapper.
--   Verified wording, 2026-09-14:
--     * publication.pravo.gov.ru/document/0001201503090041 prints the act as
--       `Федеральный закон от 08.03.2015 № 21-ФЗ "Кодекс административного
--       судопроизводства Российской Федерации"` - this is the portal's own
--       naming pattern and the pattern adopted here (straight quotes normalised
--       to Russian guillemets).
--     * the ИПС text of 51-ФЗ (?doc_itself=&nd=102033239) heads the act
--       «Гражданский кодекс Российской Федерации» with «ЧАСТЬ ПЕРВАЯ» on a
--       separate line; the ИПС card title renders it «Гражданский кодекс
--       Российской Федерации. Часть первая»; СЗ РФ / КонсультантПлюс / Гарант
--       cite it «Гражданский кодекс Российской Федерации (часть первая)».
--       The parenthesised lower-case form is the one adopted here, because it is
--       the citation form and it keeps the part inside the code's name rather
--       than turning it into a second sentence.
--   KONST_RF is the one row without an act type, date or number: the Constitution
--   was adopted by the all-Russian referendum of 12.12.1993 (no adopting law, no
--   number), so its title is simply «Конституция Российской Федерации».
--
--   Nothing verified is thrown away: the ИПС classification that the old titles
--   carried as a prefix moves to `ips_document_type` ('Кодекс' for the 21 ИПС
--   code records, 'Конституция' for KONST_RF, 'Федеральный закон' for the portal
--   act publication of KAS_RF). It describes the object at official_url.
--
-- -----------------------------------------------------------------------------
-- 4. "the portal starts in 2011" was a normative claim dressed as a measurement
-- -----------------------------------------------------------------------------
--   003 wrote "publication.pravo.gov.ru starts in 2011". The probes of
--   2026-09-14 did not measure that: searching the portal by act number returned
--   result sets whose EARLIEST records are from 2012. The corrected wording, used
--   in every comment below: official publication on the portal is normatively in
--   force from 2011 (per the portal's own description; the enabling act was NOT
--   re-verified in this session, so it is deliberately not cited), while the
--   earliest records found by search on 2026-09-14 were from 2012. Either way no
--   pre-2011 founding act has a portal eoNumber - which is the operative fact.
--
-- -----------------------------------------------------------------------------
-- 5. short_name is a display label, not a key
-- -----------------------------------------------------------------------------
--   «ВК РФ» is the short_name of BOTH VZK_RF (Воздушный кодекс) and VDK_RF
--   (Водный кодекс). Any lookup keyed on short_name silently picks one of two
--   different codes. Documented in a column comment and asserted by the seed test
--   (grep of src/ and scripts/ on 2026-09-14 found display uses only).
--
-- -----------------------------------------------------------------------------
-- 6. The unique index has no jurisdiction column (Stage 6 debt)
-- -----------------------------------------------------------------------------
--   uq_consolidated_codes_founding_act is (original_eo_number, original_date)
--   with no country/jurisdiction component, because consolidated_codes has no
--   such column at all - the table is implicitly Russia-only. A second country
--   adapter MUST add a jurisdiction column and extend this index, or two
--   countries' acts with the same number and date will collide.
--
-- -----------------------------------------------------------------------------
-- 7. Seed drift found while extending the test to every seeded column
-- -----------------------------------------------------------------------------
--   init.sql and the live DB disagreed on name/short_name/description for 8 rows
--   (live carried English descriptions such as 'Civil Code Part 2' and shortened
--   names from an older init.sql). Only init.sql writes this table, so the live
--   rows are stale. This migration brings them to the seed values, and the seed
--   now spells part names the same way the titles do, e.g.
--   «Гражданский кодекс Российской Федерации (часть вторая)».
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------

ALTER TABLE consolidated_codes
  ADD COLUMN IF NOT EXISTS official_url_kind VARCHAR(20),
  ADD COLUMN IF NOT EXISTS official_text_eo_number VARCHAR(100),
  ADD COLUMN IF NOT EXISTS ips_document_type VARCHAR(50);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'consolidated_codes_official_url_kind_check'
  ) THEN
    ALTER TABLE consolidated_codes
      ADD CONSTRAINT consolidated_codes_official_url_kind_check
      CHECK (official_url_kind IN ('act_publication', 'code_record'));
  END IF;
END
$$;

COMMENT ON COLUMN consolidated_codes.official_url IS
  'Canonical official URL for this row. WHAT IT POINTS AT VARIES BY ROW - read official_url_kind before using it: act_publication = the official publication of the adopting act itself; code_record = the ИПС record of the CODE, which shows the current consolidated text, not the act as enacted. Every URL verified HTTP 200 on 2026-09-14.';

COMMENT ON COLUMN consolidated_codes.official_url_kind IS
  'Which object official_url identifies. act_publication = publication.pravo.gov.ru publication of the adopting act (only KAS_RF: the portal covers 2011+ and no earlier founding act has an eoNumber). code_record = pravo.gov.ru/proxy/ips/ record of the code, i.e. the current consolidated text. Never assume: a row without this value has an unclassified URL.';

COMMENT ON COLUMN consolidated_codes.official_text_eo_number IS
  'Portal eoNumber of an officially published CONSOLIDATED TEXT of the code, if any - a DIFFERENT OBJECT from the founding act. Only KONST_RF has one: 0001202007040001, the official text with the amendments approved in the all-Russian vote of 01.07.2020, published 04.07.2020. Never put this value in founding_act_eo_number: the Constitution has no founding act with a number.';

COMMENT ON COLUMN consolidated_codes.ips_document_type IS
  'Document-type classification of the object at official_url, as its source states it: Кодекс (ИПС record of a code), Конституция (ИПС record of the Constitution), Федеральный закон (portal publication of an adopting act). This is a CLASSIFICATION, not the type of the adopting act - the act that enacted the Civil Code part one is a федеральный закон even though the ИПС record is typed Кодекс.';

COMMENT ON COLUMN consolidated_codes.founding_act_title IS
  'Official designation of the ADOPTING ACT, one convention for every row: "<act type> от DD.MM.YYYY № <number> «<official name of the code>»", act type = Федеральный закон (Федеральный конституционный закон where applicable), date and number identical to original_date/original_eo_number, name as the act itself designates the code - e.g. «Федеральный закон от 30.11.1994 № 51-ФЗ «Гражданский кодекс Российской Федерации (часть первая)»». NOT the ИПС document type (see ips_document_type). KONST_RF is the sole exception: adopted by referendum, no act type, date or number in the title - «Конституция Российской Федерации».';

COMMENT ON COLUMN consolidated_codes.founding_act_eo_number IS
  'Real publication.pravo.gov.ru eoNumber OF THE FOUNDING ACT (usable with /file/pdf?eoNumber= and /file/sig?eoNumber=). NULL for every pre-2011 act: official publication on the portal is normatively in force from 2011 (per the portal description; the enabling act was not re-verified here) and the earliest records found by search on 2026-09-14 were from 2012 - either way the portal holds no artifact for them. An eoNumber of a consolidated TEXT belongs in official_text_eo_number, not here.';

COMMENT ON COLUMN consolidated_codes.founding_act_status IS
  'known = adopting act verified against an official source; none = there is no adopting act with a number (KONST_RF: the Constitution was adopted by the all-Russian referendum of 12.12.1993); unknown = not established yet. Says nothing about official_text_eo_number, which describes a different object.';

COMMENT ON COLUMN consolidated_codes.short_name IS
  'DISPLAY LABEL ONLY - NOT A KEY AND NOT UNIQUE. «ВК РФ» is the label of both VZK_RF (Воздушный кодекс) and VDK_RF (Водный кодекс). Look codes up by `code`, never by short_name.';

COMMENT ON COLUMN consolidated_codes.name IS
  'Official name of the code (or of its part) in Russian, spelled as in the founding act title, e.g. «Гражданский кодекс Российской Федерации (часть вторая)».';

-- ---------------------------------------------------------------------------
-- Data
-- ---------------------------------------------------------------------------

UPDATE consolidated_codes c SET
  name                    = v.name,
  short_name              = v.short_name,
  description             = v.description,
  official_url_kind       = v.url_kind,
  ips_document_type       = v.ips_type,
  founding_act_title      = v.act_title,
  founding_act_eo_number  = v.act_eo,
  official_text_eo_number = v.text_eo
FROM (VALUES
  ('KONST_RF',
   'Конституция Российской Федерации', 'Конституция', 'Основной закон Российской Федерации',
   'code_record', 'Конституция',
   'Конституция Российской Федерации',
   NULL::varchar, '0001202007040001'::varchar),

  ('GK_RF',
   'Гражданский кодекс Российской Федерации (часть первая)', 'ГК РФ',
   'Основной нормативный акт, регулирующий гражданские правоотношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 30.11.1994 № 51-ФЗ «Гражданский кодекс Российской Федерации (часть первая)»',
   NULL, NULL),

  ('GK_RF_2',
   'Гражданский кодекс Российской Федерации (часть вторая)', 'ГК РФ ч.2',
   'Часть 2 Гражданского кодекса',
   'code_record', 'Кодекс',
   'Федеральный закон от 26.01.1996 № 14-ФЗ «Гражданский кодекс Российской Федерации (часть вторая)»',
   NULL, NULL),

  ('GK_RF_3',
   'Гражданский кодекс Российской Федерации (часть третья)', 'ГК РФ ч.3',
   'Часть 3 Гражданского кодекса',
   'code_record', 'Кодекс',
   'Федеральный закон от 26.11.2001 № 146-ФЗ «Гражданский кодекс Российской Федерации (часть третья)»',
   NULL, NULL),

  ('GK_RF_4',
   'Гражданский кодекс Российской Федерации (часть четвертая)', 'ГК РФ ч.4',
   'Часть 4 Гражданского кодекса',
   'code_record', 'Кодекс',
   'Федеральный закон от 18.12.2006 № 230-ФЗ «Гражданский кодекс Российской Федерации (часть четвертая)»',
   NULL, NULL),

  ('UK_RF',
   'Уголовный кодекс Российской Федерации', 'УК РФ',
   'Основной нормативный акт, определяющий преступность и наказуемость деяний',
   'code_record', 'Кодекс',
   'Федеральный закон от 13.06.1996 № 63-ФЗ «Уголовный кодекс Российской Федерации»',
   NULL, NULL),

  ('TK_RF',
   'Трудовой кодекс Российской Федерации', 'ТК РФ',
   'Кодекс законов, регулирующих трудовые отношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 30.12.2001 № 197-ФЗ «Трудовой кодекс Российской Федерации»',
   NULL, NULL),

  ('NK_RF',
   'Налоговый кодекс Российской Федерации (часть первая)', 'НК РФ',
   'Часть 1 Налогового кодекса',
   'code_record', 'Кодекс',
   'Федеральный закон от 31.07.1998 № 146-ФЗ «Налоговый кодекс Российской Федерации (часть первая)»',
   NULL, NULL),

  ('NK_RF_2',
   'Налоговый кодекс Российской Федерации (часть вторая)', 'НК РФ ч.2',
   'Часть 2 Налогового кодекса',
   'code_record', 'Кодекс',
   'Федеральный закон от 05.08.2000 № 117-ФЗ «Налоговый кодекс Российской Федерации (часть вторая)»',
   NULL, NULL),

  ('KoAP_RF',
   'Кодекс Российской Федерации об административных правонарушениях', 'КоАП РФ',
   'Основной нормативный акт, регулирующий административную ответственность',
   'code_record', 'Кодекс',
   'Федеральный закон от 30.12.2001 № 195-ФЗ «Кодекс Российской Федерации об административных правонарушениях»',
   NULL, NULL),

  ('SK_RF',
   'Семейный кодекс Российской Федерации', 'СК РФ',
   'Кодекс, регулирующий семейные отношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 29.12.1995 № 223-ФЗ «Семейный кодекс Российской Федерации»',
   NULL, NULL),

  ('ZhK_RF',
   'Жилищный кодекс Российской Федерации', 'ЖК РФ',
   'Кодекс, регулирующий жилищные отношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 29.12.2004 № 188-ФЗ «Жилищный кодекс Российской Федерации»',
   NULL, NULL),

  ('ZK_RF',
   'Земельный кодекс Российской Федерации', 'ЗК РФ',
   'Основной нормативный акт, регулирующий земельные отношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 25.10.2001 № 136-ФЗ «Земельный кодекс Российской Федерации»',
   NULL, NULL),

  ('APK_RF',
   'Арбитражный процессуальный кодекс Российской Федерации', 'АПК РФ',
   'Кодекс, регулирующий судопроизводство в арбитражных судах',
   'code_record', 'Кодекс',
   'Федеральный закон от 24.07.2002 № 95-ФЗ «Арбитражный процессуальный кодекс Российской Федерации»',
   NULL, NULL),

  ('GPK_RF',
   'Гражданский процессуальный кодекс Российской Федерации', 'ГПК РФ',
   'Кодекс, регулирующий судопроизводство в судах общей юрисдикции',
   'code_record', 'Кодекс',
   'Федеральный закон от 14.11.2002 № 138-ФЗ «Гражданский процессуальный кодекс Российской Федерации»',
   NULL, NULL),

  ('UPK_RF',
   'Уголовно-процессуальный кодекс Российской Федерации', 'УПК РФ',
   'Кодекс, регулирующий уголовное судопроизводство',
   'code_record', 'Кодекс',
   'Федеральный закон от 18.12.2001 № 174-ФЗ «Уголовно-процессуальный кодекс Российской Федерации»',
   NULL, NULL),

  ('BK_RF',
   'Бюджетный кодекс Российской Федерации', 'БК РФ',
   'Кодекс, регулирующий бюджетные отношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 31.07.1998 № 145-ФЗ «Бюджетный кодекс Российской Федерации»',
   NULL, NULL),

  ('GRK_RF',
   'Градостроительный кодекс Российской Федерации', 'ГрК РФ',
   'Кодекс, регулирующий градостроительную деятельность',
   'code_record', 'Кодекс',
   'Федеральный закон от 29.12.2004 № 190-ФЗ «Градостроительный кодекс Российской Федерации»',
   NULL, NULL),

  ('UIK_RF',
   'Уголовно-исполнительный кодекс Российской Федерации', 'УИК РФ',
   'Кодекс, регулирующий исполнение уголовных наказаний',
   'code_record', 'Кодекс',
   'Федеральный закон от 08.01.1997 № 1-ФЗ «Уголовно-исполнительный кодекс Российской Федерации»',
   NULL, NULL),

  ('VZK_RF',
   'Воздушный кодекс Российской Федерации', 'ВК РФ',
   'Кодекс, регулирующий использование воздушного пространства',
   'code_record', 'Кодекс',
   'Федеральный закон от 19.03.1997 № 60-ФЗ «Воздушный кодекс Российской Федерации»',
   NULL, NULL),

  ('VDK_RF',
   'Водный кодекс Российской Федерации', 'ВК РФ',
   'Кодекс, регулирующий водные отношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 03.06.2006 № 74-ФЗ «Водный кодекс Российской Федерации»',
   NULL, NULL),

  ('LK_RF',
   'Лесной кодекс Российской Федерации', 'ЛК РФ',
   'Кодекс, регулирующий лесные отношения',
   'code_record', 'Кодекс',
   'Федеральный закон от 04.12.2006 № 200-ФЗ «Лесной кодекс Российской Федерации»',
   NULL, NULL),

  ('KAS_RF',
   'Кодекс административного судопроизводства Российской Федерации', 'КАС РФ',
   'Кодекс, регулирующий административное судопроизводство',
   'act_publication', 'Федеральный закон',
   'Федеральный закон от 08.03.2015 № 21-ФЗ «Кодекс административного судопроизводства Российской Федерации»',
   '0001201503090041', NULL)
) AS v(code, name, short_name, description, url_kind, ips_type, act_title, act_eo, text_eo)
WHERE c.code = v.code;

-- ---------------------------------------------------------------------------
-- Guard rails
-- ---------------------------------------------------------------------------

-- The index has no jurisdiction component because the table has no jurisdiction
-- column. Stage 6 debt: a second country adapter must add one and extend this.
COMMENT ON INDEX uq_consolidated_codes_founding_act IS
  'A founding act is identified by (number, date), never by the number alone: 146-ФЗ is both NK_RF (31.07.1998) and GK_RF_3 (26.11.2001). NO JURISDICTION COLUMN IS INCLUDED because consolidated_codes has none - the table is implicitly Russia-only. Stage 6 debt: a second country adapter MUST add a jurisdiction column and extend this index, otherwise two countries'' acts sharing a number and date will collide.';

DO $$
DECLARE
  bad INTEGER;
BEGIN
  SELECT count(*) INTO bad FROM consolidated_codes
   WHERE official_url_kind IS NULL
      OR founding_act_title IS NULL
      OR ips_document_type IS NULL;
  IF bad > 0 THEN
    RAISE EXCEPTION 'consolidated_codes: % row(s) lack official_url_kind / founding_act_title / ips_document_type', bad;
  END IF;

  -- act_publication must point at the very eoNumber it claims.
  SELECT count(*) INTO bad FROM consolidated_codes
   WHERE official_url_kind = 'act_publication'
     AND (founding_act_eo_number IS NULL OR official_url NOT LIKE '%' || founding_act_eo_number || '%');
  IF bad > 0 THEN
    RAISE EXCEPTION 'consolidated_codes: % act_publication row(s) whose URL does not carry founding_act_eo_number', bad;
  END IF;

  -- A code_record URL must be an ИПС record, never a portal act publication.
  SELECT count(*) INTO bad FROM consolidated_codes
   WHERE official_url_kind = 'code_record' AND official_url NOT LIKE '%pravo.gov.ru/proxy/ips/%';
  IF bad > 0 THEN
    RAISE EXCEPTION 'consolidated_codes: % code_record row(s) whose URL is not an ИПС record', bad;
  END IF;

  -- The Constitution has no founding act: the 2020 official text is not one.
  SELECT count(*) INTO bad FROM consolidated_codes
   WHERE founding_act_status = 'none' AND founding_act_eo_number IS NOT NULL;
  IF bad > 0 THEN
    RAISE EXCEPTION 'consolidated_codes: % row(s) claim status none yet carry a founding-act eoNumber', bad;
  END IF;

  -- One title convention: act type + date + number + name, or the Constitution.
  SELECT count(*) INTO bad FROM consolidated_codes
   WHERE founding_act_title !~ '^Федеральный (конституционный )?закон от [0-9]{2}\.[0-9]{2}\.[0-9]{4} № '
     AND founding_act_title <> 'Конституция Российской Федерации';
  IF bad > 0 THEN
    RAISE EXCEPTION 'consolidated_codes: % founding_act_title(s) do not follow the single title convention', bad;
  END IF;

  RAISE NOTICE 'consolidated_codes: referents explicit; short_name «ВК РФ» is shared by VZK_RF and VDK_RF by design (display label, not a key)';
END
$$;

COMMIT;
