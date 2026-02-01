"""Multiple selector strategy system for robust HTML parsing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class SelectorType(Enum):
    """Type of selector."""

    CSS = "css"
    XPATH = "xpath"


@dataclass
class SelectorStrategy:
    """A single selector strategy."""

    selector: str
    selector_type: SelectorType
    priority: int = 0
    description: str = ""

    def __post_init__(self):
        if isinstance(self.selector_type, str):
            self.selector_type = SelectorType(self.selector_type)


@dataclass
class FieldSelector:
    """Multiple selector strategies for a field."""

    field_name: str
    strategies: list[SelectorStrategy]
    required: bool = True
    transform: Optional[Callable[[Any], Any]] = None


class SelectorEngine:
    """Engine for trying multiple selector strategies."""

    def __init__(self, soup: BeautifulSoup) -> None:
        self.soup = soup
        self._successful_selectors: dict[str, str] = {}

    def find_element(
        self,
        field_selector: FieldSelector,
        parent: Optional[Tag] = None,
    ) -> Optional[Tag]:
        """Find element using multiple selector strategies."""
        search_context = parent or self.soup

        for strategy in sorted(
            field_selector.strategies,
            key=lambda s: s.priority,
            reverse=True,
        ):
            try:
                element = self._try_selector(search_context, strategy)
                if element:
                    self._track_success(field_selector.field_name, strategy)
                    logger.debug(
                        f"[SelectorEngine] Found {field_selector.field_name} "
                        f"using {strategy.selector_type.value}: {strategy.selector}"
                    )
                    return element
            except Exception as e:
                logger.debug(
                    f"[SelectorEngine] Strategy failed for {field_selector.field_name}: "
                    f"{strategy.selector} - {e}"
                )
                continue

        if field_selector.required:
            logger.warning(
                f"[SelectorEngine] No strategy worked for {field_selector.field_name}"
            )
        return None

    def find_elements(
        self,
        field_selector: FieldSelector,
        parent: Optional[Tag] = None,
    ) -> list[Tag]:
        """Find all elements using multiple selector strategies."""
        search_context = parent or self.soup

        for strategy in sorted(
            field_selector.strategies,
            key=lambda s: s.priority,
            reverse=True,
        ):
            try:
                elements = self._try_selector_all(search_context, strategy)
                if elements:
                    self._track_success(field_selector.field_name, strategy)
                    logger.debug(
                        f"[SelectorEngine] Found {len(elements)} {field_selector.field_name} "
                        f"using {strategy.selector_type.value}: {strategy.selector}"
                    )
                    return elements
            except Exception as e:
                logger.debug(
                    f"[SelectorEngine] Strategy failed for {field_selector.field_name}: "
                    f"{strategy.selector} - {e}"
                )
                continue

        if field_selector.required:
            logger.warning(
                f"[SelectorEngine] No strategy worked for {field_selector.field_name}"
            )
        return []

    def _try_selector(self, context: Tag, strategy: SelectorStrategy) -> Optional[Tag]:
        """Try a single selector strategy."""
        if strategy.selector_type == SelectorType.CSS:
            return context.select_one(strategy.selector)
        elif strategy.selector_type == SelectorType.XPATH:
            return self._xpath_select_one(context, strategy.selector)
        return None

    def _try_selector_all(self, context: Tag, strategy: SelectorStrategy) -> list[Tag]:
        """Try a single selector strategy for multiple elements."""
        if strategy.selector_type == SelectorType.CSS:
            return context.select(strategy.selector)
        elif strategy.selector_type == SelectorType.XPATH:
            return self._xpath_select_all(context, strategy.selector)
        return []

    def _xpath_select_one(self, context: Tag, xpath: str) -> Optional[Tag]:
        """Select single element using XPath."""
        try:
            from lxml import etree

            dom = etree.HTML(str(context))
            result = dom.xpath(xpath)
            return result[0] if result else None
        except ImportError:
            logger.warning("[SelectorEngine] lxml not installed, XPath not available")
            return None

    def _xpath_select_all(self, context: Tag, xpath: str) -> list[Tag]:
        """Select all elements using XPath."""
        try:
            from lxml import etree

            dom = etree.HTML(str(context))
            return dom.xpath(xpath)
        except ImportError:
            logger.warning("[SelectorEngine] lxml not installed, XPath not available")
            return []

    def _track_success(self, field_name: str, strategy: SelectorStrategy) -> None:
        """Track successful selector for telemetry."""
        key = f"{field_name}:{strategy.selector_type.value}"
        self._successful_selectors[key] = strategy.selector

    def get_successful_selectors(self) -> dict[str, str]:
        """Get mapping of successful selectors."""
        return self._successful_selectors.copy()
