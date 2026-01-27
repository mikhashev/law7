#!/usr/bin/env python3
"""
Supreme Court Portal Analysis Script.

This script analyzes the Supreme Court portal (vsrf.gov.ru) to understand
its structure, API availability, and document listing patterns.

Usage:
    poetry run python scripts/analysis/analyze_supreme_court.py
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


class SupremeCourtAnalyzer:
    """Analyze Supreme Court portal structure."""

    BASE_URL = "https://vsrf.gov.ru"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.findings = {
            "portal": "Supreme Court (vsrf.gov.ru)",
            "timestamp": datetime.now().isoformat(),
            "api_endpoints": [],
            "html_structure": {},
            "document_patterns": {},
            "pagination": {},
            "errors": []
        }

    def analyze_main_page(self):
        """Analyze the main documents page."""
        logger.info("Analyzing main documents page...")

        urls = [
            f"{self.BASE_URL}/documents/own/",  # Plenary resolutions
            f"{self.BASE_URL}/documents/practice/",  # Practice reviews
        ]

        for url in urls:
            try:
                logger.info(f"Fetching {url}...")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()

                # Analyze HTML structure
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

                # Find document links
                doc_links = soup.find_all("a", href=re.compile(r"/documents/\d+"))
                if doc_links:
                    self.findings["document_patterns"]["link_pattern"] = doc_links[0].get("href")
                    self.findings["document_patterns"]["count_on_page"] = len(doc_links)

                # Look for pagination
                pagination = soup.find_all("a", href=re.compile(r"page"))
                if pagination:
                    self.findings["pagination"]["found"] = True
                    self.findings["pagination"]["selector"] = "a[href*='page']"

                # Analyze main content container
                content_div = soup.find("div", class_=re.compile(r"content|documents|items"))
                if content_div:
                    self.findings["html_structure"]["main_container"] = content_div.get("class")

            except Exception as e:
                error_msg = f"Error analyzing {url}: {e}"
                logger.error(error_msg)
                self.findings["errors"].append(error_msg)

    def analyze_document_page(self):
        """Analyze a specific document detail page."""
        logger.info("Analyzing document detail page...")

        # Try to find a document ID from the main page
        try:
            response = self.session.get(f"{self.BASE_URL}/documents/own/", timeout=30)
            soup = BeautifulSoup(response.text, "html.parser")

            # Find first document link
            doc_link = soup.find("a", href=re.compile(r"/documents/own/\d+"))
            if doc_link:
                doc_url = f"{self.BASE_URL}{doc_link.get('href')}"
                logger.info(f"Fetching document detail: {doc_url}")

                response = self.session.get(doc_url, timeout=30)
                soup = BeautifulSoup(response.text, "html.parser")

                # Analyze document structure
                title = soup.find("h1")
                if title:
                    self.findings["html_structure"]["title_selector"] = "h1"

                # Look for PDF download link
                pdf_link = soup.find("a", href=re.compile(r"\.pdf"))
                if pdf_link:
                    self.findings["document_patterns"]["pdf_link_pattern"] = pdf_link.get("href")

                # Look for document content
                content = soup.find("div", class_=re.compile(r"content|text|document"))
                if content:
                    self.findings["html_structure"]["content_selector"] = content.get("class")

        except Exception as e:
            error_msg = f"Error analyzing document page: {e}"
            logger.error(error_msg)
            self.findings["errors"].append(error_msg)

    def check_api_endpoints(self):
        """Check for common API endpoints."""
        logger.info("Checking for API endpoints...")

        common_api_paths = [
            "/api/documents",
            "/api/v1/documents",
            "/api/v2/documents",
            "/json/documents",
            "/ajax/documents",
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
        print("SUPREME COURT PORTAL ANALYSIS FINDINGS")
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
        print("HTML STRUCTURE")
        print("-"*70)
        for key, value in self.findings["html_structure"].items():
            print(f"  {key}: {value}")

        print("\n" + "-"*70)
        print("DOCUMENT PATTERNS")
        print("-"*70)
        for key, value in self.findings["document_patterns"].items():
            print(f"  {key}: {value}")

        print("\n" + "-"*70)
        print("PAGINATION")
        print("-"*70)
        if self.findings["pagination"]:
            for key, value in self.findings["pagination"].items():
                print(f"  {key}: {value}")
        else:
            print("  No pagination found")

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

        output_file = Path(__file__).parent / "results" / "supreme_court_analysis.json"
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.findings, f, indent=2, ensure_ascii=False)

        logger.info(f"Findings saved to {output_file}")

    def run(self):
        """Run complete analysis."""
        logger.info("Starting Supreme Court portal analysis...")

        self.check_api_endpoints()
        self.analyze_main_page()
        self.analyze_document_page()

        self.print_findings()
        self.save_findings()


def main():
    """Main entry point."""
    analyzer = SupremeCourtAnalyzer()
    analyzer.run()


if __name__ == "__main__":
    main()
