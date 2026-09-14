"""Test date parsing with Russian titles."""
import re
from datetime import date

def parse_date_from_title(title: str) -> date:
    """Extract decision date from Russian document title."""
    months_genitive = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
    }

    pattern = r'от\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s+(года|го)'
    match = re.search(pattern, title)
    if match:
        day = int(match.group(1))
        year = int(match.group(3))
        month_name = match.group(2).lower()

        for full_name, month_num in months_genitive.items():
            if month_name == full_name or month_name in full_name:
                try:
                    return date(year, month_num, day)
                except ValueError:
                    return None

    return None

# Test cases
test_cases = [
    ('Постановление Пленума Верховного Суда Российской Федерации от 27 января 2026 года', date(2026, 1, 27)),
    ('Постановление Пленума Верховного Суда Российской Федерации от 23 декабря 2025 го', date(2025, 12, 23)),
    ('Постановление Пленума Верховного Суда Российской Федерации от 24 июня 2025 года', date(2025, 6, 24)),
    ('Постановление Пленума Верховного Суда Российской Федерации от 16 мая 2017 года №', date(2017, 5, 16)),
    ('Постановление Пленума Верховного Суда Российской Федерации от 28 октября 2015 года', date(2015, 10, 28)),
]

print('Testing date parsing from titles:')
passed = 0
failed = 0

for title, expected in test_cases:
    result = parse_date_from_title(title)
    status = 'PASS' if result == expected else 'FAIL'
    if status == 'PASS':
        passed += 1
    else:
        failed += 1
    print(f'{status}: {result} (expected {expected}) - {title[:70]}')

print(f'\nResults: {passed}/{len(test_cases)} tests passed')
