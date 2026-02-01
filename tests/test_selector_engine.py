"""Tests for multiple selector strategies."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.crawler.selector_engine import (
    FieldSelector,
    SelectorEngine,
    SelectorStrategy,
    SelectorType,
)


class TestSelectorEngine(unittest.TestCase):
    """Test the selector engine with multiple strategies."""

    def setUp(self):
        """Set up test fixtures."""
        self.html = """
        <html>
            <body>
                <div class="gs_r gs_or gs_scl">
                    <h3 class="gs_rt">
                        <a href="http://example.com/paper1">Test Paper 1</a>
                    </h3>
                    <div class="gs_a">Author A, Author B - 2024 - Journal X</div>
                </div>
                <div class="gs_r">
                    <h3 class="gs_rt">
                        <a href="http://example.com/paper2">Test Paper 2</a>
                    </h3>
                    <div class="gs_a">Author C - 2023 - Journal Y</div>
                </div>
            </body>
        </html>
        """
        self.soup = BeautifulSoup(self.html, "html.parser")

    def test_find_element_with_primary_strategy(self):
        """Test finding element with primary CSS strategy."""
        field_selector = FieldSelector(
            field_name="test_field",
            strategies=[
                SelectorStrategy(
                    selector="div.gs_r.gs_or.gs_scl",
                    selector_type=SelectorType.CSS,
                    priority=100,
                ),
            ],
        )

        engine = SelectorEngine(self.soup)
        element = engine.find_element(field_selector)

        self.assertIsNotNone(element)
        classes = element.get("class", [])
        if isinstance(classes, str):
            self.assertIn("gs_r", classes)
        else:
            self.assertIn("gs_r", classes)
            self.assertIn("gs_or", classes)
            self.assertIn("gs_scl", classes)

    def test_find_element_with_fallback_strategy(self):
        """Test finding element with fallback strategy."""
        field_selector = FieldSelector(
            field_name="test_field",
            strategies=[
                SelectorStrategy(
                    selector="div.nonexistent",
                    selector_type=SelectorType.CSS,
                    priority=100,
                ),
                SelectorStrategy(
                    selector="div.gs_r",
                    selector_type=SelectorType.CSS,
                    priority=50,
                ),
            ],
        )

        engine = SelectorEngine(self.soup)
        elements = engine.find_elements(field_selector)

        self.assertEqual(len(elements), 2)

    def test_find_elements_with_multiple_strategies(self):
        """Test finding multiple elements."""
        field_selector = FieldSelector(
            field_name="results",
            strategies=[
                SelectorStrategy(
                    selector="div.gs_r.gs_or.gs_scl",
                    selector_type=SelectorType.CSS,
                    priority=100,
                ),
                SelectorStrategy(
                    selector="div.gs_r",
                    selector_type=SelectorType.CSS,
                    priority=50,
                ),
            ],
        )

        engine = SelectorEngine(self.soup)
        elements = engine.find_elements(field_selector)

        self.assertGreaterEqual(len(elements), 1)

    def test_priority_ordering(self):
        """Test that higher priority strategies are tried first."""
        field_selector = FieldSelector(
            field_name="test_field",
            strategies=[
                SelectorStrategy(
                    selector="div.gs_r",
                    selector_type=SelectorType.CSS,
                    priority=50,
                ),
                SelectorStrategy(
                    selector="div.gs_r.gs_or.gs_scl",
                    selector_type=SelectorType.CSS,
                    priority=100,
                ),
            ],
        )

        engine = SelectorEngine(self.soup)
        element = engine.find_element(field_selector)

        self.assertIsNotNone(element)
        classes = element.get("class", [])
        if isinstance(classes, str):
            self.assertIn("gs_r", classes)
        else:
            self.assertIn("gs_r", classes)
            self.assertIn("gs_or", classes)
            self.assertIn("gs_scl", classes)

    def test_successful_selector_tracking(self):
        """Test tracking of successful selectors."""
        field_selector = FieldSelector(
            field_name="test_field",
            strategies=[
                SelectorStrategy(
                    selector="div.gs_r",
                    selector_type=SelectorType.CSS,
                    priority=100,
                ),
            ],
        )

        engine = SelectorEngine(self.soup)
        engine.find_elements(field_selector)

        successful = engine.get_successful_selectors()
        self.assertIn("test_field:css", successful)
        self.assertEqual(successful["test_field:css"], "div.gs_r")

    def test_required_field_not_found(self):
        """Test that required fields return None when not found."""
        field_selector = FieldSelector(
            field_name="nonexistent",
            strategies=[
                SelectorStrategy(
                    selector="div.nonexistent",
                    selector_type=SelectorType.CSS,
                    priority=100,
                ),
            ],
            required=True,
        )

        engine = SelectorEngine(self.soup)
        element = engine.find_element(field_selector)

        self.assertIsNone(element)

    def test_optional_field_not_found(self):
        """Test that optional fields return None when not found."""
        field_selector = FieldSelector(
            field_name="nonexistent",
            strategies=[
                SelectorStrategy(
                    selector="div.nonexistent",
                    selector_type=SelectorType.CSS,
                    priority=100,
                ),
            ],
            required=False,
        )

        engine = SelectorEngine(self.soup)
        element = engine.find_element(field_selector)

        self.assertIsNone(element)

    def test_xpath_selector(self):
        """Test XPath selector functionality."""
        field_selector = FieldSelector(
            field_name="test_field",
            strategies=[
                SelectorStrategy(
                    selector="//div[contains(@class, 'gs_r')]",
                    selector_type=SelectorType.XPATH,
                    priority=100,
                ),
            ],
        )

        engine = SelectorEngine(self.soup)
        elements = engine.find_elements(field_selector)

        self.assertEqual(len(elements), 2)


if __name__ == "__main__":
    unittest.main()
