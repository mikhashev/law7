#!/bin/bash
# docker/check-backup.sh - Verify backup integrity and show contents
#
# Usage:
#   cd docker
#   ./check-backup.sh <backup_archive>
#
# Example:
#   ./check-backup.sh backups/law7_backup_20250124_120000.tar.gz
#
# This script will:
#   1. Verify the tar.gz archive integrity
#   2. Verify the SHA256 checksum (if available)
#   3. List archive contents
#   4. Show file sizes and database statistics

set -e

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_FILE="$1"

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

log_header() {
    echo -e "${CYAN}[====]${NC} $1"
}

print_separator() {
    echo "----------------------------------------------------------------------"
}

human_readable_size() {
    local bytes=$1
    if [ "$bytes" -ge 1073741824 ]; then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1073741824}") GB"
    elif [ "$bytes" -ge 1048576 ]; then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1048576}") MB"
    elif [ "$bytes" -ge 1024 ]; then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1024}") KB"
    else
        echo "${bytes} B"
    fi
}

verify_tar_integrity() {
    log_header "Verifying Archive Integrity"

    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "File not found: $BACKUP_FILE"
        exit 1
    fi

    log_info "Checking file: $BACKUP_FILE"

    # Verify tar.gz integrity
    if tar -tzf "$BACKUP_FILE" > /dev/null 2>&1; then
        log_success "Archive integrity: OK"
    else
        log_error "Archive is corrupted or not a valid tar.gz file."
        exit 1
    fi

    # Show file size
    local file_size=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null || echo "N/A")
    if [ "$file_size" != "N/A" ]; then
        local hr_size=$(human_readable_size "$file_size")
        log_info "Archive size: ${hr_size} (${file_size} bytes)"
    fi

    echo ""
}

verify_checksum() {
    log_header "Verifying SHA256 Checksum"

    local checksum_file="${BACKUP_FILE}.sha256"

    if [ ! -f "$checksum_file" ]; then
        log_warn "Checksum file not found: ${checksum_file}"
        log_info "Skipping checksum verification."
        echo ""
        return
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        log_info "Checking checksum..."

        if sha256sum -c "$checksum_file" 2>/dev/null; then
            log_success "Checksum verification: PASSED"
        else
            log_error "Checksum verification: FAILED"
            log_error "The backup file may have been corrupted or modified."
            exit 1
        fi
    else
        log_warn "sha256sum command not available."
        log_info "Skipping checksum verification."
    fi

    echo ""
}

list_contents() {
    log_header "Archive Contents"

    log_info "Listing files in archive..."
    echo ""

    # List archive contents with sizes (by extracting to temp and checking)
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    tar -xzf "$BACKUP_FILE" -C "$temp_dir"

    # Find the backup directory
    local backup_dir=$(find "$temp_dir" -maxdepth 1 -type d -name "law7_backup_*" | head -1)

    if [ -z "$backup_dir" ]; then
        log_error "Could not find backup directory in archive."
        exit 1
    fi

    # Display directory structure
    echo "${backup_dir}/"
    (cd "$backup_dir" && find . -type f | sort | while read -r file; do
        local size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "0")
        local hr_size=$(human_readable_size "$size")
        printf "  %-40s %10s\n" "${file#./}" "$hr_size"
    done)

    echo ""
}

show_statistics() {
    log_header "Database Statistics"

    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    tar -xzf "$BACKUP_FILE" -C "$temp_dir"

    local backup_dir=$(find "$temp_dir" -maxdepth 1 -type d -name "law7_backup_*" | head -1)
    local readme_file="${backup_dir}/README.md"

    if [ -f "$readme_file" ]; then
        # Extract statistics from README
        echo ""
        grep -A 10 "Database Statistics" "$readme_file" | while IFS= read -r line; do
            if [[ "$line" =~ ^\|.*\|$ ]]; then
                # Format table row
                echo "$line" | sed 's/^[[:space:]]*//'
            fi
        done
    else
        log_warn "README.md not found in backup."
    fi

    echo ""
}

show_backup_metadata() {
    log_header "Backup Metadata"

    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    tar -xzf "$BACKUP_FILE" -C "$temp_dir"

    local backup_dir=$(find "$temp_dir" -maxdepth 1 -type d -name "law7_backup_*" | head -1)
    local backup_name=$(basename "$backup_dir")

    echo "  Backup Name:  ${backup_name}"
    echo "  Archive File: $(basename "$BACKUP_FILE")"

    # Extract timestamp from backup name
    local timestamp=$(echo "$backup_name" | grep -oP '[0-9]{8}_[0-9]{6}')
    if [ -n "$timestamp" ]; then
        local date_part=$(echo "$timestamp" | cut -d'_' -f1)
        local time_part=$(echo "$timestamp" | cut -d'_' -f2)
        echo "  Created:      ${date_part:0:4}-${date_part:4:2}-${date_part:6:2} ${time_part:0:2}:${time_part:2:2}:${time_part:4:2}"
    fi

    echo ""
}

verify_required_files() {
    log_header "Required Files Check"

    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    tar -xzf "$BACKUP_FILE" -C "$temp_dir"

    local backup_dir=$(find "$temp_dir" -maxdepth 1 -type d -name "law7_backup_*" | head -1)

    local required_files=(
        "postgresql/law7.dump"
        "qdrant/law_chunks.snapshot"
        ".env.example"
        "README.md"
    )

    local all_present=true

    for file in "${required_files[@]}"; do
        local full_path="${backup_dir}/${file}"
        if [ -f "$full_path" ]; then
            local size=$(stat -c%s "$full_path" 2>/dev/null || stat -f%z "$full_path" 2>/dev/null || echo "0")
            local hr_size=$(human_readable_size "$size")
            log_success "  [FOUND]  ${file}  (${hr_size})"
        else
            log_error "  [MISSING] ${file}"
            all_present=false
        fi
    done

    echo ""

    if [ "$all_present" = true ]; then
        log_success "All required files are present."
    else
        log_error "Some required files are missing!"
        exit 1
    fi

    echo ""
}

show_restore_command() {
    log_header "Restore Command"

    local backup_name=$(basename "$BACKUP_FILE" .tar.gz)

    echo "  To restore this backup, run:"
    echo ""
    echo "    cd docker"
    echo "    ./restore.sh ${backup_name}"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo ""
    echo "======================================================================"
    echo "                    Law7 Backup Verification"
    echo "======================================================================"
    echo ""

    # Check if backup file is provided
    if [ -z "$BACKUP_FILE" ]; then
        log_error "No backup file specified."
        echo ""
        echo "Usage: ./check-backup.sh <backup_archive>"
        echo ""
        echo "Example:"
        echo "  ./check-backup.sh backups/law7_backup_20250124_120000.tar.gz"
        echo ""
        echo "Available backups in backups/:"
        if [ -d "${SCRIPT_DIR}/backups" ]; then
            for file in "${SCRIPT_DIR}/backups"/law7_backup_*.tar.gz; do
                if [ -f "$file" ]; then
                    echo "  $(basename "$file")"
                fi
            done
        else
            echo "  (backups directory not found)"
        fi
        exit 1
    fi

    # Resolve relative path
    if [[ ! "$BACKUP_FILE" =~ ^/ ]] && [[ ! "$BACKUP_FILE" =~ ^.:/ ]]; then
        BACKUP_FILE="${SCRIPT_DIR}/${BACKUP_FILE}"
    fi

    # Run verification checks
    verify_tar_integrity
    verify_checksum
    show_backup_metadata
    verify_required_files
    list_contents
    show_statistics
    show_restore_command

    echo "======================================================================"
    log_success "Backup verification complete!"
    echo "======================================================================"
    echo ""
}

# Run main function
main "$@"
