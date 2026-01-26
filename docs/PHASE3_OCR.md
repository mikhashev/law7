# Phase 3: Enhanced OCR Implementation

**Duration:** Weeks 9-12
**Priority:** MEDIUM
**Status:** Not Started

---

## Overview

Improve PDF parsing quality by evaluating and implementing better OCR engines for Russian legal text.

---

## 3.1 OCR Engine Abstraction

**Priority:** MEDIUM - Improves PDF parsing quality

### Current State

Basic Tesseract OCR in `html_parser.py`

### Goal

Support multiple OCR engines with configuration

### Create OCR Engine Interface

```python
# scripts/parser/ocr_engine.py
from typing import Protocol

class OCREngine(Protocol):
    def extract_text(self, pdf_path: str) -> str:
        """Extract text from PDF"""
        ...

class TesseractOCREngine:
    """Current implementation"""
    ...

class PaddleOCREngine:
    """PaddleOCR implementation - better Russian support"""
    ...

class DeepSeekOCREngine:
    """DeepSeek-OCR VLM implementation - highest accuracy"""
    ...

def get_ocr_engine() -> OCREngine:
    """Factory function based on config"""
    engine_type = os.getenv("OCR_ENGINE", "tesseract")
    if engine_type == "paddleocr":
        return PaddleOCREngine()
    elif engine_type == "deepseek":
        return DeepSeekOCREngine()
    return TesseractOCREngine()
```

### Files to Create/Modify

- `scripts/parser/ocr_engine.py` (new)
- `scripts/parser/html_parser.py` (use OCR engine abstraction)
- `.env` (add `OCR_ENGINE` config)

---

## 3.2 Benchmark OCR Options

**Priority:** MEDIUM - Data-driven decision on OCR engine

### Candidate Models

1. **PaddleOCR** - Fast, good Russian support, 82.5% accuracy
2. **DeepSeek-OCR** - +25% Cyrillic accuracy vs Tesseract
3. **Qwen2.5-VL** - 32 language OCR, complex layouts
4. **Tesseract** (current) - Baseline

### Benchmark Setup

```python
# scripts/parser/benchmark_ocr.py
def benchmark_ocr():
    """Test all OCR engines on sample documents"""
    samples = [
        "scanned_pdf_1.pdf",
        "complex_layout.pdf",
        "table_heavy.pdf",
        "multi_column.pdf"
    ]
    results = {}
    for engine in [Tesseract, PaddleOCR, DeepSeek]:
        for sample in samples:
            # Measure accuracy, speed, memory
            pass
    return results
```

### Metrics to Track

- Accuracy (% correct characters for Russian legal text)
- Speed (docs/minute)
- Memory usage (GB)
- GPU utilization (if applicable)

### Files to Create

- `scripts/parser/benchmark_ocr.py`
- `scripts/parser/ocr_samples/` (test PDFs)

---

## 3.3 Deploy Enhanced OCR

**Priority:** LOW - After benchmarking completes

### Implementation

1. Select best OCR engine from benchmark
2. Add Poetry dependency (e.g., `paddleocr` or `paddlepaddle`)
3. Update `.env` with selected engine
4. Deploy with feature flag (process 10% of documents first)
5. Monitor accuracy and performance
6. Roll out to 100% if successful

### Files to Modify

- `pyproject.toml` (add OCR dependencies)
- `.env.example` (document OCR_ENGINE option)
- `scripts/parser/html_parser.py` (use selected engine)

---

## Deliverables

- OCR engine abstraction layer
- Benchmark results comparing OCR options
- Improved OCR engine deployed and configured

---

## Related Phases

- **Requires:** [Phase 1](./PHASE1_FOUNDATION.md) (tests for OCR)
- **Improves:** [Phase 4](./PHASE4_REGIONAL.md) (better regional document parsing)

---

## Timeline

**Week 9:** OCR engine abstraction
**Week 10:** Benchmark OCR options
**Week 11-12:** Deploy selected engine

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** Phase 1 (tests)
**Blocking:** None (quality improvement)
