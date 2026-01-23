#!/bin/bash
# docker/restore.sh - Restore PostgreSQL and Qdrant from backup
#
# Usage:
#   cd docker
#   ./restore.sh <backup_name>
#
# Example:
#   ./restore.sh law7_backup_20250124_120000
#
# The script will:
#   1. Validate the backup archive
#   2. Extract the archive
#   3. Restore PostgreSQL database
#   4. Restore Qdrant collection
#   5. Verify the restore was successful

set -e

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"
BACKUP_NAME="$1"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
ARCHIVE_PATH="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

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
CYAN='\033[0;36m'
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

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."

    local missing=()

    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v curl >/dev/null 2>&1 || missing+=("curl")
    command -v tar >/dev/null 2>&1 || missing+=("tar")

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Please install missing tools and try again."
        exit 1
    fi

    log_success "All dependencies found."
}

validate_backup() {
    log_step "Validating backup..."

    # Check if backup name is provided
    if [ -z "$BACKUP_NAME" ]; then
        log_error "No backup name specified."
        log_info "Usage: ./restore.sh <backup_name>"
        log_info "Example: ./restore.sh law7_backup_20250124_120000"
        log_info ""
        log_info "Available backups in backups/:"
        if [ -d "${BACKUP_DIR}" ]; then
            for dir in "${BACKUP_DIR}"/law7_backup_*/; do
                if [ -d "$dir" ]; then
                    echo "  $(basename "$dir")"
                fi
            done
        else
            log_info "  (backups directory not found)"
        fi
        exit 1
    fi

    # Check if backup archive exists
    if [ ! -f "$ARCHIVE_PATH" ]; then
        log_error "Backup archive not found: ${ARCHIVE_PATH}"

        # Check if extracted backup exists
        if [ -d "$BACKUP_PATH" ]; then
            log_info "Found extracted backup at: ${BACKUP_PATH}"
            log_info "Proceeding with extracted backup..."
            return 0
        else
            log_error "Backup directory also not found: ${BACKUP_PATH}"
            exit 1
        fi
    fi

    # Verify checksum if available
    local checksum_file="${ARCHIVE_PATH}.sha256"
    if [ -f "$checksum_file" ]; then
        log_info "Verifying SHA256 checksum..."
        if command -v sha256sum >/dev/null 2>&1; then
            if sha256sum -c "$checksum_file" > /dev/null 2>&1; then
                log_success "Checksum verified."
            else
                log_error "Checksum verification failed!"
                log_warn "Proceeding anyway (backup may be corrupted)..."
            fi
        else
            log_warn "sha256sum not available, skipping checksum verification."
        fi
    fi

    # Verify tar integrity
    log_info "Verifying archive integrity..."
    if ! tar -tzf "$ARCHIVE_PATH" > /dev/null 2>&1; then
        log_error "Archive is corrupted or not a valid tar.gz file."
        exit 1
    fi

    log_success "Backup archive validated."
}

extract_backup() {
    # If backup is already extracted, skip
    if [ -d "$BACKUP_PATH" ]; then
        log_info "Backup already extracted at: ${BACKUP_PATH}"
        return 0
    fi

    # Only extract if archive exists
    if [ ! -f "$ARCHIVE_PATH" ]; then
        log_error "Archive not found: ${ARCHIVE_PATH}"
        exit 1
    fi

    log_step "Extracting backup archive..."

    mkdir -p "$BACKUP_DIR"
    tar -xzf "$ARCHIVE_PATH" -C "$BACKUP_DIR"

    log_success "Backup extracted to: ${BACKUP_PATH}"
}

check_required_files() {
    log_step "Checking required backup files..."

    local required_files=(
        "${BACKUP_PATH}/postgresql/${POSTGRES_DB}.dump"
        "${BACKUP_PATH}/qdrant/${QDRANT_COLLECTION}.snapshot"
    )

    local missing_files=()

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done

    if [ ${#missing_files[@]} -gt 0 ]; then
        log_error "Missing required files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi

    log_success "All required files present."
}

check_containers_running() {
    log_step "Checking container status..."

    local postgres_running=$(docker ps --filter "name=${POSTGRES_CONTAINER}" --format "{{.Names}}")
    local qdrant_running=$(docker ps --filter "name=${QDRANT_CONTAINER}" --format "{{.Names}}")

    if [ -z "$postgres_running" ] || [ -z "$qdrant_running" ]; then
        log_warn "Some containers are not running."
        log_info "Starting containers with docker-compose..."
        cd "${SCRIPT_DIR}"
        docker-compose up -d postgres qdrant
        cd "${SCRIPT_DIR}"

        # Wait for containers to be ready
        log_info "Waiting for containers to be ready..."
        sleep 5
    fi

    log_success "Containers are running."
}

restore_postgresql() {
    log_step "Restoring PostgreSQL database..."

    local dump_file="${BACKUP_PATH}/postgresql/${POSTGRES_DB}.dump"

    # First, drop and recreate the database for clean restore
    log_info "Preparing database (drop and recreate)..."
    docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"
    docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d postgres -c "CREATE DATABASE ${POSTGRES_DB};"

    # Restore the database
    log_info "Restoring from dump (parallel, 4 jobs)..."
    docker exec -i ${POSTGRES_CONTAINER} pg_restore \
        -U ${POSTGRES_USER} \
        -d ${POSTGRES_DB} \
        -j 4 \
        --no-owner \
        --no-acl < "$dump_file"

    log_success "PostgreSQL restore completed."
}

restore_qdrant() {
    log_step "Restoring Qdrant collection..."

    local snapshot_file="${BACKUP_PATH}/qdrant/${QDRANT_COLLECTION}.snapshot"

    # Check if collection exists and delete it
    log_info "Checking for existing collection..."
    local collection_exists=$(curl -s "${QDRANT_URL}/collections/${QDRANT_COLLECTION}" | grep -o '"status":"' | wc -l)

    if [ "$collection_exists" -gt 0 ]; then
        log_info "Deleting existing collection..."
        curl -s -X DELETE "${QDRANT_URL}/collections/${QDRANT_COLLECTION}" > /dev/null
        sleep 1
    fi

    # Upload the snapshot
    log_info "Uploading snapshot (this may take a while)..."
    local response=$(curl -s -X POST \
        "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/upload?priority=snapshot" \
        -H "Content-Type: multipart/form-data" \
        -F "snapshot=@${snapshot_file}")

    # Check for errors
    if echo "$response" | grep -q "error\|false"; then
        log_error "Qdrant snapshot upload failed."
        log_error "Response: $response"
        log_warn "You may need to manually restore Qdrant."
        log_warn "Try: curl -X POST '${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/upload?priority=snapshot' \\"
        log_warn "  -H 'Content-Type: multipart/form-data' \\"
        log_warn "  -F 'snapshot=@${snapshot_file}'"
        return 1
    fi

    log_success "Qdrant restore completed."
}

verify_restore() {
    log_step "Verifying restore..."

    # Get expected stats from backup (if available)
    local expected_doc_count=""
    local expected_article_count=""
    local expected_point_count=""

    # Try to parse from README if it exists
    if [ -f "${BACKUP_PATH}/README.md" ]; then
        expected_doc_count=$(grep -A 10 "Database Statistics" "${BACKUP_PATH}/README.md" | grep "Documents" | grep -oP '[0-9]+' || echo "")
        expected_article_count=$(grep -A 10 "Database Statistics" "${BACKUP_PATH}/README.md" | grep "Code Articles" | grep -oP '[0-9]+' || echo "")
        expected_point_count=$(grep -A 10 "Database Statistics" "${BACKUP_PATH}/README.md" | grep "Qdrant Vectors" | grep -oP '[0-9]+' || echo "")
    fi

    # Check PostgreSQL document count
    log_info "Checking PostgreSQL documents..."
    local doc_count=$(docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM documents;")
    doc_count=$(echo "$doc_count" | tr -d ' ')

    if [ -n "$expected_doc_count" ]; then
        if [ "$doc_count" -eq "$expected_doc_count" ]; then
            log_success "Documents: ${doc_count} (expected: ${expected_doc_count})"
        else
            log_warn "Documents: ${doc_count} (expected: ${expected_doc_count})"
        fi
    else
        log_info "Documents: ${doc_count}"
    fi

    # Check code article versions
    log_info "Checking code article versions..."
    local article_count=$(docker exec ${POSTGRES_CONTAINER} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM code_article_versions;")
    article_count=$(echo "$article_count" | tr -d ' ')

    if [ -n "$expected_article_count" ]; then
        if [ "$article_count" -eq "$expected_article_count" ]; then
            log_success "Code Articles: ${article_count} (expected: ${expected_article_count})"
        else
            log_warn "Code Articles: ${article_count} (expected: ${expected_article_count})"
        fi
    else
        log_info "Code Articles: ${article_count}"
    fi

    # Check Qdrant collection
    log_info "Checking Qdrant collection..."
    local qdrant_info=$(curl -s "${QDRANT_URL}/collections/${QDRANT_COLLECTION}")
    local point_count=$(echo "$qdrant_info" | grep -oP '"points":[0-9]+' | grep -oP '[0-9]+' || echo "N/A")
    local vector_count=$(echo "$qdrant_info" | grep -oP '"vectors":[0-9]+' | grep -oP '[0-9]+' || echo "N/A")

    if [ "$point_count" != "N/A" ]; then
        if [ -n "$expected_point_count" ]; then
            if [ "$point_count" -eq "$expected_point_count" ]; then
                log_success "Qdrant Points: ${point_count} (expected: ${expected_point_count})"
            else
                log_warn "Qdrant Points: ${point_count} (expected: ${expected_point_count})"
            fi
        else
            log_info "Qdrant Points: ${point_count}"
        fi
    else
        log_warn "Could not retrieve Qdrant point count."
    fi

    log_success "Restore verification complete."
}

show_summary() {
    echo ""
    echo "======================================================================"
    log_success "Restore completed!"
    echo "======================================================================"
    echo ""
    echo "Restored from: ${BACKUP_NAME}"
    echo ""
    echo "You can now:"
    echo "  1. Start the MCP server: cd .. && npm start"
    echo "  2. Or run data sync scripts: poetry run python scripts/sync/content_sync.py"
    echo ""
    echo "To verify the restore:"
    echo "  # PostgreSQL"
    echo "  docker exec law7-postgres psql -U law7 -d law7 -c 'SELECT COUNT(*) FROM documents;'"
    echo ""
    echo "  # Qdrant"
    echo "  curl http://localhost:6333/collections/law_chunks"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo ""
    echo "======================================================================"
    echo "                    Law7 Database Restore"
    echo "======================================================================"
    echo ""
    echo "Backup: ${BACKUP_NAME}"
    echo ""

    # Confirm restore
    if [ -t 1 ]; then  # Only prompt if running in terminal
        echo -e "${YELLOW}This will REPLACE the current database with the backup.${NC}"
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Restore cancelled."
            exit 0
        fi
    fi

    # Execute restore steps
    check_dependencies
    validate_backup
    extract_backup
    check_required_files
    check_containers_running
    restore_postgresql
    restore_qdrant
    verify_restore

    show_summary
}

# Run main function
main "$@"
