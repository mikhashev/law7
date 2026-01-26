#!/usr/bin/env python
"""Test imports for Phase 7A - Issue #14"""
import sys
sys.path.insert(0, 'scripts')

print("Testing Phase 7A Module Structure...")
print("-" * 50)

# Test base classes
from country_modules.base.scraper import BaseScraper, RawDocument
from country_modules.base.parser import BaseParser
from country_modules.base.sync import DocumentSync, DocumentManifest
from country_modules import __version__

print("✅ Base Classes")
print(f"  BaseScraper: {BaseScraper}")
print(f"  BaseParser: {BaseParser}")
print(f"  DocumentSync: {DocumentSync}")
print(f"  RawDocument: {RawDocument}")
print(f"  DocumentManifest: {DocumentManifest}")

# Test module structure
import country_modules
import country_modules.base
import country_modules.russia
import country_modules.russia.scrapers
import country_modules.russia.parsers
import country_modules.russia.consolidation
import country_modules.russia.sync

print("")
print("✅ Module Structure")
print(f"  country_modules: v{__version__}")
print(f"  country_modules.base: imported")
print(f"  country_modules.russia: imported")
print(f"  country_modules.russia.scrapers: imported")
print(f"  country_modules.russia.parsers: imported")
print(f"  country_modules.russia.consolidation: imported")
print(f"  country_modules.russia.sync: imported")

print("")
print("-" * 50)
print("✅ All imports successful - Issue #14 complete!")
