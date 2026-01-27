#!/usr/bin/env python3
"""
Moscow City Duma Portal Analysis Script.

This script analyzes the Moscow City Duma portal (duma.mos.ru) to understand
its structure, API availability, and KoAP document patterns.

Usage:
    poetry run python scripts/analysis/analyze_moscow_duma.py
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
import re

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MoscowDumaAnalyzer:
    """Analyze Moscow City Duma portal structure."""

    BASE_URL = "https://duma.mos.ru"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.findings = {
            "portal": "Moscow City Duma (duma.mos.ru)",
            "timestamp": datetime.now().isoformat(),
            "api_endpoints": [],
            "html_structure": {},
            "koap_patterns": {},
            "errors": []
        }

    def analyze_documentation_page(self):
        """Analyze the documentation section."""
        logger.info("Analyzing documentation page...")

        url = f"{self.BASE_URL}/ru/documentation/"
        try:
            logger.info(f"Fetching {url}...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for API calls in scripts
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string:
                    # Look for API endpoints in JavaScript
                    api_patterns = re.findall(
                        r'["\']https?://[^"\']*(?:api|ajax|json)["\']',
                        script.string
                    )
                    for pattern in api_patterns:
                        if pattern not in self.findings["api_endpoints"]:
                            self.findings["api_endpoints"].append(pattern)

            # Look for KoAP section
            koap_link = soup.find("a", href=re.compile(r"koap|KoAP|административн", re.I))
            if koap_link:
                self.findings["koap_patterns"]["koap_link_found"] = True
                self.findings["koap_patterns"]["koap_link"] = koap_link.get("href")

            # Look for document categories
            categories = soup.find_all("a", href=re.compile(r"category|razdel|section"))
            if categories:
                self.findings["html_structure"]["category_links_found"] = len(categories)

        except Exception as e:
            error_msg = f"Error analyzing documentation page: {e}"
            logger.error(error_msg)
            self.findings["errors"].append(error_msg)

    def check_api_endpoints(self):
        """Check for common API endpoints."""
        logger.info("Checking for API endpoints...")

        common_api_paths = [
            "/api/documents",
            "/api/v1/documents",
            "/ru/api/document",
            "/api/koap",
        ]

        for path in common_api_paths:
            try:
                url = f"{self.BASE_URL}{path}"
                logger.info(f"Trying {url}...")
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.findings["api_endpoints"].append({
                            "url": url,
                            "status": "works",
                            "response_structure": list(data.keys()) if isinstance(data, dict) else "array"
                        })
                        logger.info(f"✓ Found working API: {url}")
                    except:
                        pass
            except Exception as e:
                pass

    def print_findings(self):
        """Print analysis findings."""
        print("\n" + "="*70)
        print("MOSCOW CITY DUMA PORTAL ANALYSIS FINDINGS")
        print("="*70)

        print(f"\nPortal: {self.findings['portal']}")
        print(f"Timestamp: {self.findings['timestamp']}")

        print("\n" + "-"*70)
        print("API ENDPOINTS")
        print("-"*70)
        if self.findings["api_endpoints"]:
            for endpoint in self.findings["api_endpoints"]:
                print(f"  • {endpoint}")
        else:
            print("  No API endpoints found")

        print("\n" + "-"*70)
        print("KOAP PATTERNS")
        print("-"*70)
        for key, value in self.findings["koap_patterns"].items():
            print(f"  {key}: {value}")

        if self.findings["errors"]:
            print("\n" + "-"*70)
            print("ERRORS")
            print("-"*70)
            for error in self.findings["errors"]:
                print(f"  • {error}")

        print("\n" + "="*70)
        print("ANALYSIS COMPLETE")
        print("="*70 + "\n")

    def save_findings(self):
        """Save findings to JSON file."""
        import json

        output_file = Path(__file__).parent / "results" / "moscow_duma_analysis.json"
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.findings, f, indent=2, ensure_ascii=False)

        logger.info(f"Findings saved to {output_file}")

    def run(self):
        """Run complete analysis."""
        logger.info("Starting Moscow City Duma portal analysis...")

        self.check_api_endpoints()
        self.analyze_documentation_page()

        self.print_findings()
        self.save_findings()


def main():
    """Main entry point."""
    analyzer = MoscowDumaAnalyzer()
    analyzer.run()


if __name__ == "__main__":
    main()
