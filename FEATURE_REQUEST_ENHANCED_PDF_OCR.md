# Feature Request: Enhanced PDF Text Extraction for Russian Legal Documents

**Status**: Proposed
**Priority**: Medium
**Target**: Future implementation

## Problem Statement

The current `html_scraper.py` implementation has limited OCR capability for:
- Scanned PDFs from pravo.gov.ru
- Image-based documents
- Complex legal document layouts (tables, multi-column text, numbered articles)

## Current State

- **Tesseract OCR**: Basic support with Russian language data
- **Accuracy**: Medium - struggles with complex layouts
- **Performance**: Fast but limited accuracy on challenging documents

## Proposed Solution

Implement enhanced OCR using modern Vision-Language Models (VLMs) and advanced OCR libraries specifically optimized for Russian legal documents.

## Candidate Models to Evaluate

### Vision-Language Models

| Model | Parameters | Type | Strengths |
|-------|------------|------|-----------|
| [DeepSeek-OCR](https://huggingface.co/deepseek-ai/DeepSeek-OCR) | Unknown | OCR | +25% Cyrillic accuracy vs traditional OCR |
| [Qwen2.5-VL-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) | 3B | VLM | 32 language OCR, complex layouts |
| [Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) | 7B | VLM | Higher accuracy, good for tables |
| [PaddleOCR-VL](https://huggingface.co/PaddlePaddle/PaddleOCR-VL) | 0.9B | VLM | Ultra-compact, multilingual |

### Traditional OCR Libraries

| Library | Russian Support | Speed | Accuracy |
|---------|----------------|-------|----------|
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | ✅ Excellent | Fast | High |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | ✅ Good | Medium | High |
| [mmocr](https://github.com/open-mmlab/mmocr) | ✅ Excellent | Fast | High |
| Tesseract (current) | ✅ With rus data | Fast | Medium |

## Requirements

1. **Russian/Cyrillic Language Support** - All documents are in Russian
2. **Legal Document Formatting** - Tables, numbered articles, amendments, multi-column layouts
3. **Batch Processing** - 157,000+ documents to process
4. **Local Execution** - No API calls, privacy-preserving
5. **GPU Compatibility** - RTX 3060 (12GB VRAM available)
6. **Commercial License** - Must allow commercial usage

## Implementation Plan

### Phase 1: Research & Benchmarking

1. **Candidate Selection**
   - Review documentation for each candidate
   - Verify Russian/Cyrillic support claims
   - Check license compatibility

2. **Benchmark Setup**
   - Collect sample PDFs from pravo.gov.ru (various types)
   - Create evaluation dataset with ground truth
   - Define metrics: accuracy, speed, memory usage

3. **Testing**
   - Run each candidate on benchmark dataset
   - Measure accuracy, speed, resource usage
   - Document pros/cons

### Phase 2: Integration

1. **Add OCR Engine Abstraction**
   ```python
   class OCREngine(Protocol):
       def extract_text(self, pdf_path: str) -> str: ...
   ```

2. **Implement Selected Engine(s)**
   - Add to `scripts/parser/ocr_engine.py`
   - Support multiple engines with configuration flag

3. **Update `html_scraper.py`**
   - Use enhanced OCR for PDF-only documents
   - Fall back to Tesseract if needed

### Phase 3: Testing & Deployment

1. **A/B Testing**
   - Compare with current Tesseract approach
   - Measure accuracy improvement
   - Validate on sample documents

2. **Configuration**
   ```bash
   # .env
   OCR_ENGINE=deepseek  # tesseract|paddleocr|deepseek|qwen
   OCR_GPU_ENABLED=true
   ```

3. **Rollout**
   - Deploy with feature flag
   - Monitor accuracy and performance
   - Iterate based on results

## References

- [7 Best Open-Source OCR Models 2025](https://www.e2enetworks.com/blog/complete-guide-open-source-ocr-models-2025)
- [PaddleOCR-VL: Boosting Multilingual Document Parsing](https://ernie.baidu.com/blog/posts/paddleocr-vl/)
- [Qwen2.5-VL Technical Report](https://arxiv.org/pdf/2502.13923)
- [DeepSeek-OCR: Contexts Optical Compression](https://arxiv.org/html/2510.18234v1)
- [HuggingFace Image-to-Text Models](https://huggingface.co/models?pipeline_tag=image-text-to-text&sort=likes)

## Related Issues/PRs

- [Initial Selenium implementation plan](../.claude/plans/binary-stirring-comet.md)
- [Current html_scraper.py](../scripts/parser/html_scraper.py)
