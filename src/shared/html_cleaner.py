"""HTML cleaning utilities for web agents."""

import logging
from typing import List

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HTMLCleaner:
    """Clean HTML to keep only relevant content for web agents"""

    # Tags to completely remove (including their content)
    REMOVE_TAGS = {
        "script",
        "style",
        "noscript",
        "meta",
        "link",
        "svg",
        "path",
        "iframe",
        "embed",
        "object",
        "canvas",
        "video",
        "audio",
    }

    # Tags to remove but keep their content
    UNWRAP_TAGS = {"font", "center", "marquee", "blink"}

    # Interactive elements we definitely want to keep
    INTERACTIVE_TAGS = {
        "a",
        "button",
        "input",
        "select",
        "textarea",
        "option",
        "form",
        "label",
        "details",
        "summary",
    }

    # Attributes to keep (useful for identifying and interacting with elements)
    KEEP_ATTRIBUTES = {
        "id",
        "name",
        "type",
        "value",
        "placeholder",
        "href",
        "src",
        "alt",
        "title",
        "aria-label",
        "role",
        "for",
        "action",
        "method",
        "data-testid",
        "data-id",
        "class",
    }

    def __init__(
        self,
        remove_hidden: bool = True,
        remove_comments: bool = True,
        max_text_length: int = 200,
        keep_semantic_tags: bool = True,
    ):
        """
        Initialize HTML cleaner

        Args:
            remove_hidden: Remove elements with display:none or visibility:hidden
            remove_comments: Remove HTML comments
            max_text_length: Maximum text length to keep in a single element
            keep_semantic_tags: Keep semantic tags like header, nav, main, etc.
        """
        self.remove_hidden = remove_hidden
        self.remove_comments = remove_comments
        self.max_text_length = max_text_length
        self.keep_semantic_tags = keep_semantic_tags

    def clean(self, html: str) -> str:
        """
        Clean HTML and return simplified version

        Args:
            html: Raw HTML string

        Returns:
            Cleaned HTML string
        """
        if not html or not html.strip():
            return ""

        try:
            soup = BeautifulSoup(html, "html.parser")

            # 1. Remove unwanted tags
            self._remove_tags(soup)

            # 2. Remove comments
            if self.remove_comments:
                self._remove_comments(soup)

            # 3. Remove hidden elements
            if self.remove_hidden:
                self._remove_hidden_elements(soup)

            # 4. Clean attributes
            self._clean_attributes(soup)

            # 5. Simplify text
            self._simplify_text(soup)

            # 6. Remove empty elements
            self._remove_empty_elements(soup)

            # 7. Add element indices for identification
            # self._add_element_indices(soup)

            return str(soup)
        except Exception as e:
            print(f"Warning: Error cleaning HTML: {e}")
            return html  # Return original if cleaning fails

    def _remove_tags(self, soup: BeautifulSoup):
        """Remove unwanted tags"""
        # Collect tags first, then remove (avoid iterator issues)
        for tag_name in self.REMOVE_TAGS:
            tags_to_remove = soup.find_all(tag_name)
            for tag in tags_to_remove:
                if tag:  # Check if tag still exists
                    tag.decompose()

        # Unwrap tags (remove tag but keep content)
        for tag_name in self.UNWRAP_TAGS:
            tags_to_unwrap = soup.find_all(tag_name)
            for tag in tags_to_unwrap:
                if tag:
                    tag.unwrap()

    def _remove_comments(self, soup: BeautifulSoup):
        """Remove HTML comments"""
        from bs4 import Comment

        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if comment:
                comment.extract()

    def _remove_hidden_elements(self, soup: BeautifulSoup):
        """Remove elements that are hidden via style or attributes"""
        tags_to_remove = []

        # Find elements with display:none or visibility:hidden in style attribute
        for tag in soup.find_all(style=True):
            if not tag:  # Safety check
                continue

            style = tag.get("style")
            if style:
                style_lower = style.lower()
                if (
                    "display:none" in style_lower.replace(" ", "")
                    or "display: none" in style_lower
                    or "visibility:hidden" in style_lower.replace(" ", "")
                    or "visibility: hidden" in style_lower
                ):
                    tags_to_remove.append(tag)

        # Find elements with hidden attribute
        tags_to_remove.extend(soup.find_all(hidden=True))

        # Find elements with aria-hidden="true"
        tags_to_remove.extend(soup.find_all(attrs={"aria-hidden": "true"}))

        # Remove all collected tags
        for tag in tags_to_remove:
            if tag and tag.parent:  # Check tag still exists and has parent
                try:
                    tag.decompose()
                except:
                    pass  # Tag might have been removed already

    def _clean_attributes(self, soup: BeautifulSoup):
        """Remove unnecessary attributes"""
        for tag in soup.find_all(True):
            if not tag:
                continue

            try:
                # Get current attributes
                attrs = dict(tag.attrs)

                # Keep only allowed attributes
                for attr in list(attrs.keys()):
                    if attr not in self.KEEP_ATTRIBUTES:
                        del tag.attrs[attr]

                # Clean class attribute - keep only first class or remove if empty
                if "class" in tag.attrs:
                    classes = tag.attrs["class"]
                    if isinstance(classes, list) and classes:
                        tag.attrs["class"] = classes[0]
                    elif not classes:
                        del tag.attrs["class"]
            except:
                continue

    def _simplify_text(self, soup: BeautifulSoup):
        """Simplify and truncate text content"""
        for tag in soup.find_all(string=True):
            if not tag:
                continue

            try:
                text = tag.string
                if text:
                    # Remove extra whitespace
                    text = " ".join(text.split())

                    # Truncate long text
                    if len(text) > self.max_text_length:
                        text = text[: self.max_text_length] + "..."

                    if text:  # Only replace if not empty
                        tag.replace_with(text)
            except:
                continue

    def _remove_empty_elements(self, soup: BeautifulSoup):
        """Remove elements that are empty or contain only whitespace"""
        # Iterate multiple times as removing elements may create new empty parents
        for _ in range(3):
            tags_to_remove = []

            for tag in soup.find_all(True):
                if not tag:
                    continue

                # Don't remove interactive elements even if empty
                if tag.name in self.INTERACTIVE_TAGS:
                    continue

                # Don't remove elements with important attributes
                if any(attr in tag.attrs for attr in ["id", "name", "role"]):
                    continue

                # Check if empty
                text_content = tag.get_text(strip=True)
                has_interactive = tag.find_all(self.INTERACTIVE_TAGS)

                if not text_content and not has_interactive:
                    tags_to_remove.append(tag)

            # Remove collected tags
            for tag in tags_to_remove:
                if tag and tag.parent:
                    try:
                        tag.decompose()
                    except:
                        pass

    def _add_element_indices(self, soup: BeautifulSoup):
        """Add index to interactive elements for easier reference"""
        index = 0
        for tag in soup.find_all(self.INTERACTIVE_TAGS):
            if not tag:
                continue

            try:
                if not tag.get("id"):
                    tag["data-idx"] = str(index)
                    index += 1
            except:
                continue

    def clean_to_text_tree(self, html: str) -> str:
        """
        Convert HTML to a simplified text tree representation
        Better for LLMs with limited context

        Returns:
            Text representation like:
            [button id="submit"] Submit Form
            [input type="text" name="query" placeholder="Search..."]
            [a href="/about"] About Us
        """
        if not html or not html.strip():
            return ""

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Clean first
            self._remove_tags(soup)
            if self.remove_comments:
                self._remove_comments(soup)
            if self.remove_hidden:
                self._remove_hidden_elements(soup)

            # Convert to text tree
            lines = []
            body = soup.body if soup.body else soup
            if body:
                self._build_text_tree(body, lines, indent=0)

            return "\n".join(lines)
        except Exception as e:
            print(f"Warning: Error creating text tree: {e}")
            return html[:1000]  # Return truncated original

    def _build_text_tree(self, element, lines: List[str], indent: int):
        """Recursively build text tree"""
        if not element:
            return

        try:
            for child in element.children:
                if not child:
                    continue

                if isinstance(child, str):
                    text = " ".join(str(child).split()).strip()
                    if text:
                        lines.append("  " * indent + text)
                elif hasattr(child, "name") and child.name:
                    # Build element representation
                    attrs = []
                    for attr in [
                        "id",
                        "name",
                        "type",
                        "placeholder",
                        "href",
                        "value",
                        "aria-label",
                    ]:
                        val = child.get(attr)
                        if val:
                            attrs.append(f'{attr}="{val}"')

                    attr_str = " ".join(attrs)
                    text = (
                        child.get_text(strip=True)[:50]
                        if hasattr(child, "get_text")
                        else ""
                    )

                    if child.name in self.INTERACTIVE_TAGS or attrs:
                        element_str = f"[{child.name}"
                        if attr_str:
                            element_str += f" {attr_str}"
                        element_str += "]"
                        if text:
                            element_str += f" {text}"

                        lines.append("  " * indent + element_str)

                    # Recurse
                    self._build_text_tree(child, lines, indent + 1)
        except Exception as e:
            print(f"Warning: Error building tree branch: {e}")


# ============================================================================
# Convenience Functions
# ============================================================================


def clean_html(html: str, format: str = "html") -> str:
    """
    Clean HTML - convenience function

    Args:
        html: Raw HTML string
        format: Output format - 'html' or 'text'

    Returns:
        Cleaned HTML or text representation
    """
    cleaner = HTMLCleaner()

    if format == "text":
        return cleaner.clean_to_text_tree(html)
    else:
        return cleaner.clean(html)


def get_interactive_elements(html: str) -> List[dict]:
    """
    Extract list of interactive elements with their properties

    Returns:
        List of dicts with element info
    """
    cleaner = HTMLCleaner()
    soup = BeautifulSoup(cleaner.clean(html), "html.parser")

    elements = []
    for tag in soup.find_all(cleaner.INTERACTIVE_TAGS):
        element_info = {
            "tag": tag.name,
            "text": tag.get_text(strip=True)[:100],
            "attributes": {},
        }

        for attr in cleaner.KEEP_ATTRIBUTES:
            if tag.get(attr):
                element_info["attributes"][attr] = tag[attr]

        elements.append(element_info)

    return elements
