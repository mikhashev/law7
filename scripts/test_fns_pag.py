import asyncio
from scripts.country_modules.russia.scrapers.ministry_scraper import MinistryScraper

async def test():
    scraper = MinistryScraper('fns')
    scraper.batch_size = 1000  # Allow more documents

    # Monkey-patch the sleep to reduce delay for testing
    original_sleep = asyncio.sleep
    async def quick_sleep(seconds):
        await original_sleep(1)  # Always sleep just 1 second

    # Patch sleep in the scraper module
    import sys
    ministry_module = sys.modules['scripts.country_modules.russia.scrapers.ministry_scraper']
    ministry_module.asyncio.sleep = quick_sleep

    try:
        manifest = await scraper.fetch_manifest()

        with open('test_fns_pag.txt', 'w', encoding='utf-8') as f:
            f.write(f'Agency: {manifest["agency_name_short"]}\n')
            f.write(f'Letters found: {len(manifest["letters"])}\n')
            f.write(f'Total available (metadata): {manifest.get("metadata", {}).get("total_found", 0)}\n')
            f.write(f'Filter actual only: {manifest.get("metadata", {}).get("filter_actual_only", False)}\n\n')

            if manifest['letters']:
                f.write('Sample letters (first 5):\n')
                for i, letter in enumerate(manifest['letters'][:5]):
                    f.write(f'  [{i+1}] {letter.get("document_number")} - {letter.get("title", "No title")[:80]}\n')
    finally:
        await scraper.close()

    print(f"Test complete. Found {len(manifest['letters'])} letters.")

if __name__ == '__main__':
    asyncio.run(test())
