import asyncio
from scripts.country_modules.russia.scrapers.ministry_scraper import MinistryScraper

async def test():
    scraper = MinistryScraper('fns')

    # Test with limit=50 to verify limit parameter works
    manifest = await scraper.fetch_manifest(limit=50)

    with open('test_fns_no_limit.txt', 'w', encoding='utf-8') as f:
        f.write(f'Agency: {manifest["agency_name_short"]}\n')
        f.write(f'Letters found: {len(manifest["letters"])}\n')
        f.write(f'Total available (metadata): {manifest.get("metadata", {}).get("total_found", 0)}\n')
        f.write(f'Filter actual only: {manifest.get("metadata", {}).get("filter_actual_only", False)}\n')
        f.write(f'Since date: {manifest.get("metadata", {}).get("since", "None (all dates)")}\n\n')

        if manifest['letters']:
            f.write('Sample letters (first 5):\n')
            for i, letter in enumerate(manifest['letters'][:5]):
                f.write(f'  [{i+1}] {letter.get("document_number")} - {letter.get("title", "No title")[:80]}\n')

    await scraper.close()
    print(f"Test complete. Found {len(manifest['letters'])} letters (limited to 50).")

if __name__ == '__main__':
    asyncio.run(test())
