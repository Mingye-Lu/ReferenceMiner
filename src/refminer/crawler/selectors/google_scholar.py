"""Google Scholar selector configurations."""

from __future__ import annotations

from refminer.crawler.selector_engine import (
    FieldSelector,
    SelectorEngine,
    SelectorStrategy,
    SelectorType,
)


class GoogleScholarSelectors:
    """Google Scholar selector configurations."""
    
    RESULT_CONTAINER = FieldSelector(
        field_name="result_container",
        strategies=[
            SelectorStrategy(
                selector="div.gs_r.gs_or.gs_scl",
                selector_type=SelectorType.CSS,
                priority=100,
                description="Standard Google Scholar result container",
            ),
            SelectorStrategy(
                selector="div.gs_r",
                selector_type=SelectorType.CSS,
                priority=50,
                description="Minimal result container class",
            ),
            SelectorStrategy(
                selector="//div[contains(@class, 'gs_r')]",
                selector_type=SelectorType.XPATH,
                priority=40,
                description="XPath fallback for result container",
            ),
            SelectorStrategy(
                selector="div[data-cid]",
                selector_type=SelectorType.CSS,
                priority=30,
                description="Result container by data attribute",
            ),
        ],
        required=True,
    )
    
    TITLE = FieldSelector(
        field_name="title",
        strategies=[
            SelectorStrategy(
                selector="h3.gs_rt",
                selector_type=SelectorType.CSS,
                priority=100,
                description="Standard title container",
            ),
            SelectorStrategy(
                selector="h3.gs_rt a",
                selector_type=SelectorType.CSS,
                priority=90,
                description="Direct title link",
            ),
            SelectorStrategy(
                selector=".gs_rt",
                selector_type=SelectorType.CSS,
                priority=50,
                description="Minimal title class",
            ),
            SelectorStrategy(
                selector="//h3[contains(@class, 'gs_rt')]",
                selector_type=SelectorType.XPATH,
                priority=40,
                description="XPath fallback for title",
            ),
        ],
        required=True,
    )
    
    TITLE_LINK = FieldSelector(
        field_name="title_link",
        strategies=[
            SelectorStrategy(
                selector="a",
                selector_type=SelectorType.CSS,
                priority=100,
                description="Link within title container",
            ),
            SelectorStrategy(
                selector="a[href]",
                selector_type=SelectorType.CSS,
                priority=90,
                description="Link with href attribute",
            ),
            SelectorStrategy(
                selector="//a[contains(@href, 'http')]",
                selector_type=SelectorType.XPATH,
                priority=50,
                description="XPath for external links",
            ),
        ],
        required=False,
    )
    
    AUTHORS_YEAR_JOURNAL = FieldSelector(
        field_name="authors_year_journal",
        strategies=[
            SelectorStrategy(
                selector="div.gs.gs_a",
                selector_type=SelectorType.CSS,
                priority=100,
                description="Standard metadata container",
            ),
            SelectorStrategy(
                selector="div.gs_a",
                selector_type=SelectorType.CSS,
                priority=90,
                description="Minimal metadata class",
            ),
            SelectorStrategy(
                selector=".gs_a",
                selector_type=SelectorType.CSS,
                priority=50,
                description="Short metadata class",
            ),
            SelectorStrategy(
                selector="//div[contains(@class, 'gs_a')]",
                selector_type=SelectorType.XPATH,
                priority=40,
                description="XPath fallback for metadata",
            ),
        ],
        required=False,
    )
    
    PDF_LINK = FieldSelector(
        field_name="pdf_link",
        strategies=[
            SelectorStrategy(
                selector="a[href$='.pdf']",
                selector_type=SelectorType.CSS,
                priority=100,
                description="Direct PDF link",
            ),
            SelectorStrategy(
                selector="a[href*='pdf']",
                selector_type=SelectorType.CSS,
                priority=80,
                description="Link containing 'pdf'",
            ),
            SelectorStrategy(
                selector="//a[contains(@href, '.pdf')]",
                selector_type=SelectorType.XPATH,
                priority=60,
                description="XPath for PDF links",
            ),
        ],
        required=False,
    )
