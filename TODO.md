# Law7 TODO

## High Priority

### [MVP] Complete Testing Flow
- [ ] Fix content sync to run without embeddings (in progress)
- [ ] Test content parsing from API metadata
- [ ] Build and test MCP server
- [ ] Test all 4 MCP tools with real data

## Medium Priority

### Embeddings Model Upgrade
**Current**: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (768 dims, CPU-only)

**Recommended Upgrades** (for RTX 3060 12GB):

1. **`intfloat/multilingual-e5-large`** (1024 dims) ⭐ RECOMMENDED
   - Better quality for Russian text
   - GPU-accelerated (CUDA 12.8 compatible)
   - ~2-3x faster on GPU vs CPU
   - Install: `pip install sentence-transformers` + set device to 'cuda'

2. **OpenAI Embeddings API** (paid, highest quality)
   - `text-embedding-3-large` (3072 dims)
   - Best for production
   - Requires API key

**Changes needed:**
- [ ] Update `.env`: `EMBEDDING_DEVICE=cuda`
- [ ] Update `pyproject.toml`: Add `torch` with CUDA support
- [ ] Update `core/config.py`: `EMBEDDING_MODEL=intfloat/multilingual-e5-large`
- [ ] Test embeddings generation speed on GPU
- [ ] Re-generate all embeddings with new model

**Commands:**
```bash
# Install PyTorch with CUDA 12.x support
pip install torch --index-url https://download.pytorch.org/whl/cu124

# Or via conda
conda install pytorch torchvision torchaudio pytorch-cuda=12.4 -c pytorch -c nvidia

# Update config
echo "EMBEDDING_DEVICE=cuda" >> .env
echo "EMBEDDING_MODEL=intfloat/multilingual-e5-large" >> .env

# Re-run content sync with new model
poetry run python scripts/sync/content_sync.py --recreate-collection
```

### OCR Enhancement (Optional)
- [ ] Install Tesseract OCR for scanned PDFs
- [ ] Test OCR quality on Russian legal documents
- [ ] Add OCR fallback for documents with short API metadata

## Low Priority

### MCP Server Enhancements
- [ ] Add hybrid search (keyword + semantic combined)
- [ ] Add document summarization tool
- [ ] Add document comparison tool
- [ ] Add date range filtering in query-laws tool

### Data Pipeline
- [ ] Add incremental sync (only new documents)
- [ ] Add change detection via text_hash
- [ ] Add retry logic for failed API requests
- [ ] Add progress resumption after interruption

### Performance
- [ ] Optimize batch sizes for RTX 3060
- [ ] Add concurrent processing for embeddings
- [ ] Add caching for frequently accessed documents
