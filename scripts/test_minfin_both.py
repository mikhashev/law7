import asyncio
from scripts.country_modules.russia.scrapers.ministry_scraper import MinistryScraper

async def test():
    scraper = MinistryScraper('minfin')

    # Test with limit to verify both sources work
    manifest = await scraper.fetch_manifest(limit=100)

    with open('test_minfin_both.txt', 'w', encoding='utf-8') as f:
        f.write(f'Agency: {manifest["agency_name_short"]}\n')
        f.write(f'Letters found: {len(manifest["letters"])}\n')
        f.write(f'Total available (metadata): {manifest.get("metadata", {}).get("total_found", 0)}\n')
        f.write(f'Sources: {manifest.get("metadata", {}).get("sources", [])}\n\n')

        # Count by source
        by_source = {}
        for letter in manifest['letters']:
            source = letter.get('source', 'unknown')
            by_source[source] = by_source.get(source, 0) + 1

        f.write('Letters by source:\n')
        for source, count in by_source.items():
            f.write(f'  {source}: {count}\n')

        f.write('\nSample letters (first 10):\n')
        for i, letter in enumerate(manifest['letters'][:10]):
            source = letter.get('source', 'unknown')
            topic = letter.get('topic', '')
            f.write(f'  [{i+1}] [{source}] {topic} - {letter.get("title", "No title")[:80]}\n')

    await scraper.close()
    print(f"Test complete. Found {len(manifest['letters'])} letters.")

if __name__ == '__main__':
    asyncio.run(test())
