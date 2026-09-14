-- Law7 Database Schema
-- PostgreSQL 15+
-- Based on pravo.gov.ru API structure analysis

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For trigram text search

-- =============================================================================
-- Countries (for multi-country support)
-- =============================================================================
CREATE TABLE IF NOT EXISTS countries (
  id SERIAL PRIMARY KEY,
  code VARCHAR(2) UNIQUE NOT NULL,
  name VARCHAR(100) NOT NULL,
  native_name VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Publication Blocks (from /api/PublicBlocks/)
-- Categories like: president, government, court, subjects, international
-- =============================================================================
CREATE TABLE IF NOT EXISTS publication_blocks (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  short_name VARCHAR(200),
  menu_name VARCHAR(200),
  code VARCHAR(50) UNIQUE NOT NULL,  -- 'president', 'government', 'court', etc.
  description TEXT,
  weight INTEGER,
  is_blocked BOOLEAN DEFAULT FALSE,
  has_children BOOLEAN DEFAULT FALSE,
  is_agencies_of_state_authorities BOOLEAN DEFAULT FALSE,
  image_id VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Signatory Authorities (from /api/SignatoryAuthorities/)
-- Organizations that sign/issue documents
-- =============================================================================
CREATE TABLE IF NOT EXISTS signatory_authorities (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(500) NOT NULL,
  code VARCHAR(100),
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Document Types (from /api/DocumentTypes/)
-- Types like: federal-law, presidential-decree, government-resolution, etc.
-- =============================================================================
CREATE TABLE IF NOT EXISTS document_types (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(200) NOT NULL,
  code VARCHAR(50) UNIQUE,
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Categories (from /api/Categories)
-- Additional categorization for documents
-- =============================================================================
CREATE TABLE IF NOT EXISTS categories (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(500),
  code VARCHAR(100),
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Documents (main table, based on /api/Documents response)
-- =============================================================================
CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Natural key from pravo.gov.ru
  eo_number VARCHAR(50) UNIQUE NOT NULL,

  -- Document names and titles
  title TEXT,                      -- Full title with HTML formatting
  name TEXT,                       -- Short name/description (can be very long)
  complex_name TEXT,               -- Full name with date and number

  -- Document identification
  document_number VARCHAR(100),    -- Number like "28-р"
  document_date DATE,              -- Date of document adoption
  publish_date DATE,               -- Date of publication
  view_date VARCHAR(20),           -- Date in DD.MM.YYYY format

  -- Document metadata
  pages_count INTEGER,
  pdf_file_size BIGINT,
  has_svg BOOLEAN DEFAULT FALSE,
  zip_file_length BIGINT,

  -- Ministry of Justice registration
  jd_reg_number VARCHAR(100),
  jd_reg_date DATE,

  -- Foreign keys
  signatory_authority_id UUID REFERENCES signatory_authorities(id) ON DELETE SET NULL,
  document_type_id UUID REFERENCES document_types(id) ON DELETE SET NULL,
  publication_block_id UUID REFERENCES publication_blocks(id) ON DELETE SET NULL,
  category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
  country_id INTEGER REFERENCES countries(id) ON DELETE CASCADE,

  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Document Content (separate table for full text and file URLs)
-- =============================================================================
CREATE TABLE IF NOT EXISTS document_content (
  document_id UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  full_text TEXT,                   -- Extracted and cleaned text
  raw_text TEXT,                    -- Original extracted text
  text_hash VARCHAR(64),            -- Hash for change detection
  pdf_url TEXT,                     -- URL to download PDF
  html_url TEXT,                    -- URL to HTML version
  updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Indexes for performance
-- =============================================================================

-- Documents indexes
CREATE INDEX IF NOT EXISTS idx_documents_eo_number ON documents(eo_number);
CREATE INDEX IF NOT EXISTS idx_documents_document_date ON documents(document_date DESC);
CREATE INDEX IF NOT EXISTS idx_documents_publish_date ON documents(publish_date DESC);
CREATE INDEX IF NOT EXISTS idx_documents_signatory_authority ON documents(signatory_authority_id);
CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type_id);
CREATE INDEX IF NOT EXISTS idx_documents_publication_block ON documents(publication_block_id);
CREATE INDEX IF NOT EXISTS idx_documents_country ON documents(country_id);

-- Full-text search indexes (Russian and English)
CREATE INDEX IF NOT EXISTS idx_documents_name_trgm ON documents USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING gin(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_complex_name_trgm ON documents USING gin(complex_name gin_trgm_ops);

-- Document content full-text search
CREATE INDEX IF NOT EXISTS idx_document_content_full_text_russian ON document_content
  USING gin(to_tsvector('russian', full_text));
CREATE INDEX IF NOT EXISTS idx_document_content_full_text_english ON document_content
  USING gin(to_tsvector('english', full_text));
CREATE INDEX IF NOT EXISTS idx_document_content_raw_text_trgm ON document_content
  USING gin(raw_text gin_trgm_ops);

-- Reference table indexes
CREATE INDEX IF NOT EXISTS idx_publication_blocks_code ON publication_blocks(code);
CREATE INDEX IF NOT EXISTS idx_signatory_authorities_name ON signatory_authorities(name);
CREATE INDEX IF NOT EXISTS idx_document_types_code ON document_types(code);
CREATE INDEX IF NOT EXISTS idx_categories_code ON categories(code);

-- =============================================================================
-- Views for common queries
-- =============================================================================

-- Recent documents view (last 30 days)
CREATE OR REPLACE VIEW recent_documents AS
SELECT
  d.id,
  d.eo_number,
  d.title,
  d.name,
  d.complex_name,
  d.document_number,
  d.document_date,
  d.publish_date,
  d.pages_count,
  c.code AS country_code,
  pb.code AS publication_block_code,
  pb.short_name AS publication_block_name,
  dt.name AS document_type_name,
  sa.name AS signatory_authority_name
FROM documents d
JOIN countries c ON d.country_id = c.id
LEFT JOIN publication_blocks pb ON d.publication_block_id = pb.id
LEFT JOIN document_types dt ON d.document_type_id = dt.id
LEFT JOIN signatory_authorities sa ON d.signatory_authority_id = sa.id
WHERE d.publish_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY d.publish_date DESC;

-- =============================================================================
-- Consolidated codes metadata (tracks base codes)
-- Created here (before "Initial data") because the INSERT below populates it.
-- =============================================================================
CREATE TABLE IF NOT EXISTS consolidated_codes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  -- NOTE: `code` currently MIXES two levels - a whole code ('UK_RF') and a PART
  -- of a code ('GK_RF' + 'GK_RF_2/3/4' are four founding acts of ONE code;
  -- 'NK_RF' + 'NK_RF_2' are two). Each part carries its own founding act below.
  -- The ELI-style work/expression split is PENDING; nothing is renamed yet.
  code VARCHAR(50) UNIQUE NOT NULL,  -- 'GK_RF', 'TK_RF', etc.
  name VARCHAR(500) NOT NULL,  -- Official name of the code (or of its part), spelled as in the
                               -- founding act title: «Гражданский кодекс Российской Федерации (часть вторая)»
  short_name VARCHAR(100),  -- DISPLAY LABEL ONLY - NOT A KEY AND NOT UNIQUE: «ВК РФ» is the label of
                            -- both VZK_RF (Воздушный) and VDK_RF (Водный). Look up by `code`.
  description TEXT,

  -- Founding official act (see migrations/003_consolidated_codes_official_acts.sql)
  original_eo_number VARCHAR(100),  -- Number of the founding act (e.g. 51-ФЗ), NOT a portal eoNumber.
                                    -- Law numbers restart yearly: key on (number, date), never number alone
                                    -- (146-ФЗ is both NK_RF 31.07.1998 and GK_RF_3 26.11.2001).
  original_date DATE,  -- Date the act is cited by: signing/promulgation date in "от DD.MM.YYYY № N".
                       -- NOT the Duma adoption date, NOT the publication date, NOT the in-force date.
  official_url TEXT,  -- Canonical official URL. WHAT IT POINTS AT VARIES BY ROW - always read
                      -- official_url_kind first (see migrations/004_consolidated_codes_referents.sql).
  official_url_kind VARCHAR(20)
    CHECK (official_url_kind IN ('act_publication', 'code_record')),
    -- Which OBJECT official_url identifies:
    --   'act_publication' = publication.pravo.gov.ru publication of the adopting ACT (only KAS_RF);
    --   'code_record'     = ИПС record of the CODE, i.e. the current consolidated TEXT, not the act.
  ips_document_type VARCHAR(50),  -- Document-type classification of the object at official_url, as its
                                  -- source states it: 'Кодекс' / 'Конституция' / 'Федеральный закон'.
                                  -- A CLASSIFICATION, not the type of the adopting act.
  founding_act_title TEXT,  -- Official designation of the ADOPTING ACT, one convention for every row:
                            -- "<тип акта> от DD.MM.YYYY № <номер> «<официальное наименование кодекса>»",
                            -- тип акта = Федеральный закон (Федеральный конституционный закон where
                            -- applicable); date/number identical to original_date/original_eo_number.
                            -- NOT the ИПС document type. KONST_RF is the sole exception (adopted by
                            -- referendum, no type/date/number): «Конституция Российской Федерации».
  founding_act_eo_number VARCHAR(100),  -- Real portal eoNumber OF THE FOUNDING ACT (works with
                                        -- /file/pdf?eoNumber= and /file/sig?eoNumber=). NULL for every
                                        -- pre-2011 act. An eoNumber of a consolidated TEXT goes to
                                        -- official_text_eo_number, never here.
  official_text_eo_number VARCHAR(100),  -- Portal eoNumber of an officially published CONSOLIDATED TEXT,
                                         -- if any - A DIFFERENT OBJECT FROM THE FOUNDING ACT. Only
                                         -- KONST_RF: 0001202007040001, the official text with the 2020
                                         -- amendments, published 04.07.2020.
  founding_act_status VARCHAR(20) DEFAULT 'unknown'
    CHECK (founding_act_status IN ('known', 'none', 'unknown')),
    -- known = adopting act verified against an official source; none = there is no adopting act with a
    -- number (Constitution, adopted by referendum); unknown = not established yet. Says nothing about
    -- official_text_eo_number, which describes a different object.
  founding_act_published_at DATE,  -- Earliest official publication date verifiable with an exact day
                                   -- (Российская газета / Парламентская газета / pravo.gov.ru).
                                   -- ИПС dates СЗ РФ only by year+issue, so СЗ РФ may precede this.

  -- Consolidation status
  last_amended_date DATE,  -- Date of most recent amendment
  total_amendments INTEGER DEFAULT 0,  -- Total amendments applied
  is_consolidated BOOLEAN DEFAULT FALSE,  -- Whether consolidation is complete
  last_consolidated_at TIMESTAMP,  -- When last consolidation ran
  source VARCHAR(50),  -- Where the base text came from (e.g. 'pravo.gov.ru', 'government.ru')

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consolidated_codes_code ON consolidated_codes(code);
CREATE INDEX IF NOT EXISTS idx_consolidated_codes_consolidated ON consolidated_codes(is_consolidated);
CREATE INDEX IF NOT EXISTS idx_consolidated_codes_source ON consolidated_codes(source);

-- A founding act is identified by (number, date), never by the number alone.
-- Permits the expected 146-ФЗ collision (NK_RF 1998 vs GK_RF_3 2001), blocks a
-- genuine duplicate of the same act on two rows.
-- NO JURISDICTION COLUMN IS INCLUDED because consolidated_codes has none - the
-- table is implicitly Russia-only. Stage 6 debt: a second country adapter MUST
-- add a jurisdiction column and extend this index, otherwise two countries' acts
-- sharing a number and a date will collide here.
CREATE UNIQUE INDEX IF NOT EXISTS uq_consolidated_codes_founding_act
  ON consolidated_codes (original_eo_number, original_date)
  WHERE original_eo_number IS NOT NULL;

-- Same comments a migrated database carries, so a clean install is not poorer in
-- metadata than an upgraded one. Full rationale: migrations 003 and 004.
COMMENT ON COLUMN consolidated_codes.code IS
  'Identifier that currently mixes a whole code (UK_RF) with a PART of a code (GK_RF/GK_RF_2/3/4 = one code, four founding acts; NK_RF/NK_RF_2 = one code, two). ELI-style work/expression split is pending.';
COMMENT ON COLUMN consolidated_codes.name IS
  'Official name of the code (or of its part) in Russian, spelled as in the founding act title, e.g. «Гражданский кодекс Российской Федерации (часть вторая)».';
COMMENT ON COLUMN consolidated_codes.original_eo_number IS
  'Number of the founding act (e.g. 51-ФЗ), not a portal eoNumber. Federal law numbers restart every year, so always key lookups on (original_eo_number, original_date): 146-ФЗ is both NK_RF (31.07.1998) and GK_RF_3 (26.11.2001).';
COMMENT ON COLUMN consolidated_codes.original_date IS
  'Date the founding act is cited by: the signing/promulgation date in "от DD.MM.YYYY № N" - NOT the Duma adoption date, NOT the publication date (see founding_act_published_at), NOT the in-force date. For KONST_RF: the 12.12.1993 referendum date.';
COMMENT ON COLUMN consolidated_codes.founding_act_status IS
  'known = adopting act verified against an official source; none = there is no adopting act with a number (KONST_RF: the Constitution was adopted by the all-Russian referendum of 12.12.1993); unknown = not established yet. Says nothing about official_text_eo_number, which describes a different object.';
COMMENT ON COLUMN consolidated_codes.founding_act_published_at IS
  'Earliest official publication date verifiable with an exact day (Российская газета / Парламентская газета / pravo.gov.ru). ИПС dates СЗ РФ only by year+issue, so an СЗ РФ publication may precede this by a few days.';
COMMENT ON COLUMN consolidated_codes.short_name IS
  'DISPLAY LABEL ONLY - NOT A KEY AND NOT UNIQUE. «ВК РФ» is the label of both VZK_RF (Воздушный кодекс) and VDK_RF (Водный кодекс). Look codes up by `code`, never by short_name.';
COMMENT ON COLUMN consolidated_codes.official_url IS
  'Canonical official URL for this row. WHAT IT POINTS AT VARIES BY ROW - read official_url_kind before using it: act_publication = the official publication of the adopting act itself; code_record = the ИПС record of the CODE, which shows the current consolidated text, not the act as enacted. Every URL verified HTTP 200 on 2026-09-14.';
COMMENT ON COLUMN consolidated_codes.official_url_kind IS
  'Which object official_url identifies. act_publication = publication.pravo.gov.ru publication of the adopting act (only KAS_RF: the portal covers 2011+ and no earlier founding act has an eoNumber). code_record = pravo.gov.ru/proxy/ips/ record of the code, i.e. the current consolidated text. Never assume: a row without this value has an unclassified URL.';
COMMENT ON COLUMN consolidated_codes.ips_document_type IS
  'Document-type classification of the object at official_url, as its source states it: Кодекс (ИПС record of a code), Конституция (ИПС record of the Constitution), Федеральный закон (portal publication of an adopting act). This is a CLASSIFICATION, not the type of the adopting act - the act that enacted the Civil Code part one is a федеральный закон even though the ИПС record is typed Кодекс.';
COMMENT ON COLUMN consolidated_codes.founding_act_title IS
  'Official designation of the ADOPTING ACT, one convention for every row: "<act type> от DD.MM.YYYY № <number> «<official name of the code>»", act type = Федеральный закон (Федеральный конституционный закон where applicable), date and number identical to original_date/original_eo_number, name as the act itself designates the code - e.g. «Федеральный закон от 30.11.1994 № 51-ФЗ «Гражданский кодекс Российской Федерации (часть первая)»». NOT the ИПС document type (see ips_document_type). KONST_RF is the sole exception: adopted by referendum, no act type, date or number in the title - «Конституция Российской Федерации».';
COMMENT ON COLUMN consolidated_codes.founding_act_eo_number IS
  'Real publication.pravo.gov.ru eoNumber OF THE FOUNDING ACT (usable with /file/pdf?eoNumber= and /file/sig?eoNumber=). NULL for every pre-2011 act: official publication on the portal is normatively in force from 2011 (per the portal description; the enabling act was not re-verified here) and the earliest records found by search on 2026-09-14 were from 2012 - either way the portal holds no artifact for them. An eoNumber of a consolidated TEXT belongs in official_text_eo_number, not here.';
COMMENT ON COLUMN consolidated_codes.official_text_eo_number IS
  'Portal eoNumber of an officially published CONSOLIDATED TEXT of the code, if any - a DIFFERENT OBJECT from the founding act. Only KONST_RF has one: 0001202007040001, the official text with the amendments approved in the all-Russian vote of 01.07.2020, published 04.07.2020. Never put this value in founding_act_eo_number: the Constitution has no founding act with a number.';
COMMENT ON INDEX uq_consolidated_codes_founding_act IS
  'A founding act is identified by (number, date), never by the number alone: 146-ФЗ is both NK_RF (31.07.1998) and GK_RF_3 (26.11.2001). NO JURISDICTION COLUMN IS INCLUDED because consolidated_codes has none - the table is implicitly Russia-only. Stage 6 debt: a second country adapter MUST add a jurisdiction column and extend this index, otherwise two countries'' acts sharing a number and date will collide.';

-- =============================================================================
-- Initial data
-- =============================================================================

-- Insert Russia as the first country
INSERT INTO countries (code, name, native_name) VALUES
  ('ru', 'Russian Federation', 'Российская Федерация')
ON CONFLICT (code) DO NOTHING;

-- Insert consolidated codes metadata.
--
-- Founding acts verified 2026-09-14 against ИПС «Законодательство России»
-- (pravo.gov.ru/proxy/ips/) and the publication portal; see
-- migrations/003_consolidated_codes_official_acts.sql for the method and for the
-- history of the errors this table used to carry, and
-- migrations/004_consolidated_codes_referents.sql for the referent fixes below.
--
-- THREE DIFFERENT OBJECTS live in these columns - never conflate them:
--   * the ADOPTING ACT: founding_act_title, original_eo_number, original_date,
--     founding_act_eo_number, founding_act_published_at;
--   * what official_url points at, stated by official_url_kind: either that act's
--     official publication ('act_publication' - only KAS_RF) or the ИПС record of
--     the CODE, i.e. its current consolidated text ('code_record' - 22 rows);
--   * an officially published CONSOLIDATED TEXT: official_text_eo_number. Only
--     KONST_RF has one (0001202007040001, the text with the amendments approved
--     on 01.07.2020, published 04.07.2020). It is NOT a founding act - KONST_RF
--     has none, the Constitution was adopted by referendum on 12.12.1993.
--
-- ONE title convention for all 23 rows: "<тип акта> от DD.MM.YYYY № <номер>
-- «<официальное наименование кодекса>»", тип акта = Федеральный закон
-- (Федеральный конституционный закон where applicable). «Кодекс» is the ИПС
-- classification and lives in ips_document_type, not in the title. KONST_RF is
-- the sole exception: «Конституция Российской Федерации», no type/date/number.
--
-- Only KAS_RF has a portal eoNumber for its founding act. Official publication on
-- publication.pravo.gov.ru is normatively in force from 2011 (per the portal's own
-- description; the enabling act was not re-verified here), and the earliest records
-- found by search on 2026-09-14 were from 2012 - either way no pre-2011 act has a
-- portal artifact, so those 22 rows are anchored to their ИПС record instead.
INSERT INTO consolidated_codes (
  code, name, short_name, description, original_eo_number, original_date, official_url, official_url_kind, ips_document_type, founding_act_title, founding_act_eo_number, official_text_eo_number, founding_act_status, founding_act_published_at
) VALUES
  ('KONST_RF', 'Конституция Российской Федерации', 'Конституция', 'Основной закон Российской Федерации', NULL, '1993-12-12', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102027595', 'code_record', 'Конституция', 'Конституция Российской Федерации', NULL, '0001202007040001', 'none', '1993-12-25'),
  ('GK_RF', 'Гражданский кодекс Российской Федерации (часть первая)', 'ГК РФ', 'Основной нормативный акт, регулирующий гражданские правоотношения', '51-ФЗ', '1994-11-30', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102033239', 'code_record', 'Кодекс', 'Федеральный закон от 30.11.1994 № 51-ФЗ «Гражданский кодекс Российской Федерации (часть первая)»', NULL, NULL, 'known', '1994-12-08'),
  ('GK_RF_2', 'Гражданский кодекс Российской Федерации (часть вторая)', 'ГК РФ ч.2', 'Часть 2 Гражданского кодекса', '14-ФЗ', '1996-01-26', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102039276', 'code_record', 'Кодекс', 'Федеральный закон от 26.01.1996 № 14-ФЗ «Гражданский кодекс Российской Федерации (часть вторая)»', NULL, NULL, 'known', '1996-02-10'),
  ('GK_RF_3', 'Гражданский кодекс Российской Федерации (часть третья)', 'ГК РФ ч.3', 'Часть 3 Гражданского кодекса', '146-ФЗ', '2001-11-26', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102073578', 'code_record', 'Кодекс', 'Федеральный закон от 26.11.2001 № 146-ФЗ «Гражданский кодекс Российской Федерации (часть третья)»', NULL, NULL, 'known', '2001-11-28'),
  ('GK_RF_4', 'Гражданский кодекс Российской Федерации (часть четвертая)', 'ГК РФ ч.4', 'Часть 4 Гражданского кодекса', '230-ФЗ', '2006-12-18', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102110716', 'code_record', 'Кодекс', 'Федеральный закон от 18.12.2006 № 230-ФЗ «Гражданский кодекс Российской Федерации (часть четвертая)»', NULL, NULL, 'known', '2006-12-21'),
  ('UK_RF', 'Уголовный кодекс Российской Федерации', 'УК РФ', 'Основной нормативный акт, определяющий преступность и наказуемость деяний', '63-ФЗ', '1996-06-13', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102041891', 'code_record', 'Кодекс', 'Федеральный закон от 13.06.1996 № 63-ФЗ «Уголовный кодекс Российской Федерации»', NULL, NULL, 'known', '1996-06-19'),
  ('TK_RF', 'Трудовой кодекс Российской Федерации', 'ТК РФ', 'Кодекс законов, регулирующих трудовые отношения', '197-ФЗ', '2001-12-30', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102074279', 'code_record', 'Кодекс', 'Федеральный закон от 30.12.2001 № 197-ФЗ «Трудовой кодекс Российской Федерации»', NULL, NULL, 'known', '2001-12-31'),
  ('NK_RF', 'Налоговый кодекс Российской Федерации (часть первая)', 'НК РФ', 'Часть 1 Налогового кодекса', '146-ФЗ', '1998-07-31', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102054722', 'code_record', 'Кодекс', 'Федеральный закон от 31.07.1998 № 146-ФЗ «Налоговый кодекс Российской Федерации (часть первая)»', NULL, NULL, 'known', '1998-08-06'),
  ('NK_RF_2', 'Налоговый кодекс Российской Федерации (часть вторая)', 'НК РФ ч.2', 'Часть 2 Налогового кодекса', '117-ФЗ', '2000-08-05', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102067058', 'code_record', 'Кодекс', 'Федеральный закон от 05.08.2000 № 117-ФЗ «Налоговый кодекс Российской Федерации (часть вторая)»', NULL, NULL, 'known', '2000-08-10'),
  ('KoAP_RF', 'Кодекс Российской Федерации об административных правонарушениях', 'КоАП РФ', 'Основной нормативный акт, регулирующий административную ответственность', '195-ФЗ', '2001-12-30', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102074277', 'code_record', 'Кодекс', 'Федеральный закон от 30.12.2001 № 195-ФЗ «Кодекс Российской Федерации об административных правонарушениях»', NULL, NULL, 'known', '2001-12-31'),
  ('SK_RF', 'Семейный кодекс Российской Федерации', 'СК РФ', 'Кодекс, регулирующий семейные отношения', '223-ФЗ', '1995-12-29', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102038925', 'code_record', 'Кодекс', 'Федеральный закон от 29.12.1995 № 223-ФЗ «Семейный кодекс Российской Федерации»', NULL, NULL, 'known', '1996-01-27'),
  ('ZhK_RF', 'Жилищный кодекс Российской Федерации', 'ЖК РФ', 'Кодекс, регулирующий жилищные отношения', '188-ФЗ', '2004-12-29', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102090645', 'code_record', 'Кодекс', 'Федеральный закон от 29.12.2004 № 188-ФЗ «Жилищный кодекс Российской Федерации»', NULL, NULL, 'known', '2005-01-12'),
  ('ZK_RF', 'Земельный кодекс Российской Федерации', 'ЗК РФ', 'Основной нормативный акт, регулирующий земельные отношения', '136-ФЗ', '2001-10-25', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102073184', 'code_record', 'Кодекс', 'Федеральный закон от 25.10.2001 № 136-ФЗ «Земельный кодекс Российской Федерации»', NULL, NULL, 'known', '2001-10-30'),
  ('APK_RF', 'Арбитражный процессуальный кодекс Российской Федерации', 'АПК РФ', 'Кодекс, регулирующий судопроизводство в арбитражных судах', '95-ФЗ', '2002-07-24', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102079219', 'code_record', 'Кодекс', 'Федеральный закон от 24.07.2002 № 95-ФЗ «Арбитражный процессуальный кодекс Российской Федерации»', NULL, NULL, 'known', '2002-07-27'),
  ('GPK_RF', 'Гражданский процессуальный кодекс Российской Федерации', 'ГПК РФ', 'Кодекс, регулирующий судопроизводство в судах общей юрисдикции', '138-ФЗ', '2002-11-14', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102078828', 'code_record', 'Кодекс', 'Федеральный закон от 14.11.2002 № 138-ФЗ «Гражданский процессуальный кодекс Российской Федерации»', NULL, NULL, 'known', '2002-11-20'),
  ('UPK_RF', 'Уголовно-процессуальный кодекс Российской Федерации', 'УПК РФ', 'Кодекс, регулирующий уголовное судопроизводство', '174-ФЗ', '2001-12-18', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102073942', 'code_record', 'Кодекс', 'Федеральный закон от 18.12.2001 № 174-ФЗ «Уголовно-процессуальный кодекс Российской Федерации»', NULL, NULL, 'known', '2001-12-22'),
  ('BK_RF', 'Бюджетный кодекс Российской Федерации', 'БК РФ', 'Кодекс, регулирующий бюджетные отношения', '145-ФЗ', '1998-07-31', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102054721', 'code_record', 'Кодекс', 'Федеральный закон от 31.07.1998 № 145-ФЗ «Бюджетный кодекс Российской Федерации»', NULL, NULL, 'known', '1998-08-12'),
  ('GRK_RF', 'Градостроительный кодекс Российской Федерации', 'ГрК РФ', 'Кодекс, регулирующий градостроительную деятельность', '190-ФЗ', '2004-12-29', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102090643', 'code_record', 'Кодекс', 'Федеральный закон от 29.12.2004 № 190-ФЗ «Градостроительный кодекс Российской Федерации»', NULL, NULL, 'known', '2004-12-30'),
  ('UIK_RF', 'Уголовно-исполнительный кодекс Российской Федерации', 'УИК РФ', 'Кодекс, регулирующий исполнение уголовных наказаний', '1-ФЗ', '1997-01-08', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102045146', 'code_record', 'Кодекс', 'Федеральный закон от 08.01.1997 № 1-ФЗ «Уголовно-исполнительный кодекс Российской Федерации»', NULL, NULL, 'known', '1997-01-16'),
  ('VZK_RF', 'Воздушный кодекс Российской Федерации', 'ВК РФ', 'Кодекс, регулирующий использование воздушного пространства', '60-ФЗ', '1997-03-19', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102046246', 'code_record', 'Кодекс', 'Федеральный закон от 19.03.1997 № 60-ФЗ «Воздушный кодекс Российской Федерации»', NULL, NULL, 'known', '1997-03-26'),
  ('VDK_RF', 'Водный кодекс Российской Федерации', 'ВК РФ', 'Кодекс, регулирующий водные отношения', '74-ФЗ', '2006-06-03', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102107048', 'code_record', 'Кодекс', 'Федеральный закон от 03.06.2006 № 74-ФЗ «Водный кодекс Российской Федерации»', NULL, NULL, 'known', '2006-06-08'),
  ('LK_RF', 'Лесной кодекс Российской Федерации', 'ЛК РФ', 'Кодекс, регулирующий лесные отношения', '200-ФЗ', '2006-12-04', 'http://pravo.gov.ru/proxy/ips/?docbody=&nd=102110364', 'code_record', 'Кодекс', 'Федеральный закон от 04.12.2006 № 200-ФЗ «Лесной кодекс Российской Федерации»', NULL, NULL, 'known', '2006-12-08'),
  ('KAS_RF', 'Кодекс административного судопроизводства Российской Федерации', 'КАС РФ', 'Кодекс, регулирующий административное судопроизводство', '21-ФЗ', '2015-03-08', 'http://publication.pravo.gov.ru/document/0001201503090041', 'act_publication', 'Федеральный закон', 'Федеральный закон от 08.03.2015 № 21-ФЗ «Кодекс административного судопроизводства Российской Федерации»', '0001201503090041', NULL, 'known', '2015-03-09')
ON CONFLICT (code) DO NOTHING;

-- Insert publication blocks (from API sample data)
INSERT INTO publication_blocks (id, short_name, menu_name, code, description, weight, is_blocked, has_children, is_agencies_of_state_authorities, image_id) VALUES
  ('e94b6872-dcac-414f-b2f1-a538d13a12a0', 'Президент Российской Федерации', 'Президент Российской Федерации', 'president', 'Законы Российской Федерации о поправке к Конституции Российской Федерации, федеральные конституционные законы, федеральные законы, указы Президента Российской Федерации, распоряжения Президента Российской Федерации', 1000, false, false, false, '11f3a3c0-3cbc-4748-85e1-0df692e7138e'),
  ('a30c9c82-4a21-48ab-a41d-d1891a10962c', 'Федеральное Собрание Российской Федерации', 'Федеральное Собрание Российской Федерации', 'assembly', 'Акты палат Федерального Собрания, принятые по вопросам, отнесенным к ведению палат частью 1 статьи 102 и частью 1 статьи 103 Конституции Российской Федерации', 998, false, true, false, NULL),
  ('19bb10cd-32f3-4632-8303-c94dd5f45359', 'Правительство Российской Федерации', 'Правительство Российской Федерации', 'government', 'Правовые акты Правительства Российской Федерации', 997, false, false, false, 'a90a3a19-f8b3-42d1-b9b3-d04a9dced979'),
  ('28bdeebd-e2cf-45ce-8d2a-2bc1aaadd7fc', 'ФОИВ и ФГО РФ', 'ФОИВ и ФГО РФ', 'federal_authorities', 'Правовые акты федеральных органов исполнительной власти и федеральных государственных органов Российской Федерации', 996, false, false, true, 'f19826f2-19e8-4d75-9ae4-476adc52df92'),
  ('b85249b6-f6e6-4562-a783-90ea989af2db', 'Конституционный Суд Российской Федерации', 'Конституционный Суд Российской Федерации', 'court', 'Постановления Конституционного Суда Российской Федерации, определения Конституционного Суда Российской Федерации и иные решения Конституционного Суда Российской Федерации', 995, false, false, false, 'dee8984d-05e3-4903-8bfb-cff7eb27566a'),
  ('022fd55f-9f60-481e-a636-56d74b9ca759', 'ОГВ Субъектов РФ', 'ОГВ Субъектов РФ', 'subjects', 'Законы и иные правовые акты субъектов Российской Федерации', 994, false, false, true, 'e12a919d-54c2-4053-90a3-53fa63ad0de5'),
  ('c79f71a1-c367-4e9d-a8b2-046cc8a1673f', 'Международные Договоры Российской Федерации', 'Международные Договоры Российской Федерации', 'international', 'Международные договоры, вступившие в силу для Российской Федерации, временно применяемые международные договоры Российской Федерации', 993, false, false, false, 'd64b7e9f-8da3-4c97-a74c-69f5fa9e1790'),
  ('f3ddeeb2-0bb5-4f28-989b-e0e8dead6e63', 'Совет Безопасности ООН', 'Совет Безопасности ООН', 'un_securitycouncil', 'Резолюции Совета Безопасности Организации Объединённых Наций', 992, false, false, false, 'fc404e31-1cb1-45cf-8cde-d7efa3faad2e')
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- Functions and triggers
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_countries_updated_at BEFORE UPDATE ON countries
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_publication_blocks_updated_at BEFORE UPDATE ON publication_blocks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_signatory_authorities_updated_at BEFORE UPDATE ON signatory_authorities
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_types_updated_at BEFORE UPDATE ON document_types
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON categories
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_content_updated_at BEFORE UPDATE ON document_content
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Consolidation Engine Tables
-- =============================================================================

-- Consolidated code article versions (snapshots for version history)
CREATE TABLE IF NOT EXISTS code_article_versions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  code_id VARCHAR(50) NOT NULL,  -- 'GK_RF', 'TK_RF', 'UK_RF', etc.
  article_number VARCHAR(50) NOT NULL,  -- '123', '124', etc.
  version_date DATE NOT NULL,  -- Effective date of this version
  article_text TEXT NOT NULL,  -- Full article text
  article_title TEXT,  -- Article title/heading

  -- Amendment that created this version
  amendment_eo_number VARCHAR(100),  -- Source amendment document
  amendment_date DATE,  -- Date of amendment

  -- Status tracking
  is_current BOOLEAN DEFAULT TRUE,  -- Whether this is the current version
  is_repealed BOOLEAN DEFAULT FALSE,  -- Whether article is repealed
  repealed_date DATE,  -- When article was repealed

  -- Change detection
  text_hash VARCHAR(64),  -- Hash of article text for comparison

  created_at TIMESTAMP DEFAULT NOW(),

  -- Unique constraint: one version per article per date
  CONSTRAINT code_article_versions_unique UNIQUE (code_id, article_number, version_date)
);

-- Amendment applications (audit log for consolidation process)
CREATE TABLE IF NOT EXISTS amendment_applications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  amendment_eo_number VARCHAR(100) NOT NULL,  -- The amendment document
  code_id VARCHAR(50) NOT NULL,  -- Code being amended

  -- What was changed
  articles_affected TEXT[],  -- List of article numbers affected ['123', '456']
  articles_added TEXT[],  -- Articles that were added
  articles_modified TEXT[],  -- Articles that were modified
  articles_repealed TEXT[],  -- Articles that were repealed

  -- Change metadata
  amendment_type VARCHAR(50),  -- 'addition', 'modification', 'repeal', 'mixed'
  amendment_date DATE,  -- When amendment takes effect

  -- Processing status
  status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'applied', 'failed', 'conflict'
  error_message TEXT,  -- Error details if failed
  applied_at TIMESTAMP,  -- When application was processed

  created_at TIMESTAMP DEFAULT NOW()
);

-- Note: consolidated_codes is created earlier, above "Initial data",
-- since that section INSERTs into it.

-- Indexes for consolidation tables
CREATE INDEX IF NOT EXISTS idx_code_article_versions_code_article ON code_article_versions(code_id, article_number);
CREATE INDEX IF NOT EXISTS idx_code_article_versions_code_current ON code_article_versions(code_id, is_current);
CREATE INDEX IF NOT EXISTS idx_code_article_versions_version_date ON code_article_versions(version_date);
CREATE INDEX IF NOT EXISTS idx_code_article_versions_code_date ON code_article_versions(code_id, article_number, version_date);

CREATE INDEX IF NOT EXISTS idx_amendment_applications_eo_number ON amendment_applications(amendment_eo_number);
CREATE INDEX IF NOT EXISTS idx_amendment_applications_code_id ON amendment_applications(code_id);
CREATE INDEX IF NOT EXISTS idx_amendment_applications_status ON amendment_applications(status);
CREATE INDEX IF NOT EXISTS idx_amendment_applications_date ON amendment_applications(amendment_date);

-- Trigger for consolidated_codes updated_at
CREATE TRIGGER update_consolidated_codes_updated_at BEFORE UPDATE ON consolidated_codes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Court Decisions System
-- =============================================================================

-- Courts metadata (reference table for court information)
CREATE TABLE IF NOT EXISTS courts (
  id VARCHAR(50) PRIMARY KEY,  -- court code (e.g., 'ASGM' for Arbitration Court of Moscow)
  name TEXT NOT NULL,  -- Full court name
  name_short VARCHAR(200),  -- Short name
  court_type VARCHAR(50) NOT NULL,  -- 'arbitration', 'general', 'supreme', 'constitutional'
  url TEXT,  -- Official court website
  jurisdiction TEXT,  -- Geographic or subject jurisdiction
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Court decisions (main table for storing court decisions)
CREATE TABLE IF NOT EXISTS court_decisions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Foreign keys
  country_id INTEGER REFERENCES countries(id) ON DELETE CASCADE,
  court_id VARCHAR(50) REFERENCES courts(id) ON DELETE SET NULL,

  -- Case identification
  case_number VARCHAR(255) NOT NULL,  -- e.g., 'А40-12345/2023'
  decision_date DATE NOT NULL,  -- Date of decision

  -- Court and case information
  court_name TEXT NOT NULL,  -- Denormalized court name for performance
  case_type VARCHAR(100),  -- Type of case (e.g., 'economic_dispute', 'civil', 'criminal')
  instance VARCHAR(50),  -- Court instance ('first', 'appeal', 'cassation', 'supreme')

  -- Decision content
  decision_text TEXT,  -- Full text of the decision
  summary TEXT,  -- Summary/abstract (for embeddings)

  -- Source information
  source_url TEXT,  -- URL to original decision
  source_type VARCHAR(50),  -- 'pravo_api', 'kad_scraper', 'sudrf_scraper', 'vsrf_scraper'

  -- Text hash for change detection
  text_hash VARCHAR(64),

  -- Timestamps
  publish_date DATE,  -- Date decision was published
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),

  -- Unique constraint on case number (may need adjustment for different court systems)
  CONSTRAINT court_decisions_case_unique UNIQUE (case_number, court_id)
);

-- Article references from court decisions (links decisions to legal articles)
CREATE TABLE IF NOT EXISTS court_decision_article_references (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Foreign key to court decision
  court_decision_id UUID NOT NULL REFERENCES court_decisions(id) ON DELETE CASCADE,

  -- Article being referenced
  code_id VARCHAR(50) NOT NULL,  -- e.g., 'GK_RF', 'UK_RF', 'TK_RF'
  article_number VARCHAR(50) NOT NULL,  -- e.g., '123', '124.1', '15-3'

  -- Reference context
  reference_context TEXT,  -- Excerpt showing how article was interpreted
  reference_type VARCHAR(50),  -- 'cited', 'interpreted', 'applied', 'distinguished'

  -- Position in decision (for locating the reference)
  position_in_text INTEGER,  -- Character position where reference appears

  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for court decision tables
CREATE INDEX IF NOT EXISTS idx_court_decisions_country_id ON court_decisions(country_id);
CREATE INDEX IF NOT EXISTS idx_court_decisions_court_id ON court_decisions(court_id);
CREATE INDEX IF NOT EXISTS idx_court_decisions_decision_date ON court_decisions(decision_date DESC);
CREATE INDEX IF NOT EXISTS idx_court_decisions_case_number ON court_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_court_decisions_case_type ON court_decisions(case_type);
CREATE INDEX IF NOT EXISTS idx_court_decisions_instance ON court_decisions(instance);
CREATE INDEX IF NOT EXISTS idx_court_decisions_source_type ON court_decisions(source_type);

-- Full-text search indexes for court decisions (Russian and English)
CREATE INDEX IF NOT EXISTS idx_court_decisions_text_trgm ON court_decisions USING gin(decision_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_court_decisions_summary_trgm ON court_decisions USING gin(summary gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_court_decisions_full_text_russian ON court_decisions
  USING gin(to_tsvector('russian', decision_text));
CREATE INDEX IF NOT EXISTS idx_court_decisions_full_text_english ON court_decisions
  USING gin(to_tsvector('english', decision_text));

-- Indexes for article references
CREATE INDEX IF NOT EXISTS idx_court_decision_article_refs_decision_id ON court_decision_article_references(court_decision_id);
CREATE INDEX IF NOT EXISTS idx_court_decision_article_refs_code_article ON court_decision_article_references(code_id, article_number);
CREATE INDEX IF NOT EXISTS idx_court_decision_article_refs_code_id ON court_decision_article_references(code_id);
CREATE INDEX IF NOT EXISTS idx_court_decision_article_refs_reference_type ON court_decision_article_references(reference_type);

-- Indexes for courts
CREATE INDEX IF NOT EXISTS idx_courts_court_type ON courts(court_type);
CREATE INDEX IF NOT EXISTS idx_courts_name_trgm ON courts USING gin(name gin_trgm_ops);

-- Triggers for updated_at
CREATE TRIGGER update_courts_updated_at BEFORE UPDATE ON courts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_court_decisions_updated_at BEFORE UPDATE ON court_decisions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- View: Court decisions with article references
-- =============================================================================
CREATE OR REPLACE VIEW court_decisions_with_articles AS
SELECT
  cd.id,
  cd.case_number,
  cd.decision_date,
  cd.court_name,
  cd.case_type,
  cd.instance,
  cd.summary,
  cd.source_url,
  c.code AS country_code,
  ct.court_type,
  COALESCE(
    json_agg(
      json_build_object(
        'code_id', ref.code_id,
        'article_number', ref.article_number,
        'reference_type', ref.reference_type,
        'reference_context', ref.reference_context
      ) ORDER BY ref.code_id, ref.article_number
    ) FILTER (WHERE ref.id IS NOT NULL),
    '[]'::json
  ) AS article_references
FROM court_decisions cd
JOIN countries c ON cd.country_id = c.id
LEFT JOIN courts ct ON cd.court_id = ct.id
LEFT JOIN court_decision_article_references ref ON cd.id = ref.court_decision_id
GROUP BY
  cd.id, cd.case_number, cd.decision_date, cd.court_name, cd.case_type,
  cd.instance, cd.summary, cd.source_url, c.code, ct.court_type;

-- =============================================================================
-- Helper functions
-- =============================================================================

-- Function to normalize document text (remove extra whitespace, etc.)
CREATE OR REPLACE FUNCTION normalize_text(text TEXT)
RETURNS TEXT AS $$
BEGIN
  IF text IS NULL THEN
    RETURN NULL;
  END IF;

  -- Replace multiple whitespace with single space
  RETURN regexp_replace(
    regexp_replace(text, E'[\\n\\r\\t]+', ' ', 'g'),
    E'\\s+', ' ', 'g'
  );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- Grant permissions (uncomment and adjust username as needed)
-- =============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO law7;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO law7;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO law7;
