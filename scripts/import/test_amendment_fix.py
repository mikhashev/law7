"""
Test script for amendment pattern filtering fix.

Tests that subsection titles with amendment notes are filtered
regardless of their paragraph number.

This verifies the fix for Issue 1 in ARTICLE_PARSING_ISSUES.md
"""
import re


def debug_pattern_matching():
    """Debug pattern matching to see what's happening."""
    pattern = r'\(.*(?:дополнение|редакция|редакции|утратил|Наименование|Дополнение).+\)'

    print('DEBUG: Pattern matching')
    print('='*60)
    print(f'Pattern: {pattern}')
    print()

    # Test the failing cases
    test_cases = [
        '2. Казачьи общества (утратил силу)',
        '3. Объединения (редакция от 01.01.2022)',
        '(утратил силу)',
        '(редакция от 01.01.2022)',
    ]

    for text in test_cases:
        match = re.search(pattern, text, re.IGNORECASE)
        print(f'Text: {text}')
        print(f'Match: {match}')
        if match:
            print(f'Matched: "{match.group()}"')
        print()

    print('='*60)
    print()


def test_amendment_pattern():
    """Test that amendment pattern correctly identifies subsection titles."""
    pattern = r'\(.*(?:дополнение|редакция|редакции|утратил|Наименование|Дополнение).+\)'

    # Test cases: (text, should_match)
    test_cases = [
        # Case 1: Lower number after higher numbers (should be filtered)
        ('1. Общественно полезные фонды (Наименование в редакции Федерального закона от 01.07.2021 № 287-ФЗ)', True),
        # Case 2: Same number as previous (should be filtered)
        ('4. Общественно полезные фонды (Наименование в редакции Федерального закона от 01.07.2021 № 287-ФЗ)', True),
        # Case 3: Next expected number (should be filtered)
        ('5. Общественно полезные фонды (Наименование в редакции Федерального закона от 01.07.2021 № 287-ФЗ)', True),
        # Additional amendment patterns
        ('1. Некоммерческие партнерства (Дополнение - Федеральный закон от 05.05.2014 № 99-ФЗ)', True),
        ('2. Казачьи общества (утратил силу)', True),
        ('3. Объединения (редакция от 01.01.2022)', True),
        # Normal paragraphs should NOT match
        ('1. First paragraph (normal text without amendment keywords)', False),
        ('1. Ordinary paragraph text', False),
        ('2. Another paragraph', False),
        ('1. K исключительной компетенции относятся:', False),
        ('4. В товариществе собственников недвижимости создаются:', False),
    ]

    print('Testing amendment pattern filtering:')
    print('='*60)

    all_passed = True
    for text, expected in test_cases:
        match = re.search(pattern, text, re.IGNORECASE)
        result = match is not None
        status = 'PASS' if result == expected else 'FAIL'

        if result != expected:
            all_passed = False

        print(f'[{status}] {text[:65]}...')
        if not result == expected:
            print(f'       Expected: {expected}, Got: {result}')
        print()

    print('='*60)
    print(f'All tests passed: {all_passed}')
    return all_passed


def test_sequential_logic_with_amendment():
    """
    Test that amendment pattern is checked BEFORE sequential validation.

    This simulates the actual code flow in import_base_code.py.
    """
    print('\nTesting sequential validation WITH amendment check:')
    print('='*60)

    # Simulate expected_paragraph_num = 5 (after paragraphs 1, 2, 3, 4)
    expected_paragraph_num = 5

    # Test cases: (text, should_be_filtered)
    test_cases = [
        # All three cases should be FILTERED by amendment pattern
        ('1. Общественно полезные фонды (Наименование в редакции Федерального закона от 01.07.2021 № 287-ФЗ)', True),
        ('4. Общественно полезные фонды (Наименование в редакции Федерального закона от 01.07.2021 № 287-ФЗ)', True),
        ('5. Общественно полезные фонды (Наименование в редакции Федерального закона от 01.07.2021 № 287-ФЗ)', True),
        # Normal paragraph should be ACCEPTED
        ('5. Normal paragraph text without amendment', False),
    ]

    amendment_pattern = r'\(.*(?:дополнение|редакция|редакции|утратил|Наименование|Дополнение).+\)'

    all_passed = True
    for text, should_be_filtered in test_cases:
        # First check: Amendment pattern (takes precedence)
        amendment_match = re.search(amendment_pattern, text, re.IGNORECASE)

        if amendment_match:
            # Amendment pattern matched - should filter
            filtered = True
            reason = 'amendment_pattern'
        else:
            # No amendment pattern - would go to sequential validation
            # (not testing sequential validation here, just that amendment comes first)
            filtered = False
            reason = 'no_amendment'

        expected_filtered = should_be_filtered
        status = 'PASS' if filtered == expected_filtered else 'FAIL'

        if filtered != expected_filtered:
            all_passed = False

        action = 'FILTERED' if filtered else 'ACCEPTED'
        expected_action = 'FILTERED' if expected_filtered else 'ACCEPTED'

        print(f'[{status}] {text[:60]}...')
        print(f'       Got: {action} ({reason})')
        print(f'       Expected: {expected_action}')
        print()

    print('='*60)
    print(f'All tests passed: {all_passed}')
    return all_passed


if __name__ == '__main__':
    print('Issue 1 Fix Verification: Subsection Titles with Amendment Notes')
    print('='*60)
    print()

    # Debug pattern matching first
    debug_pattern_matching()

    test1_passed = test_amendment_pattern()
    test2_passed = test_sequential_logic_with_amendment()

    print('\n' + '='*60)
    print('FINAL RESULT:')
    if test1_passed and test2_passed:
        print('  All tests PASSED')
    else:
        print('  Some tests FAILED')
    print('='*60)
