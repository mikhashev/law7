#!/usr/bin/env python3
"""
Ministry of Finance Portal Analysis Script.

This script analyzes the Ministry of Finance portal (minfin.gov.ru) to understand
its structure, API availability, and document listing patterns.

Usage:
    poetry run python scripts/analysis/analyze_minfin.py
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


class MinfinAnalyzer:
    """Analyze Ministry of Finance portal structure."""

    BASE_URL = "https://minfin.gov.ru"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.findings = {
            "portal": "Ministry of Finance (minfin.gov.ru)",
            "timestamp": datetime.now().isoformat(),
            "api_endpoints": [],
            "html_structure": {},
            "document_patterns": {},
            "filters": {},
            "errors": []
        }

    def analyze_documents_page(self):
        """Analyze the main documents page."""
        logger.info("Analyzing documents page...")

        url = f"{self.BASE_URL}/ru/document/"
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
                        r'["\']https?://[^"\']*(?:api|ajax|json|documents)["\']',
                        script.string
                    )
                    for pattern in api_patterns:
                        if pattern not in self.findings["api_endpoints"]:
                            self.findings["api_endpoints"].append(pattern)

            # Find filter section
            filters = soup.find_all(["select", "input"], attrs={"name": re.compile(r"filter|sort|type")})
            if filters:
                self.findings["filters"]["found"] = True
                self.findings["filters"]["count"] = len(filters)
                self.findings["filters"]["types"] = [f.get("name") for f in filters if f.get("name")]

            # Find document cards
            doc_cards = soup.find_all("div", class_=re.compile(r"doc|card|item"))
            if doc_cards:
                self.findings["document_patterns"]["card_selector"] = doc_cards[0].get("class")
                self.findings["document_patterns"]["count_on_page"] = len(doc_cards)

                # Analyze document card structure
                if doc_cards:
                    card = doc_cards[0]
                    link = card.find("a", href=True)
                    if link:
                        self.findings["document_patterns"]["detail_link_pattern"] = link.get("href")

                    # Look for metadata
                    date_elem = card.find(string=re.compile(r"\d{2}\.\d{2}\.\d{4}"))
                    if date_elem:
                        self.findings["document_patterns"]["date_found"] = True

                    number_elem = card.find(string=re.compile(r"\d{2}-\d{2}-\d{2}/\d+"))
                    if number_elem:
                        self.findings["document_patterns"]["number_format"] = "XX-XX-XX/XXXXX"

        except Exception as e:
            error_msg = f"Error analyzing documents page: {e}"
            logger.error(error_msg)
            self.findings["errors"].append(error_msg)

    def analyze_filters(self):
        """Analyze filter functionality."""
        logger.info("Analyzing filters...")

        # Try to detect filter types
        known_filters = {
            "document_type": ["Письмо Минфина России", "Приказ", "Распоряжение"],
            "topic": ["Налоговая политика", "Бюджет", "Бухгалтерский учет"],
            "date_range": ["startDate", "endDate", "date"]
        }

        self.findings["filters"]["known_types"] = known_filters

    def check_api_endpoints(self):
        """Check for common API endpoints."""
        logger.info("Checking for API endpoints...")

        common_api_paths = [
            "/api/documents",
            "/ru/api/document",
            "/document/api",
            "/ajax/get-documents",
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
        print("MINISTRY OF FINANCE PORTAL ANALYSIS FINDINGS")
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
        print("FILTERS")
        print("-"*70)
        if self.findings.get("filters"):
            for key, value in self.findings["filters"].items():
                print(f"  {key}: {value}")

        print("\n" + "-"*70)
        print("DOCUMENT PATTERNS")
        print("-"*70)
        for key, value in self.findings["document_patterns"].items():
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

        output_file = Path(__file__).parent / "results" / "minfin_analysis.json"
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.findings, f, indent=2, ensure_ascii=False)

        logger.info(f"Findings saved to {output_file}")

    def run(self):
        """Run complete analysis."""
        logger.info("Starting Ministry of Finance portal analysis...")

        self.check_api_endpoints()
        self.analyze_documents_page()
        self.analyze_filters()

        self.print_findings()
        self.save_findings()


def main():
    """Main entry point."""
    analyzer = MinfinAnalyzer()
    analyzer.run()


if __name__ == "__main__":
    main()
