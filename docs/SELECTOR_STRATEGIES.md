# Multiple Selector Strategies Implementation

## Overview

This implementation adds robust multiple selector strategies to the ReferenceMiner crawler, making it more resilient to website structure changes and anti-scraping measures.

## Files Created/Modified

### New Files

1. **`src/refminer/crawler/selector_engine.py`**
   - Core selector engine with multiple strategy support
   - Classes: `SelectorType`, `SelectorStrategy`, `FieldSelector`, `SelectorEngine`
   - Features:
     - CSS and XPath selector support
     - Priority-based strategy ordering
     - Successful selector tracking
     - Graceful fallback handling

2. **`src/refminer/crawler/selectors/__init__.py`**
   - Package initialization for selector configurations

3. **`src/refminer/crawler/selectors/google_scholar.py`**
   - Google Scholar-specific selector configurations
   - Multiple fallback strategies for each field:
     - Result containers (4 strategies)
     - Titles (4 strategies)
     - Title links (3 strategies)
     - Authors/year/journal (4 strategies)
     - PDF links (3 strategies)

4. **`tests/test_selector_engine.py`**
   - Comprehensive unit tests for selector engine
   - 8 test cases covering all major functionality

### Modified Files

1. **`src/refminer/crawler/engines/google_scholar.py`**
   - Updated to use `SelectorEngine`
   - Now uses multiple selector strategies instead of single selectors
   - Tracks successful selectors for observability

2. **`src/refminer/crawler/downloader.py`**
   - Updated `_extract_pdf_from_html()` to use selector engine
   - Added multiple PDF link selector strategies
   - Added multiple citation meta tag strategies

## Key Features

### 1. Multiple Selector Strategies

Each field can have multiple selector strategies with different priorities:

```python
FieldSelector(
    field_name="title",
    strategies=[
        SelectorStrategy(
            selector="h3.gs_rt",
            selector_type=SelectorType.CSS,
            priority=100,  # Try first
        ),
        SelectorStrategy(
            selector=".gs_rt",
            selector_type=SelectorType.CSS,
            priority=50,  # Fallback
        ),
        SelectorStrategy(
            selector="//h3[contains(@class, 'gs_rt')]",
            selector_type=SelectorType.XPATH,
            priority=40,  # Last resort
        ),
    ],
)
```

### 2. Priority-Based Ordering

Strategies are tried in priority order (highest first). If a strategy fails, the next one is tried automatically.

### 3. Selector Type Support

- **CSS Selectors**: Standard BeautifulSoup CSS selectors
- **XPath Selectors**: XPath expressions via lxml (optional dependency)

### 4. Successful Selector Tracking

The engine tracks which selectors work successfully:

```python
engine = SelectorEngine(soup)
results = engine.find_elements(field_selector)
successful = engine.get_successful_selectors()
# Returns: {"field_name:css": "div.gs_r", ...}
```

### 5. Graceful Error Handling

- Failed strategies are logged at DEBUG level
- Missing required fields are logged at WARNING level
- Optional fields return None without warnings

## Benefits

1. **Resilience**: Single selector changes won't break the crawler
2. **Maintainability**: Easy to add new strategies without changing core logic
3. **Observability**: Track which selectors work for monitoring
4. **Flexibility**: Supports both CSS and XPath selectors
5. **Backward Compatible**: Existing code continues to work
6. **Extensible**: Easy to add selector configs for other engines

## Testing

Run the test suite:

```bash
uv run python -m unittest tests.test_selector_engine -v
```

All 8 tests pass:

- `test_find_element_with_primary_strategy`
- `test_find_element_with_fallback_strategy`
- `test_find_elements_with_multiple_strategies`
- `test_priority_ordering`
- `test_successful_selector_tracking`
- `test_required_field_not_found`
- `test_optional_field_not_found`
- `test_xpath_selector`

## Usage Example

```python
from bs4 import BeautifulSoup
from refminer.crawler.selector_engine import SelectorEngine
from refminer.crawler.selectors.google_scholar import GoogleScholarSelectors

html = """<html>...</html>"""
soup = BeautifulSoup(html, "html.parser")

engine = SelectorEngine(soup)

# Find result containers
results = engine.find_elements(GoogleScholarSelectors.RESULT_CONTAINER)

# Check which selectors worked
successful = engine.get_successful_selectors()
print(f"Successful selectors: {successful}")
```

## Dependencies

- `beautifulsoup4>=4.12.0` (already in requirements.txt)
- `lxml>=4.9.0` (already in requirements.txt, optional for XPath)

## Future Enhancements

1. **Add selector configs for other engines**:
   - PubMed selectors
   - Semantic Scholar selectors
   - arXiv selectors

2. **ML-based selector discovery**:
   - Automatically learn selectors from HTML structure
   - Detect when selectors fail and suggest alternatives

3. **Selector performance tracking**:
   - Track success rates per selector
   - Dynamically adjust priorities based on success rates

4. **Selector versioning**:
   - Version selectors by website layout
   - Auto-detect website version and use appropriate selectors

5. **Selector caching**:
   - Cache successful selectors per domain
   - Reduce selector trial overhead

## Migration Notes

No migration needed! The implementation is backward compatible. Existing code continues to work, and the new selector system is automatically used where implemented.

## Performance Impact

- **Minimal overhead**: Only when selectors fail
- **First strategy success**: No performance penalty
- **Fallback scenarios**: Slight delay for trying additional selectors
- **XPath selectors**: Slightly slower than CSS, but only used as fallbacks

## Security Considerations

- **No injection vulnerabilities**: Selectors are hardcoded, not user-provided
- **Rate limiting**: Handled by existing rate limiter in BaseCrawler
- **Anti-detection**: Still uses existing User-Agent and rate limiting

## License

Same as ReferenceMiner project.
