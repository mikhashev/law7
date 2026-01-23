#!/bin/bash
# docker/backup.sh - Backup PostgreSQL and Qdrant for law7 project
#
# Usage:
#   cd docker
#   ./backup.sh
#
# Creates a timestamped backup in backups/ directory containing:
#   - PostgreSQL dump (custom compressed format)
#   - Qdrant collection snapshot
#   - README with restore instructions
#   - Environment template (.env.example)

set -e

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="law7_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Database settings (from docker-compose.yml)
POSTGRES_CONTAINER="law7-postgres"
POSTGRES_USER="law7"
POSTGRES_DB="law7"
QDRANT_CONTAINER="law7-qdrant"
QDRANT_URL="http://localhost:6333"
QDRANT_COLLECTION="law_chunks"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."

    local missing=()

    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v curl >/dev/null 2>&1 || missing+=("curl")
    command -v tar >/dev/null 2>&1 || missing+=("tar")
    command -v sha256sum >/dev/null 2>&1 || missing+=("sha256sum")

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Please install missing tools and try again."
        exit 1
    fi

    log_success "All dependencies found."
}

check_containers_running() {
    log_info "Checking if required containers are running..."

    local postgres_running=$(docker ps --filter "name=${POSTGRES_CONTAINER}" --format "{{.Names}}")
    local qdrant_running=$(docker ps --filter "name=${QDRANT_CONTAINER}" --format "{{.Names}}")

    if [ -z "$postgres_running" ]; then
        log_error "PostgreSQL container '${POSTGRES_CONTAINER}' is not running."
        log_info "Start containers with: docker-compose up -d"
        exit 1
    fi

    if [ -z "$qdrant_running" ]; then
        log_error "Qdrant container '${QDRANT_CONTAINER}' is not running."
        log_info "Start containers with: docker-compose up -d"
        exit 1
    fi

    log_success "All required containers are running."
}

backup_postgresql() {
    log_info "Backing up PostgreSQL database..."

    mkdir -p "${BACKUP_PATH}/postgresql"

    log_info "Running pg_dump (custom compressed format)..."
    docker exec ${POSTGRES_CONTAINER} pg_dump -Fc -Z9 -U ${POSTGRES_USER} -d ${POSTGRES_DB} > "${BACKUP_PATH}/postgresql/${POSTGRES_DB}.dump"

    local size=$(du -h "${BACKUP_PATH}/postgresql/${POSTGRES_DB}.dump" | cut -f1)
    log_success "PostgreSQL backup complete: ${size}"
}

backup_qdrant() {
    log_info "Backing up Qdrant collection..."

    mkdir -p "${BACKUP_PATH}/qdrant"

    # Create snapshot
    log_info "Creating Qdrant snapshot..."
    local response=$(curl -s -X POST "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots")

    # Wait a moment for snapshot to be created
    sleep 2

    # List snapshots to get the filename
    log_info "Retrieving snapshot name..."
    local snapshots=$(curl -s "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots")
    local snapshot_name=$(echo "$snapshots" | grep -oP '"name":"\K[^"]+' | head -1)

    if [ -z "$snapshot_name" ]; then
        log_error "Failed to get snapshot name."
        log_error "Response: $snapshots"
        exit 1
    fi

    log_info "Downloading snapshot: ${snapshot_name}"

    # Download the snapshot
    curl -s "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/${snapshot_name}" \
         --output "${BACKUP_PATH}/qdrant/${QDRANT_COLLECTION}.snapshot"

    # Verify file was created and has content
    if [ ! -s "${BACKUP_PATH}/qdrant/${QDRANT_COLLECTION}.snapshot" ]; then
        log_error "Snapshot file is empty or was not created."
        exit 1
    fi

    local size=$(du -h "${BACKUP_PATH}/qdrant/${QDRANT_COLLECTION}.snapshot" | cut -f1)
    log_success "Qdrant snapshot complete: ${size}"

    # Clean up snapshot from Qdrant storage (optional, saves space)
    log_info "Cleaning up snapshot from Qdrant..."
    curl -s -X DELETE "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/${snapshot_name}" > /dev/null
}

get_db_stats() {
    log_info "Gathering database statistics..."

    # Get document count
    local doc_count=$(docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM documents;")
    doc_count=$(echo "$doc_count" | tr -d ' ')

    # Get article count
    local article_count=$(docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM code_article_versions;")
    article_count=$(echo "$article_count" | tr -d ' ')

    # Get Qdrant point count
    local qdrant_info=$(curl -s "${QDRANT_URL}/collections/${QDRANT_COLLECTION}")
    local point_count=$(echo "$qdrant_info" | grep -oP '"points":[0-9]+' | grep -oP '[0-9]+' || echo "N/A")

    echo "${doc_count}|${article_count}|${point_count}"
}

create_readme() {
    log_info "Creating README..."

    # Get statistics
    local stats=$(get_db_stats)
    local doc_count=$(echo "$stats" | cut -d'|' -f1)
    local article_count=$(echo "$stats" | cut -d'|' -f2)
    local point_count=$(echo "$stats" | cut -d'|' -f3)

    cat > "${BACKUP_PATH}/README.md" << EOF
# Law7 Backup - ${TIMESTAMP}

This backup contains the complete law7 database for Russian legal documents.

## Contents

- \`postgresql/law7.dump\` - PostgreSQL database dump (custom compressed format)
- \`qdrant/law_chunks.snapshot\` - Qdrant vector database snapshot
- \`.env.example\` - Environment configuration template

## Database Statistics

| Metric | Count |
|--------|-------|
| Documents | ${doc_count} |
| Code Articles | ${article_count} |
| Qdrant Vectors | ${point_count} |

## Prerequisites for Restore

- Docker and Docker Compose installed
- ~2 GB free disk space
- Ports 5433, 6333, 6380 available (or configure alternatives)

## Quick Restore Instructions

### 1. Clone the repository

\`\`\`bash
git clone https://github.com/mikhashev/law7
cd law7/docker
\`\`\`

### 2. Configure environment

\`\`\`bash
# Copy the env template from backup
cp backups/${BACKUP_NAME}/.env.example .env

# Edit .env if needed (change ports if conflicts exist)
nano .env
\`\`\`

### 3. Start containers

\`\`\`bash
docker-compose up -d
\`\`\`

### 4. Restore database

\`\`\`bash
./restore.sh ${BACKUP_NAME}
\`\`\`

### 5. Verify restore

\`\`\`bash
# Check PostgreSQL
docker exec law7-postgres psql -U law7 -d law7 -c "SELECT COUNT(*) FROM documents;"

# Check Qdrant
curl http://localhost:6333/collections/law_chunks
\`\`\`

## Full Documentation

For detailed instructions, see:
https://github.com/mikhashev/law7/docs/BACKUP_RESTORE.md

## Backup Details

- **Created**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
- **PostgreSQL Version**: 15-alpine
- **Qdrant Version**: latest
- **Backup Type**: Full database backup
- **Compression**: PostgreSQL custom format (level 9), Qdrant snapshot (gzip)

## Troubleshooting

### Port already in use

Edit \`docker/.env\` to change ports:
\`\`\`
DB_PORT=5434
REDIS_PORT=6381
\`\`\`

### Out of memory during restore

Restore PostgreSQL with single thread:
\`\`\`bash
docker exec -i law7-postgres pg_restore -U law7 -d law7 -j 1 \\
    --clean --if-exists --no-owner --no-acl < postgresql/law7.dump
\`\`\`

### Qdrant collection already exists

Delete before restoring:
\`\`\`bash
curl -X DELETE "http://localhost:6333/collections/law_chunks"
\`\`\`
EOF

    log_success "README created."
}

create_archive() {
    log_info "Creating compressed archive..."

    cd "${BACKUP_DIR}"

    # Create tar.gz archive
    tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"

    # Create checksum
    log_info "Creating SHA256 checksum..."
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "${BACKUP_NAME}.tar.gz" > "${BACKUP_NAME}.tar.gz.sha256"
    else
        log_warn "sha256sum not found, skipping checksum."
    fi

    local size=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
    log_success "Archive created: ${BACKUP_NAME}.tar.gz (${size})"

    cd "${SCRIPT_DIR}"
}

show_summary() {
    echo ""
    echo "======================================================================"
    log_success "Backup completed successfully!"
    echo "======================================================================"
    echo ""
    echo "Backup location:"
    echo "  ${BACKUP_PATH}/"
    echo ""
    echo "Archive (for sharing):"
    echo "  ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    echo "  ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz.sha256"
    echo ""
    echo "To restore this backup:"
    echo "  ./restore.sh ${BACKUP_NAME}"
    echo ""
    echo "To verify integrity:"
    echo "  ./check-backup.sh ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo ""
    echo "======================================================================"
    echo "                    Law7 Database Backup"
    echo "======================================================================"
    echo ""
    echo "Backup: ${BACKUP_NAME}"
    echo ""

    # Create backup directory
    mkdir -p "${BACKUP_PATH}"

    # Execute backup steps
    check_dependencies
    check_containers_running
    backup_postgresql
    backup_qdrant
    create_readme
    create_archive

    # Copy .env.example to backup (template only, not actual .env)
    if [ -f "${SCRIPT_DIR}/../.env.example" ]; then
        cp "${SCRIPT_DIR}/../.env.example" "${BACKUP_PATH}/.env.example"
        log_info "Environment template copied."
    fi

    show_summary
}

# Run main function
main "$@"
