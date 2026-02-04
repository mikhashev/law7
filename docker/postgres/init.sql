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
-- Initial data
-- =============================================================================

-- Insert Russia as the first country
INSERT INTO countries (code, name, native_name) VALUES
  ('ru', 'Russian Federation', 'Российская Федерация')
ON CONFLICT (code) DO NOTHING;

-- Insert consolidated codes metadata
INSERT INTO consolidated_codes (code, name, short_name, description, original_eo_number, original_date) VALUES
  ('KONST_RF', 'Конституция Российской Федерации', 'К РФ', 'Основной закон Российской Федерации', NULL, '1993-12-12'),
  ('GK_RF', 'Гражданский кодекс Российской Федерации', 'ГК РФ', 'Основной нормативный акт, регулирующий гражданские правоотношения', '51-ФЗ', '1994-11-30'),
  ('GK_RF_2', 'Гражданский кодекс Российской Федерации часть 2', 'ГК РФ ч.2', 'Часть 2 Гражданского кодекса', '51-ФЗ', '1994-11-30'),
  ('GK_RF_3', 'Гражданский кодекс Российской Федерации часть 3', 'ГК РФ ч.3', 'Часть 3 Гражданского кодекса', '51-ФЗ', '1994-11-30'),
  ('GK_RF_4', 'Гражданский кодекс Российской Федерации часть 4', 'ГК РФ ч.4', 'Часть 4 Гражданского кодекса', '51-ФЗ', '1994-11-30'),
  ('UK_RF', 'Уголовный кодекс Российской Федерации', 'УК РФ', 'Основной нормативный акт, определяющий преступность и наказуемость деяний', '63-ФЗ', '1996-05-24'),
  ('TK_RF', 'Трудовой кодекс Российской Федерации', 'ТК РФ', 'Кодекс законов, регулирующих трудовые отношения', '197-ФЗ', '2001-12-30'),
  ('NK_RF', 'Налоговый кодекс Российской Федерации часть 1', 'НК РФ', 'Часть 1 Налогового кодекса', '146-ФЗ', '2000-07-31'),
  ('NK_RF_2', 'Налоговый кодекс Российской Федерации часть 2', 'НК РФ ч.2', 'Часть 2 Налогового кодекса', '146-ФЗ', '2000-07-31'),
  ('KoAP_RF', 'Кодекс Российской Федерации об административных правонарушениях', 'КоАП РФ', 'Основной нормативный акт, регулирующий административную ответственность', '195-ФЗ', '2001-12-30'),
  ('SK_RF', 'Семейный кодекс Российской Федерации', 'СК РФ', 'Кодекс, регулирующий семейные отношения', '223-ФЗ', '1995-12-29'),
  ('ZhK_RF', 'Жилищный кодекс Российской Федерации', 'ЖК РФ', 'Кодекс, регулирующий жилищные отношения', '188-ФЗ', '2004-12-29'),
  ('ZK_RF', 'Земельный кодекс Российской Федерации', 'ЗК РФ', 'Основной нормативный акт, регулирующий земельные отношения', '136-ФЗ', '2001-10-25'),
  ('APK_RF', 'Арбитражный процессуальный кодекс Российской Федерации', 'АПК РФ', 'Кодекс, регулирующий судопроизводство в арбитражных судах', '95-ФЗ', '2002-07-24'),
  ('GPK_RF', 'Гражданский процессуальный кодекс Российской Федерации', 'ГПК РФ', 'Кодекс, регулирующий судопроизводство в судах общей юрисдикции', '138-ФЗ', '2002-11-14'),
  ('UPK_RF', 'Уголовно-процессуальный кодекс Российской Федерации', 'УПК РФ', 'Кодекс, регулирующий уголовное судопроизводство', '174-ФЗ', '2001-12-18'),
  ('BK_RF', 'Бюджетный кодекс Российской Федерации', 'БК РФ', 'Кодекс, регулирующий бюджетные отношения', '145-ФЗ', '1998-07-31'),
  ('GRK_RF', 'Градостроительный кодекс Российской Федерации', 'ГрК РФ', 'Кодекс, регулирующий градостроительную деятельность', '190-ФЗ', '2004-12-29'),
  ('UIK_RF', 'Уголовно-исполнительный кодекс Российской Федерации', 'УИК РФ', 'Кодекс, регулирующий исполнение уголовных наказаний', '1-ФЗ', '1997-01-08'),
  ('VZK_RF', 'Воздушный кодекс Российской Федерации', 'ВК РФ', 'Кодекс, регулирующий использование воздушного пространства', '60-ФЗ', '1997-03-19'),
  ('VDK_RF', 'Водный кодекс Российской Федерации', 'ВК РФ', 'Кодекс, регулирующий водные отношения', '74-ФЗ', '2006-06-03'),
  ('LK_RF', 'Лесной кодекс Российской Федерации', 'ЛК РФ', 'Кодекс, регулирующий лесные отношения', '200-ФЗ', '2006-12-04'),
  ('KAS_RF', 'Кодекс административного судопроизводства Российской Федерации', 'КАС РФ', 'Кодекс, регулирующий административное судопроизводство', '21-ФЗ', '2015-03-08')
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

-- Consolidated codes metadata (tracks base codes)
CREATE TABLE IF NOT EXISTS consolidated_codes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  code VARCHAR(50) UNIQUE NOT NULL,  -- 'GK_RF', 'TK_RF', etc.
  name VARCHAR(500) NOT NULL,  -- Full name
  short_name VARCHAR(100),  -- Short name (ГК РФ, ТК РФ)
  description TEXT,

  -- Original publication info
  original_eo_number VARCHAR(100),  -- Original law number
  original_date DATE,  -- Original publication date
  official_url TEXT,  -- Link to official publication

  -- Consolidation status
  last_amended_date DATE,  -- Date of most recent amendment
  total_amendments INTEGER DEFAULT 0,  -- Total amendments applied
  is_consolidated BOOLEAN DEFAULT FALSE,  -- Whether consolidation is complete
  last_consolidated_at TIMESTAMP,  -- When last consolidation ran

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for consolidation tables
CREATE INDEX IF NOT EXISTS idx_code_article_versions_code_article ON code_article_versions(code_id, article_number);
CREATE INDEX IF NOT EXISTS idx_code_article_versions_code_current ON code_article_versions(code_id, is_current);
CREATE INDEX IF NOT EXISTS idx_code_article_versions_version_date ON code_article_versions(version_date);
CREATE INDEX IF NOT EXISTS idx_code_article_versions_code_date ON code_article_versions(code_id, article_number, version_date);

CREATE INDEX IF NOT EXISTS idx_amendment_applications_eo_number ON amendment_applications(amendment_eo_number);
CREATE INDEX IF NOT EXISTS idx_amendment_applications_code_id ON amendment_applications(code_id);
CREATE INDEX IF NOT EXISTS idx_amendment_applications_status ON amendment_applications(status);
CREATE INDEX IF NOT EXISTS idx_amendment_applications_date ON amendment_applications(amendment_date);

CREATE INDEX IF NOT EXISTS idx_consolidated_codes_code ON consolidated_codes(code);
CREATE INDEX IF NOT EXISTS idx_consolidated_codes_consolidated ON consolidated_codes(is_consolidated);

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
