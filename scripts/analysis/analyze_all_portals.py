#!/usr/bin/env python3
"""
Run all Phase 7C portal analysis scripts.

This script runs all three portal analysis scripts and generates a consolidated report.

Usage:
    poetry run python scripts/analysis/analyze_all_portals.py
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from datetime import datetime

from analyze_supreme_court import SupremeCourtAnalyzer
from analyze_minfin import MinfinAnalyzer
from analyze_moscow_duma import MoscowDumaAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Run all portal analyses."""
    print("\n" + "="*70)
    print("PHASE 7C PORTAL ANALYSIS - ALL PORTALS")
    print("="*70)
    print(f"Started at: {datetime.now().isoformat()}")

    # Analyze Supreme Court
    print("\n" + "-"*70)
    print("1/3: Analyzing Supreme Court Portal...")
    print("-"*70)
    try:
        supreme_analyzer = SupremeCourtAnalyzer()
        supreme_analyzer.run()
    except Exception as e:
        logger.error(f"Supreme Court analysis failed: {e}")

    # Analyze Ministry of Finance
    print("\n" + "-"*70)
    print("2/3: Analyzing Ministry of Finance Portal...")
    print("-"*70)
    try:
        minfin_analyzer = MinfinAnalyzer()
        minfin_analyzer.run()
    except Exception as e:
        logger.error(f"Ministry of Finance analysis failed: {e}")

    # Analyze Moscow Duma
    print("\n" + "-"*70)
    print("3/3: Analyzing Moscow City Duma Portal...")
    print("-"*70)
    try:
        moscow_analyzer = MoscowDumaAnalyzer()
        moscow_analyzer.run()
    except Exception as e:
        logger.error(f"Moscow Duma analysis failed: {e}")

    print("\n" + "="*70)
    print("ALL ANALYSES COMPLETE")
    print("="*70)
    print(f"Completed at: {datetime.now().isoformat()}")
    print("\nResults saved to: scripts/analysis/results/")
    print("- supreme_court_analysis.json")
    print("- minfin_analysis.json")
    print("- moscow_duma_analysis.json")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
