-- Laws-Context7 Database Schema
-- PostgreSQL 15+

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Countries table
CREATE TABLE IF NOT EXISTS countries (
  id SERIAL PRIMARY KEY,
  code VARCHAR(2) UNIQUE NOT NULL,
  name VARCHAR(100) NOT NULL,
  native_name VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Categories table (legal categories: constitution, codes, federal-laws, etc.)
CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  country_id INTEGER REFERENCES countries(id) ON DELETE CASCADE,
  code VARCHAR(50) NOT NULL,
  name VARCHAR(200) NOT NULL,
  native_name VARCHAR(200),
  document_type VARCHAR(50),
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(country_id, code)
);

-- Documents table (with upsert support via eo_number)
CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  country_id INTEGER REFERENCES countries(id) ON DELETE CASCADE,
  category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  eo_number VARCHAR(50) UNIQUE NOT NULL,
  document_type VARCHAR(50),
  title VARCHAR(500),
  title_native VARCHAR(500),
  document_number VARCHAR(100),
  adoption_date DATE,
  publication_date DATE,
  effective_date DATE,
  signatory_authority VARCHAR(200),
  source_url TEXT,
  pdf_url TEXT,
  pages_count INTEGER,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Document Content table
CREATE TABLE IF NOT EXISTS document_content (
  document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  full_text TEXT,
  raw_text TEXT,
  text_hash VARCHAR(64),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Document Versions table (for amendment tracking)
CREATE TABLE IF NOT EXISTS document_versions (
  id SERIAL PRIMARY KEY,
  document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  version_number VARCHAR(50),
  effective_date DATE,
  is_current BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Amendments table
CREATE TABLE IF NOT EXISTS amendments (
  id SERIAL PRIMARY KEY,
  document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  amending_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
  amendment_type VARCHAR(50),
  description TEXT,
  amendment_date DATE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Document Relationships table (cross-references between laws)
CREATE TABLE IF NOT EXISTS document_relationships (
  id SERIAL PRIMARY KEY,
  source_document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  target_document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  relationship_type VARCHAR(50),
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(source_document_id, target_document_id, relationship_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_eo_number ON documents(eo_number);
CREATE INDEX IF NOT EXISTS idx_documents_country_category ON documents(country_id, category_id);
CREATE INDEX IF NOT EXISTS idx_documents_adoption_date ON documents(adoption_date);
CREATE INDEX IF NOT EXISTS idx_documents_publication_date ON documents(publication_date);
CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_signatory_authority ON documents(signatory_authority);
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_documents_title_native ON documents USING gin(to_tsvector('russian', title_native));

CREATE INDEX IF NOT EXISTS idx_categories_country_code ON categories(country_id, code);
CREATE INDEX IF NOT EXISTS idx_categories_document_type ON categories(document_type);

-- Full-text search index for document content
CREATE INDEX IF NOT EXISTS idx_document_content_full_text ON document_content USING gin(to_tsvector('russian', full_text));
CREATE INDEX IF NOT EXISTS idx_document_content_full_text_en ON document_content USING gin(to_tsvector('english', full_text));

-- Insert initial data
INSERT INTO countries (code, name, native_name) VALUES
  ('ru', 'Russian Federation', 'Российская Федерация')
ON CONFLICT (code) DO NOTHING;

-- Insert Russian legal categories
INSERT INTO categories (country_id, code, name, native_name, document_type, description) VALUES
  (1, 'constitution', 'Constitution', 'Конституция', 'constitution', 'Constitution of the Russian Federation'),
  (1, 'civil-code', 'Civil Code', 'Гражданский кодекс', 'code', 'Civil Code of the Russian Federation'),
  (1, 'criminal-code', 'Criminal Code', 'Уголовный кодекс', 'code', 'Criminal Code of the Russian Federation'),
  (1, 'labor-code', 'Labor Code', 'Трудовой кодекс', 'code', 'Labor Code of the Russian Federation'),
  (1, 'tax-code', 'Tax Code', 'Налоговый кодекс', 'code', 'Tax Code of the Russian Federation'),
  (1, 'federal-laws', 'Federal Laws', 'Федеральные законы', 'federal-law', 'Federal Laws'),
  (1, 'presidential-decrees', 'Presidential Decrees', 'Указы Президента', 'presidential-decree', 'Presidential Decrees'),
  (1, 'government-resolutions', 'Government Resolutions', 'Постановления Правительства', 'government-resolution', 'Government Resolutions'),
  (1, 'court-decisions', 'Court Decisions', 'Судебные решения', 'court-decision', 'Court Decisions')
ON CONFLICT (country_id, code) DO NOTHING;

-- Create a view for recent documents
CREATE OR REPLACE VIEW recent_documents AS
SELECT
  d.id,
  d.eo_number,
  d.title,
  d.title_native,
  d.document_type,
  d.adoption_date,
  d.publication_date,
  c.code AS country_code,
  cat.code AS category_code,
  d.signatory_authority
FROM documents d
JOIN countries c ON d.country_id = c.id
LEFT JOIN categories cat ON d.category_id = cat.id
WHERE d.publication_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY d.publication_date DESC;

-- Grant permissions (adjust username as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO laws_context7;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO laws_context7;

-- Create function to update updated_at timestamp
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

CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_content_updated_at BEFORE UPDATE ON document_content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
