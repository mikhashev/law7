# Backup and Restore Guide

This guide explains how to create and restore database backups for the law7 project.

## Table of Contents

- [Overview](#overview)
- [Quick Start: Download Latest Backup](#quick-start-download-latest-backup)
- [Creating Backups](#creating-backups)
- [Verifying Backups](#verifying-backups)
- [Restoring from Backup](#restoring-from-backup)
- [Sharing Backups](#sharing-backups)
- [Troubleshooting](#troubleshooting)

## Overview

The law7 project uses three databases:

| Database | Purpose | Backed Up? | Size (approx) |
|----------|---------|------------|---------------|
| PostgreSQL | Legal documents metadata and content | Yes | ~217 MB |
| Qdrant | Vector embeddings for semantic search | Yes | ~2-300 MB |
| Redis | Query cache (1-hour TTL) | No | - |

**Total backup size**: ~218 MB compressed (current)

### What Gets Backed Up

- **PostgreSQL**: All tables including documents (1.1M+), document_content (47K+), code_article_versions (6K+), amendment tracking
- **Qdrant**: The `law_chunks` collection with vector embeddings (265 in current backup, full sync pending)
- **Configuration**: `.env.example` template (not actual credentials)

### Database Statistics (Current Backup)

| Metric | Count |
|--------|-------|
| Total Documents | 1,134,985 |
| Documents with Content | 47,871 (4.22%) |
| Code Articles | 6,232 (22 consolidated codes) |
| Qdrant Vectors | 265 (test data - full embeddings pending) |
| Years Covered | 2019-2026 |

## Quick Start: Download Latest Backup

### Public Backup Available

The latest backup is available for download:

| Property | Value |
|----------|-------|
| **Download** | [law7_backup_20260211_014519.tar.gz](https://drive.google.com/file/d/1DPLpFpuwUZbLZEGo2TxnCAcLRdb2V1aD/view?usp=sharing) |
| **Size** | 218 MB |
| **SHA256** | `70a1d8fc6b27b67ad7f12f03f017d02b5f68a0c895447159039800965895f8b2` |

### Quick Restore (5 minutes)

```bash
# 1. Download backup from link above
# 2. Clone repository
git clone https://github.com/mikhashev/law7
cd law7/docker

# 3. Place downloaded .tar.gz in backups/ directory
# 4. Start Docker services
docker-compose up -d

# 5. Restore backup
./restore.sh law7_backup_20260211_014519
```

### Legal Disclaimer

**IMPORTANT**: This backup contains legal documents from official Russian government sources (pravo.gov.ru).

- **Official government documents** are in the **public domain** under Russian Civil Code Article 1259
- **NOT for official use** in court or government bodies
- **NO guarantee of accuracy, completeness, or timeliness**
- Always verify against original sources for official purposes

The **software and database structure** are licensed under AGPL-3.0.
The **legal documents themselves** are public domain under Russian law.

## Creating Backups

### Quick Start

```bash
cd docker
./backup.sh
```

This creates a timestamped backup in `docker/backups/`:
```
backups/
└── law7_backup_20250124_120000/
    ├── README.md
    ├── .env.example
    ├── postgresql/
    │   └── law7.dump
    └── qdrant/
        └── law_chunks.snapshot
```

### Archive Created

The script also creates a compressed archive ready for sharing:
```
law7_backup_20250124_120000.tar.gz
law7_backup_20250124_120000.tar.gz.sha256
```

### Prerequisites

Ensure containers are running before backing up:
```bash
cd docker
docker-compose up -d
```

### What the Script Does

1. Checks dependencies (docker, curl, tar, sha256sum)
2. Verifies containers are running
3. Dumps PostgreSQL using `pg_dump -Fc` (custom compressed format)
4. Creates Qdrant snapshot via REST API
5. Generates README with database statistics
6. Creates tar.gz archive with SHA256 checksum

## Verifying Backups

### Quick Verification

```bash
cd docker
./check-backup.sh backups/law7_backup_20250124_120000.tar.gz
```

### What Gets Checked

1. Archive integrity (tar.gz format)
2. SHA256 checksum (if available)
3. Required files presence
4. Database statistics from README
5. File sizes

### Output Example

```
======================================================================
                    Law7 Backup Verification
======================================================================

[====] Verifying Archive Integrity
[SUCCESS] Archive integrity: OK
[INFO] Archive size: 987.32 MB (1035423744 bytes)

[====] Verifying SHA256 Checksum
[SUCCESS] Checksum verification: PASSED

[====] Required Files Check
[SUCCESS]   [FOUND]  postgresql/law7.dump  (650.23 MB)
[SUCCESS]   [FOUND]  qdrant/law_chunks.snapshot  (320.15 MB)
[SUCCESS]   [FOUND]  .env.example  (2.45 KB)
[SUCCESS]   [FOUND]  README.md  (3.21 KB)

[====] Database Statistics

| Metric        | Count    |
|---------------|----------|
| Documents     | 157730   |
| Code Articles | 8118     |
| Qdrant Vectors| 77819    |
```

## Restoring from Backup

### Quick Start

```bash
cd docker
./restore.sh law7_backup_20250124_120000
```

### Prerequisites for Restore

1. **Docker and Docker Compose** installed
   - Download from https://www.docker.com/products/docker-desktop/
2. **2+ GB free disk space**
3. **Ports available**: 5433, 6333, 6380 (or configure alternatives)
4. **Git** (to clone repository)

### Step-by-Step Restore

#### 1. Clone the Repository

```bash
git clone https://github.com/mikhashev/law7
cd law7/docker
```

#### 2. Copy and Extract Backup

```bash
# If you have the tar.gz archive
cp /path/to/law7_backup_*.tar.gz backups/
cd backups
tar -xzf law7_backup_*.tar.gz
cd ..

# OR if you already have the extracted directory
# Just copy it to backups/
```

#### 3. Configure Environment

```bash
# Copy from backup or from repository
cp backups/law7_backup_*/.env.example .env
# OR
cp ../.env.example .env

# Edit if needed (nano, vim, or any text editor)
nano .env
```

Common changes in `.env`:
```bash
# Change ports if conflicts exist
DB_PORT=5434
REDIS_PORT=6381
```

#### 4. Start Containers

```bash
docker-compose up -d
```

Wait for containers to be healthy (10-20 seconds).

#### 5. Restore Database

```bash
./restore.sh law7_backup_20250124_120000
```

The script will:
1. Validate the backup
2. Extract the archive (if needed)
3. Drop and recreate PostgreSQL database
4. Restore PostgreSQL data (parallel, 4 jobs)
5. Delete existing Qdrant collection (if exists)
6. Upload Qdrant snapshot
7. Verify the restore

#### 6. Verify Restore

```bash
# Check PostgreSQL document count
docker exec law7-postgres psql -U law7 -d law7 -c "SELECT COUNT(*) FROM documents;"
# Expected: ~157730

# Check Qdrant collection info
curl http://localhost:6333/collections/law_chunks
# Expected: "points": 77819, "vectors": 75401

# Check code article versions
docker exec law7-postgres psql -U law7 -d law7 -c "SELECT COUNT(*) FROM code_article_versions;"
# Expected: ~8118
```

### Confirm Prompt

The restore script asks for confirmation before proceeding:
```
This will REPLACE the current database with the backup.
Continue? (y/N):
```

## Sharing Backups

### What to Share

Share these files:
```
law7_backup_20250124_120000.tar.gz
law7_backup_20250124_120000.tar.gz.sha256
```

### How to Share

Options:
1. **File sharing service**: Google Drive, Dropbox, OneDrive, WeTransfer
2. **Direct download**: Host on a web server
3. **Git LFS**: For version-controlled backups (large files)

### What Your Friend Needs

Tell them to:
1. Install Docker Desktop
2. Clone this repository: `git clone https://github.com/mikhashev/law7`
3. Follow restore instructions above

### Verification Before Sharing

```bash
./check-backup.sh backups/law7_backup_*.tar.gz
```

## Troubleshooting

### Port Already in Use

**Error**: `port is already allocated`

**Solution**: Change ports in `docker/.env`:
```bash
DB_PORT=5434       # Instead of 5433
REDIS_PORT=6381    # Instead of 6380
# Qdrant URL in .env must also match
```

### Out of Memory During Restore

**Error**: `memory exhausted` or `out of memory`

**Solution**: Restore PostgreSQL with single thread:
```bash
docker exec -i law7-postgres pg_restore -U law7 -d law7 -j 1 \
    --clean --if-exists --no-owner --no-acl < postgresql/law7.dump
```

### Qdrant Collection Already Exists

**Error**: `collection already exists`

**Solution**: Manually delete before restore:
```bash
curl -X DELETE "http://localhost:6333/collections/law_chunks"
./restore.sh law7_backup_20250124_120000
```

### Checksum Verification Failed

**Error**: `SHA256 checksum mismatch`

**Solutions**:
1. Re-download the backup
2. Check if file was corrupted during transfer
3. Verify with sender: `sha256sum law7_backup_*.tar.gz`

### Containers Not Starting

**Error**: Containers fail to start

**Solutions**:
```bash
# Check Docker is running
docker ps

# Check logs
docker-compose logs postgres
docker-compose logs qdrant

# Re-create containers
docker-compose down -v
docker-compose up -d
```

### Permission Denied on Scripts

**Error**: `Permission denied: ./backup.sh`

**Solution**: Make scripts executable:
```bash
chmod +x docker/backup.sh
chmod +x docker/restore.sh
chmod +x docker/check-backup.sh
```

**Windows (Git Bash)**:
```bash
# Run with bash explicitly
bash docker/backup.sh
```

### Windows-Specific Issues

**Git Bash**: Scripts should work natively.

**WSL**: Scripts work natively.

**PowerShell/CMD**: Use Git Bash or WSL to run scripts.

### Backup Too Large

If backup is too large to share:
1. Exclude Qdrant (can rebuild from PostgreSQL):
   - Edit `backup.sh` to skip Qdrant
   - Recipient runs content sync to rebuild embeddings
2. Split archive:
   ```bash
   split -b 500M law7_backup.tar.gz law7_backup.tar.gz.part.
   ```
   Recipient joins:
   ```bash
   cat law7_backup.tar.gz.part.* > law7_backup.tar.gz
   ```

### Slow Restore

Restore speed depends on:
- Disk I/O speed
- Docker performance
- Database size

**Tips**:
- Use SSD for Docker storage
- Allocate more resources to Docker Desktop
- Close other applications during restore

## Advanced Usage

### Automated Backups

Create a cron job or scheduled task:

**Linux/macOS (cron)**:
```bash
# Edit crontab
crontab -e

# Add: Daily backup at 2 AM
0 2 * * * cd /path/to/law7/docker && ./backup.sh
```

**Windows (Task Scheduler)**:
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 2:00 AM
4. Action: Start a program
   - Program: `C:\Program Files\Git\bin\bash.exe`
   - Arguments: `-c "cd /c/path/to/law7/docker && ./backup.sh"`

### Backup to Remote Location

```bash
# After backup, send to remote server
./backup.sh
scp backups/law7_backup_*.tar.gz user@server:/backups/

# Or use rclone for cloud storage
./backup.sh
rclone copy backups/law7_backup_*.tar.gz remote:law7-backups/
```

### Partial Restore (PostgreSQL Only)

If you only need to restore PostgreSQL:
```bash
docker exec law7-postgres psql -U law7 -d postgres -c "DROP DATABASE IF EXISTS law7;"
docker exec law7-postgres psql -U law7 -d postgres -c "CREATE DATABASE law7;"
docker exec -i law7-postgres pg_restore -U law7 -d law7 -j 4 --no-owner --no-acl < postgresql/law7.dump
```

### Export to SQL (Plain Text)

For human-readable backup:
```bash
docker exec law7-postgres pg_dump -U law7 -d law7 > law7.sql
```

Restore:
```bash
docker exec -i law7-postgres psql -U law7 -d law7 < law7.sql
```

## Additional Resources

- [CLAUDE.md](../CLAUDE.md) - Project overview and setup
- [DATA_PIPELINE.md](DATA_PIPELINE.md) - Data pipeline documentation
- [PostgreSQL Documentation](https://www.postgresql.org/docs/current/backup.html)
- [Qdrant Snapshots](https://qdrant.tech/documentation/concepts/snapshots/)
