-- ============================================================================
-- Phase 7C: Database Schema for Regional, Courts, and Ministry Data
--
-- This migration adds tables to support:
-- 1. Regional legislation (top 10 regions)
-- 2. Court decisions (Supreme + Constitutional)
-- 3. Ministry interpretations (Minfin + Rostrud)
--
-- Related: Phase 4 (Regional), Phase 5 (Courts), Phase 6 (Interpretations)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Regional Legislation Tables
-- ----------------------------------------------------------------------------

-- Regional documents (laws, decrees, etc.)
CREATE TABLE IF NOT EXISTS regional_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries
    region_id VARCHAR(10) NOT NULL,          -- OKATO code or FIAS region code
    region_name VARCHAR(200) NOT NULL,
    jurisdiction_level VARCHAR(20) NOT NULL, -- 'regional', 'municipal'
    document_type VARCHAR(50),               -- 'law', 'decree', 'resolution', etc.

    -- Document identification
    document_number VARCHAR(100),
    document_date DATE,
    title TEXT,
    name TEXT,
    complex_name TEXT,

    -- Document metadata
    pages_count INTEGER,
    pdf_file_size BIGINT,
    source_url TEXT,

    -- Status and tracking
    status VARCHAR(50) DEFAULT 'active',     -- 'active', 'repealed', 'superseded'
    effective_from DATE,
    effective_until DATE,

    -- Relationships
    signatory_authority_id UUID,
    publication_block_id UUID,

    -- Full text search
    content TEXT,

    -- Note: Vector embeddings stored in Qdrant, not PostgreSQL

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT regional_documents_country_fkey
        FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

-- Regional codes (e.g., KoAP - Administrative Codes)
CREATE TABLE IF NOT EXISTS regional_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries
    region_id VARCHAR(10) NOT NULL,
    region_name VARCHAR(200) NOT NULL,

    -- Code identification
    code_id VARCHAR(50) NOT NULL,            -- e.g., "KOAP_MOSCOW", "KOAP_SPB"
    code_name VARCHAR(200) NOT NULL,         -- e.g., "Кодекс об административных правонарушениях города Москвы"
    code_type VARCHAR(50) NOT NULL,          -- 'administrative', 'civil', 'labor', etc.

    -- Dates
    adoption_date DATE,
    last_amendment_date DATE,

    -- Status
    consolidation_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'partial', 'complete'
    is_active BOOLEAN DEFAULT TRUE,

    -- Source
    source_url TEXT,

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    UNIQUE(country_id, region_id, code_id)
);

-- Regional code articles (individual articles from regional codes)
CREATE TABLE IF NOT EXISTS regional_code_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries
    region_id VARCHAR(10) NOT NULL,
    code_id VARCHAR(50) NOT NULL,

    -- Article identification
    article_number VARCHAR(20) NOT NULL,
    chapter_number VARCHAR(20),
    part_number VARCHAR(20),

    -- Article content
    article_title TEXT,
    article_content TEXT NOT NULL,

    -- Status and dates
    status VARCHAR(50) DEFAULT 'active',     -- 'active', 'repealed', 'modified'
    effective_from DATE,
    effective_until DATE,

    -- Version tracking
    version_date DATE NOT NULL DEFAULT CURRENT_DATE,
    is_current BOOLEAN DEFAULT TRUE,

    -- Source
    source_url TEXT,

    -- Note: Vector embeddings stored in Qdrant, not PostgreSQL

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 2. Court Decision Tables
-- ----------------------------------------------------------------------------

-- Court decisions (Supreme Court, Constitutional Court)
CREATE TABLE IF NOT EXISTS court_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries

    -- Court identification
    court_type VARCHAR(50) NOT NULL,         -- 'supreme', 'constitutional'
    court_level VARCHAR(50),                 -- 'federal', 'regional', 'district'
    decision_type VARCHAR(50) NOT NULL,      -- 'plenary_resolution', 'ruling', 'determination', 'review'

    -- Case identification
    case_number VARCHAR(100),
    decision_date DATE NOT NULL,
    publication_date DATE,

    -- Decision content
    title TEXT,
    summary TEXT,
    full_text TEXT,

    -- Legal analysis
    legal_issues TEXT[],                     -- Array of legal issues addressed
    articles_interpreted JSONB,              -- {code_id: [article_numbers]}
    binding_nature VARCHAR(50) DEFAULT 'mandatory', -- 'mandatory', 'persuasive', 'informational'

    -- Supersession tracking
    supersedes UUID[],                       -- Array of decision IDs this supersedes
    superseded_by UUID,

    -- Status and source
    status VARCHAR(50) DEFAULT 'active',
    source_url TEXT,

    -- Note: Vector embeddings stored in Qdrant, not PostgreSQL

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

-- Practice reviews (Обзоры судебной практики)
CREATE TABLE IF NOT EXISTS practice_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries

    -- Court identification
    court_type VARCHAR(50) NOT NULL,         -- 'supreme', 'constitutional'

    -- Review identification
    review_title TEXT NOT NULL,
    publication_date DATE NOT NULL,
    period_covered VARCHAR(100),             -- e.g., "Q1 2024", "2023"

    -- Review content
    content TEXT NOT NULL,
    key_conclusions TEXT[],                  -- Array of key legal conclusions
    common_errors TEXT[],                    -- Array of common judicial errors
    correct_approach TEXT[],                 -- Array of correct approaches

    -- Metadata
    cases_analyzed INTEGER,
    source_url TEXT,

    -- Note: Vector embeddings stored in Qdrant, not PostgreSQL

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE
);

-- Legal positions (for Constitutional Court)
CREATE TABLE IF NOT EXISTS legal_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries

    -- Decision reference
    decision_id UUID NOT NULL,               -- References court_decisions

    -- Position content
    position_text TEXT NOT NULL,

    -- Legal basis
    constitutional_basis TEXT[],             -- Articles of Constitution referenced
    laws_affected TEXT[],                    -- Laws affected by this position

    -- Status
    position_date DATE NOT NULL,
    still_valid BOOLEAN DEFAULT TRUE,

    -- Note: Vector embeddings stored in Qdrant, not PostgreSQL

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE,
    FOREIGN KEY (decision_id) REFERENCES court_decisions(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 3. Ministry Interpretation Tables
-- ----------------------------------------------------------------------------

-- Government agencies registry
CREATE TABLE IF NOT EXISTS government_agencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries

    -- Agency identification
    agency_name VARCHAR(200) NOT NULL,
    agency_name_short VARCHAR(100),          -- e.g., "Минфин", "ФНС", "Роструд"
    agency_type VARCHAR(50) NOT NULL,        -- 'ministry', 'service', 'agency', 'inspection'

    -- Hierarchy
    parent_agency_id UUID,

    -- Jurisdiction
    jurisdiction VARCHAR(100) NOT NULL,      -- 'federal', 'regional'

    -- Contact
    website VARCHAR(200),
    email VARCHAR(200),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_agency_id) REFERENCES government_agencies(id)
);

-- Official interpretations (ministry letters, guidance, instructions)
CREATE TABLE IF NOT EXISTS official_interpretations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_id INTEGER NOT NULL,            -- References countries.id
    country_code VARCHAR(2) NOT NULL DEFAULT 'RU', -- For easier queries

    -- Agency reference
    agency_id UUID NOT NULL,

    -- Document identification
    document_type VARCHAR(50) NOT NULL,      -- 'letter', 'guidance', 'instruction', 'explanation'
    document_number VARCHAR(100),
    document_date DATE NOT NULL,

    -- Content
    title TEXT,
    question TEXT,                           -- The question being answered
    answer TEXT,                             -- The official answer
    full_content TEXT,

    -- Classification
    legal_topic VARCHAR(100),
    related_laws JSONB,                      -- Related law references

    -- Status and validity
    binding_nature VARCHAR(50),              -- 'official', 'informational', 'recommendation'
    validity_status VARCHAR(50) DEFAULT 'valid', -- 'valid', 'superseded', 'withdrawn'

    -- Supersession tracking
    supersedes UUID[],                       -- Interpretations this supersedes
    superseded_by UUID,

    -- Source
    source_url TEXT,

    -- Note: Vector embeddings stored in Qdrant, not PostgreSQL

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE,
    FOREIGN KEY (agency_id) REFERENCES government_agencies(id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Regional documents indexes
CREATE INDEX IF NOT EXISTS idx_regional_documents_country_region
    ON regional_documents(country_id, region_id);
CREATE INDEX IF NOT EXISTS idx_regional_documents_jurisdiction
    ON regional_documents(jurisdiction_level, jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_regional_documents_type
    ON regional_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_regional_documents_date
    ON regional_documents(document_date DESC);
CREATE INDEX IF NOT EXISTS idx_regional_documents_region_id
    ON regional_documents(region_id);

-- Regional codes indexes
CREATE INDEX IF NOT EXISTS idx_regional_codes_region
    ON regional_codes(country_id, region_id);
CREATE INDEX IF NOT EXISTS idx_regional_codes_code_id
    ON regional_codes(code_id);
CREATE INDEX IF NOT EXISTS idx_regional_codes_active
    ON regional_codes(is_active) WHERE is_active = TRUE;

-- Regional code articles indexes
CREATE INDEX IF NOT EXISTS idx_regional_articles_code
    ON regional_code_articles(code_id, article_number);
CREATE INDEX IF NOT EXISTS idx_regional_articles_region
    ON regional_code_articles(country_id, region_id);
CREATE INDEX IF NOT EXISTS idx_regional_articles_current
    ON regional_code_articles(code_id, article_number, is_current)
    WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_regional_articles_date
    ON regional_code_articles(version_date DESC);

-- Court decisions indexes
CREATE INDEX IF NOT EXISTS idx_court_decisions_court_type
    ON court_decisions(court_type, decision_type);
CREATE INDEX IF NOT EXISTS idx_court_decisions_date
    ON court_decisions(decision_date DESC);
CREATE INDEX IF NOT EXISTS idx_court_decisions_case_number
    ON court_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_court_decisions_binding
    ON court_decisions(binding_nature);

-- Practice reviews indexes
CREATE INDEX IF NOT EXISTS idx_practice_reviews_court
    ON practice_reviews(court_type);
CREATE INDEX IF NOT EXISTS idx_practice_reviews_date
    ON practice_reviews(publication_date DESC);

-- Legal positions indexes
CREATE INDEX IF NOT EXISTS idx_legal_positions_decision
    ON legal_positions(decision_id);
CREATE INDEX IF NOT EXISTS idx_legal_positions_valid
    ON legal_positions(still_valid) WHERE still_valid = TRUE;

-- Government agencies indexes
CREATE INDEX IF NOT EXISTS idx_gov_agencies_country
    ON government_agencies(country_id);
CREATE INDEX IF NOT EXISTS idx_gov_agencies_type
    ON government_agencies(agency_type);
CREATE INDEX IF NOT EXISTS idx_gov_agencies_active
    ON government_agencies(is_active) WHERE is_active = TRUE;

-- Official interpretations indexes
CREATE INDEX IF NOT EXISTS idx_official_interpretations_agency
    ON official_interpretations(agency_id);
CREATE INDEX IF NOT EXISTS idx_official_interpretations_type
    ON official_interpretations(document_type);
CREATE INDEX IF NOT EXISTS idx_official_interpretations_date
    ON official_interpretations(document_date DESC);
CREATE INDEX IF NOT EXISTS idx_official_interpretations_topic
    ON official_interpretations(legal_topic);
CREATE INDEX IF NOT EXISTS idx_official_interpretations_valid
    ON official_interpretations(validity_status);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_regional_documents_updated_at
    BEFORE UPDATE ON regional_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_regional_codes_updated_at
    BEFORE UPDATE ON regional_codes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_regional_code_articles_updated_at
    BEFORE UPDATE ON regional_code_articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_court_decisions_updated_at
    BEFORE UPDATE ON court_decisions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_practice_reviews_updated_at
    BEFORE UPDATE ON practice_reviews
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_government_agencies_updated_at
    BEFORE UPDATE ON government_agencies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_official_interpretations_updated_at
    BEFORE UPDATE ON official_interpretations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA - Government Agencies (for Phase 7C)
-- ============================================================================

-- Insert target agencies for Phase 7C
-- Note: Using country_id = 1 (Russian Federation) from countries table
INSERT INTO government_agencies (country_id, country_code, agency_name, agency_name_short, agency_type, jurisdiction, website)
VALUES
    (1, 'ru', 'Министерство финансов Российской Федерации', 'Минфин', 'ministry', 'federal', 'https://minfin.gov.ru'),
    (1, 'ru', 'Федеральная налоговая служба', 'ФНС', 'service', 'federal', 'https://www.nalog.gov.ru'),
    (1, 'ru', 'Федеральная служба по труду и занятости', 'Роструд', 'service', 'federal', 'https://rostrud.gov.ru')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE regional_documents IS 'Regional legal documents (laws, decrees, resolutions)';
COMMENT ON TABLE regional_codes IS 'Regional codes (e.g., KoAP - Administrative Codes)';
COMMENT ON TABLE regional_code_articles IS 'Individual articles from regional codes';

COMMENT ON TABLE court_decisions IS 'Supreme and Constitutional Court decisions';
COMMENT ON TABLE practice_reviews IS 'Court practice reviews (Обзоры судебной практики)';
COMMENT ON TABLE legal_positions IS 'Constitutional Court legal positions';

COMMENT ON TABLE government_agencies IS 'Government agencies registry (ministries, services)';
COMMENT ON TABLE official_interpretations IS 'Official ministry letters and interpretations';
