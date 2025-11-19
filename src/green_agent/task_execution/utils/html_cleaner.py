"""HTML cleaning utilities for web agents."""

import logging
from bs4 import BeautifulSoup
from typing import List

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


# ============================================================================
# Examples & Testing
# ============================================================================

if __name__ == "__main__":
    # Example 1: Clean complex HTML
    messy_html = """
    <!DOCTYPE html><html lang="en-US" translate="no" xmlns="http://www.w3.org/1999/xhtml" xmlns:fb="http://www.facebook.com/2008/fbml" xmlns:og="http://ogp.me/ns#"><head><style type="text/css">:root{--toastify-color-light: #fff;--toastify-color-dark: #121212;--toastify-color-info: #3498db;--toastify-color-success: #07bc0c;--toastify-color-warning: #f1c40f;--toastify-color-error: hsl(6, 78%, 57%);--toastify-color-transparent: rgba(255, 255, 255, .7);--toastify-icon-color-info: var(--toastify-color-info);--toastify-icon-color-success: var(--toastify-color-success);--toastify-icon-color-warning: var(--toastify-color-warning);--toastify-icon-color-error: var(--toastify-color-error);--toastify-container-width: fit-content;--toastify-toast-width: 320px;--toastify-toast-offset: 16px;--toastify-toast-top: max(var(--toastify-toast-offset), env(safe-area-inset-top));--toastify-toast-right: max(var(--toastify-toast-offset), env(safe-area-inset-right));--toastify-toast-left: max(var(--toastify-toast-offset), env(safe-area-inset-left));--toastify-toast-bottom: max(var(--toastify-toast-offset), env(safe-area-inset-bottom));--toastify-toast-background: #fff;--toastify-toast-padding: 14px;--toastify-toast-min-height: 64px;--toastify-toast-max-height: 800px;--toastify-toast-bd-radius: 6px;--toastify-toast-shadow: 0px 4px 12px rgba(0, 0, 0, .1);--toastify-font-family: sans-serif;--toastify-z-index: 9999;--toastify-text-color-light: #757575;--toastify-text-color-dark: #fff;--toastify-text-color-info: #fff;--toastify-text-color-success: #fff;--toastify-text-color-warning: #fff;--toastify-text-color-error: #fff;--toastify-spinner-color: #616161;--toastify-spinner-color-empty-area: #e0e0e0;--toastify-color-progress-light: linear-gradient(to right, #4cd964, #5ac8fa, #007aff, #34aadc, #5856d6, #ff2d55);--toastify-color-progress-dark: #bb86fc;--toastify-color-progress-info: var(--toastify-color-info);--toastify-color-progress-success: var(--toastify-color-success);--toastify-color-progress-warning: var(--toastify-color-warning);--toastify-color-progress-error: var(--toastify-color-error);--toastify-color-progress-bgo: .2}.Toastify__toast-container{z-index:var(--toastify-z-index);-webkit-transform:translate3d(0,0,var(--toastify-z-index));position:fixed;width:var(--toastify-container-width);box-sizing:border-box;color:#fff;display:flex;flex-direction:column}.Toastify__toast-container--top-left{top:var(--toastify-toast-top);left:var(--toastify-toast-left)}.Toastify__toast-container--top-center{top:var(--toastify-toast-top);left:50%;transform:translate(-50%);align-items:center}.Toastify__toast-container--top-right{top:var(--toastify-toast-top);right:var(--toastify-toast-right);align-items:end}.Toastify__toast-container--bottom-left{bottom:var(--toastify-toast-bottom);left:var(--toastify-toast-left)}.Toastify__toast-container--bottom-center{bottom:var(--toastify-toast-bottom);left:50%;transform:translate(-50%);align-items:center}.Toastify__toast-container--bottom-right{bottom:var(--toastify-toast-bottom);right:var(--toastify-toast-right);align-items:end}.Toastify__toast{--y: 0;position:relative;touch-action:none;width:var(--toastify-toast-width);min-height:var(--toastify-toast-min-height);box-sizing:border-box;margin-bottom:1rem;padding:var(--toastify-toast-padding);border-radius:var(--toastify-toast-bd-radius);box-shadow:var(--toastify-toast-shadow);max-height:var(--toastify-toast-max-height);font-family:var(--toastify-font-family);z-index:0;display:flex;flex:1 auto;align-items:center;word-break:break-word}@media only screen and (max-width: 480px){.Toastify__toast-container{width:100vw;left:env(safe-area-inset-left);margin:0}.Toastify__toast-container--top-left,.Toastify__toast-container--top-center,.Toastify__toast-container--top-right{top:env(safe-area-inset-top);transform:translate(0)}.Toastify__toast-container--bottom-left,.Toastify__toast-container--bottom-center,.Toastify__toast-container--bottom-right{bottom:env(safe-area-inset-bottom);transform:translate(0)}.Toastify__toast-container--rtl{right:env(safe-area-inset-right);left:initial}.Toastify__toast{--toastify-toast-width: 100%;margin-bottom:0;border-radius:0}}.Toastify__toast-container[data-stacked=true]{width:var(--toastify-toast-width)}.Toastify__toast--stacked{position:absolute;width:100%;transform:translate3d(0,var(--y),0) scale(var(--s));transition:transform .3s}.Toastify__toast--stacked[data-collapsed] .Toastify__toast-body,.Toastify__toast--stacked[data-collapsed] .Toastify__close-button{transition:opacity .1s}.Toastify__toast--stacked[data-collapsed=false]{overflow:visible}.Toastify__toast--stacked[data-collapsed=true]:not(:last-child)>*{opacity:0}.Toastify__toast--stacked:after{content:"";position:absolute;left:0;right:0;height:calc(var(--g) * 1px);bottom:100%}.Toastify__toast--stacked[data-pos=top]{top:0}.Toastify__toast--stacked[data-pos=bot]{bottom:0}.Toastify__toast--stacked[data-pos=bot].Toastify__toast--stacked:before{transform-origin:top}.Toastify__toast--stacked[data-pos=top].Toastify__toast--stacked:before{transform-origin:bottom}.Toastify__toast--stacked:before{content:"";position:absolute;left:0;right:0;bottom:0;height:100%;transform:scaleY(3);z-index:-1}.Toastify__toast--rtl{direction:rtl}.Toastify__toast--close-on-click{cursor:pointer}.Toastify__toast-icon{margin-inline-end:10px;width:22px;flex-shrink:0;display:flex}.Toastify--animate{animation-fill-mode:both;animation-duration:.5s}.Toastify--animate-icon{animation-fill-mode:both;animation-duration:.3s}.Toastify__toast-theme--dark{background:var(--toastify-color-dark);color:var(--toastify-text-color-dark)}.Toastify__toast-theme--light,.Toastify__toast-theme--colored.Toastify__toast--default{background:var(--toastify-color-light);color:var(--toastify-text-color-light)}.Toastify__toast-theme--colored.Toastify__toast--info{color:var(--toastify-text-color-info);background:var(--toastify-color-info)}.Toastify__toast-theme--colored.Toastify__toast--success{color:var(--toastify-text-color-success);background:var(--toastify-color-success)}.Toastify__toast-theme--colored.Toastify__toast--warning{color:var(--toastify-text-color-warning);background:var(--toastify-color-warning)}.Toastify__toast-theme--colored.Toastify__toast--error{color:var(--toastify-text-color-error);background:var(--toastify-color-error)}.Toastify__progress-bar-theme--light{background:var(--toastify-color-progress-light)}.Toastify__progress-bar-theme--dark{background:var(--toastify-color-progress-dark)}.Toastify__progress-bar--info{background:var(--toastify-color-progress-info)}.Toastify__progress-bar--success{background:var(--toastify-color-progress-success)}.Toastify__progress-bar--warning{background:var(--toastify-color-progress-warning)}.Toastify__progress-bar--error{background:var(--toastify-color-progress-error)}.Toastify__progress-bar-theme--colored.Toastify__progress-bar--info,.Toastify__progress-bar-theme--colored.Toastify__progress-bar--success,.Toastify__progress-bar-theme--colored.Toastify__progress-bar--warning,.Toastify__progress-bar-theme--colored.Toastify__progress-bar--error{background:var(--toastify-color-transparent)}.Toastify__close-button{color:#fff;position:absolute;top:6px;right:6px;background:transparent;outline:none;border:none;padding:0;cursor:pointer;opacity:.7;transition:.3s ease;z-index:1}.Toastify__toast--rtl .Toastify__close-button{left:6px;right:unset}.Toastify__close-button--light{color:#000;opacity:.3}.Toastify__close-button>svg{fill:currentColor;height:16px;width:14px}.Toastify__close-button:hover,.Toastify__close-button:focus{opacity:1}@keyframes Toastify__trackProgress{0%{transform:scaleX(1)}to{transform:scaleX(0)}}.Toastify__progress-bar{position:absolute;bottom:0;left:0;width:100%;height:100%;z-index:1;opacity:.7;transform-origin:left}.Toastify__progress-bar--animated{animation:Toastify__trackProgress linear 1 forwards}.Toastify__progress-bar--controlled{transition:transform .2s}.Toastify__progress-bar--rtl{right:0;left:initial;transform-origin:right;border-bottom-left-radius:initial}.Toastify__progress-bar--wrp{position:absolute;overflow:hidden;bottom:0;left:0;width:100%;height:5px;border-bottom-left-radius:var(--toastify-toast-bd-radius);border-bottom-right-radius:var(--toastify-toast-bd-radius)}.Toastify__progress-bar--wrp[data-hidden=true]{opacity:0}.Toastify__progress-bar--bg{opacity:var(--toastify-color-progress-bgo);width:100%;height:100%}.Toastify__spinner{width:20px;height:20px;box-sizing:border-box;border:2px solid;border-radius:100%;border-color:var(--toastify-spinner-color-empty-area);border-right-color:var(--toastify-spinner-color);animation:Toastify__spin .65s linear infinite}@keyframes Toastify__bounceInRight{0%,60%,75%,90%,to{animation-timing-function:cubic-bezier(.215,.61,.355,1)}0%{opacity:0;transform:translate3d(3000px,0,0)}60%{opacity:1;transform:translate3d(-25px,0,0)}75%{transform:translate3d(10px,0,0)}90%{transform:translate3d(-5px,0,0)}to{transform:none}}@keyframes Toastify__bounceOutRight{20%{opacity:1;transform:translate3d(-20px,var(--y),0)}to{opacity:0;transform:translate3d(2000px,var(--y),0)}}@keyframes Toastify__bounceInLeft{0%,60%,75%,90%,to{animation-timing-function:cubic-bezier(.215,.61,.355,1)}0%{opacity:0;transform:translate3d(-3000px,0,0)}60%{opacity:1;transform:translate3d(25px,0,0)}75%{transform:translate3d(-10px,0,0)}90%{transform:translate3d(5px,0,0)}to{transform:none}}@keyframes Toastify__bounceOutLeft{20%{opacity:1;transform:translate3d(20px,var(--y),0)}to{opacity:0;transform:translate3d(-2000px,var(--y),0)}}@keyframes Toastify__bounceInUp{0%,60%,75%,90%,to{animation-timing-function:cubic-bezier(.215,.61,.355,1)}0%{opacity:0;transform:translate3d(0,3000px,0)}60%{opacity:1;transform:translate3d(0,-20px,0)}75%{transform:translate3d(0,10px,0)}90%{transform:translate3d(0,-5px,0)}to{transform:translateZ(0)}}@keyframes Toastify__bounceOutUp{20%{transform:translate3d(0,calc(var(--y) - 10px),0)}40%,45%{opacity:1;transform:translate3d(0,calc(var(--y) + 20px),0)}to{opacity:0;transform:translate3d(0,-2000px,0)}}@keyframes Toastify__bounceInDown{0%,60%,75%,90%,to{animation-timing-function:cubic-bezier(.215,.61,.355,1)}0%{opacity:0;transform:translate3d(0,-3000px,0)}60%{opacity:1;transform:translate3d(0,25px,0)}75%{transform:translate3d(0,-10px,0)}90%{transform:translate3d(0,5px,0)}to{transform:none}}@keyframes Toastify__bounceOutDown{20%{transform:translate3d(0,calc(var(--y) - 10px),0)}40%,45%{opacity:1;transform:translate3d(0,calc(var(--y) + 20px),0)}to{opacity:0;transform:translate3d(0,2000px,0)}}.Toastify__bounce-enter--top-left,.Toastify__bounce-enter--bottom-left{animation-name:Toastify__bounceInLeft}.Toastify__bounce-enter--top-right,.Toastify__bounce-enter--bottom-right{animation-name:Toastify__bounceInRight}.Toastify__bounce-enter--top-center{animation-name:Toastify__bounceInDown}.Toastify__bounce-enter--bottom-center{animation-name:Toastify__bounceInUp}.Toastify__bounce-exit--top-left,.Toastify__bounce-exit--bottom-left{animation-name:Toastify__bounceOutLeft}.Toastify__bounce-exit--top-right,.Toastify__bounce-exit--bottom-right{animation-name:Toastify__bounceOutRight}.Toastify__bounce-exit--top-center{animation-name:Toastify__bounceOutUp}.Toastify__bounce-exit--bottom-center{animation-name:Toastify__bounceOutDown}@keyframes Toastify__zoomIn{0%{opacity:0;transform:scale3d(.3,.3,.3)}50%{opacity:1}}@keyframes Toastify__zoomOut{0%{opacity:1}50%{opacity:0;transform:translate3d(0,var(--y),0) scale3d(.3,.3,.3)}to{opacity:0}}.Toastify__zoom-enter{animation-name:Toastify__zoomIn}.Toastify__zoom-exit{animation-name:Toastify__zoomOut}@keyframes Toastify__flipIn{0%{transform:perspective(400px) rotateX(90deg);animation-timing-function:ease-in;opacity:0}40%{transform:perspective(400px) rotateX(-20deg);animation-timing-function:ease-in}60%{transform:perspective(400px) rotateX(10deg);opacity:1}80%{transform:perspective(400px) rotateX(-5deg)}to{transform:perspective(400px)}}@keyframes Toastify__flipOut{0%{transform:translate3d(0,var(--y),0) perspective(400px)}30%{transform:translate3d(0,var(--y),0) perspective(400px) rotateX(-20deg);opacity:1}to{transform:translate3d(0,var(--y),0) perspective(400px) rotateX(90deg);opacity:0}}.Toastify__flip-enter{animation-name:Toastify__flipIn}.Toastify__flip-exit{animation-name:Toastify__flipOut}@keyframes Toastify__slideInRight{0%{transform:translate3d(110%,0,0);visibility:visible}to{transform:translate3d(0,var(--y),0)}}@keyframes Toastify__slideInLeft{0%{transform:translate3d(-110%,0,0);visibility:visible}to{transform:translate3d(0,var(--y),0)}}@keyframes Toastify__slideInUp{0%{transform:translate3d(0,110%,0);visibility:visible}to{transform:translate3d(0,var(--y),0)}}@keyframes Toastify__slideInDown{0%{transform:translate3d(0,-110%,0);visibility:visible}to{transform:translate3d(0,var(--y),0)}}@keyframes Toastify__slideOutRight{0%{transform:translate3d(0,var(--y),0)}to{visibility:hidden;transform:translate3d(110%,var(--y),0)}}@keyframes Toastify__slideOutLeft{0%{transform:translate3d(0,var(--y),0)}to{visibility:hidden;transform:translate3d(-110%,var(--y),0)}}@keyframes Toastify__slideOutDown{0%{transform:translate3d(0,var(--y),0)}to{visibility:hidden;transform:translate3d(0,500px,0)}}@keyframes Toastify__slideOutUp{0%{transform:translate3d(0,var(--y),0)}to{visibility:hidden;transform:translate3d(0,-500px,0)}}.Toastify__slide-enter--top-left,.Toastify__slide-enter--bottom-left{animation-name:Toastify__slideInLeft}.Toastify__slide-enter--top-right,.Toastify__slide-enter--bottom-right{animation-name:Toastify__slideInRight}.Toastify__slide-enter--top-center{animation-name:Toastify__slideInDown}.Toastify__slide-enter--bottom-center{animation-name:Toastify__slideInUp}.Toastify__slide-exit--top-left,.Toastify__slide-exit--bottom-left{animation-name:Toastify__slideOutLeft;animation-timing-function:ease-in;animation-duration:.3s}.Toastify__slide-exit--top-right,.Toastify__slide-exit--bottom-right{animation-name:Toastify__slideOutRight;animation-timing-function:ease-in;animation-duration:.3s}.Toastify__slide-exit--top-center{animation-name:Toastify__slideOutUp;animation-timing-function:ease-in;animation-duration:.3s}.Toastify__slide-exit--bottom-center{animation-name:Toastify__slideOutDown;animation-timing-function:ease-in;animation-duration:.3s}@keyframes Toastify__spin{0%{transform:rotate(0)}to{transform:rotate(360deg)}}
</style>


<title>Buy sports, concert and theater tickets on StubHub!</title>
<meta name="description" content="Buy and sell sports tickets, concert tickets, theater tickets and Broadway tickets on StubHub!">
<meta name="keywords" content="StubHub, buy tickets, sell tickets, concert, sport, theater">



<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="format-detection" content="telephone=no">


<link rel="preconnect dns-prefetch" href="https://ws.vggcdn.net/">
<link rel="preconnect dns-prefetch" href="https://ws.vggcdn.net/" crossorigin="">

<link rel="preconnect dns-prefetch" href="https://img.vggcdn.net/">
<link rel="preconnect dns-prefetch" href="https://img.vggcdn.net/" crossorigin="">

<link rel="preconnect dns-prefetch" href="https://wt.viagogo.net">
<link rel="preconnect dns-prefetch" href="https://wt.viagogo.net" crossorigin="">

<link rel="preconnect dns-prefetch" href="//www.google-analytics.com">
<link rel="preconnect dns-prefetch" href="//www.google-analytics.com" crossorigin="">

<link rel="preconnect dns-prefetch" href="https://media.stubhubstatic.com">
<link rel="preconnect dns-prefetch" href="https://www.facebook.com">
<link rel="preconnect dns-prefetch" href="https://connect.facebook.net">
<link rel="preconnect dns-prefetch" href="https://maps.googleapis.com">
<link rel="preconnect dns-prefetch" href="https://googleads.g.doubleclick.net">
<link rel="preconnect dns-prefetch" href="https://www.googleadservices.com">

    <link rel="preconnect dns-prefetch" href="https://fonts.googleapis.com">
    <link rel="preconnect dns-prefetch" href="https://fonts.gstatic.com" crossorigin="">
    <link rel="preload" href="https://fonts.googleapis.com/css?family=Inter:400,500,600,700&amp;display=block" as="style">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Inter:400,500,600,700&amp;display=block">


<script type="text/javascript" async="" src="https://www.googletagmanager.com/gtag/js?id=G-1686WQLB4Q&amp;cx=c&amp;gtm=4e5bc1"></script><script src="//bat.bing.com/bat.js" async=""></script><script type="text/javascript" src="https://b2037b2ab8ee.edge.sdk.awswaf.com/b2037b2ab8ee/db6f5e3d1a86/challenge.compact.js" defer=""></script>



            <link rel="preload" as="image" href="https://media.stubhubstatic.com/stubhub-v2-catalog/d_defaultLogo.jpg/q_auto:low,f_auto,c_fill,g_auto,w_1600,h_800/categories/10669/6395464">
            <link rel="preload" as="image" href="https://media.stubhubstatic.com/stubhub-dam/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/Team_Logos/NFL/Las_Vegas_Raiders/Las_Vegas_Raiders_SmallHelmetVariant_Desktop.png">
            <link rel="preload" as="image" href="https://media.stubhubstatic.com/stubhub-dam/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/Team_Logos/NFL/Philadelphia_Eagles/Philadelphia_Eagles_SmallHelmetVariant_Desktop.png">
            <link rel="preload" as="image" href="https://media.stubhubstatic.com/stubhub-v2-catalog/d_defaultLogo.jpg/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/categories/421995/6439975">
            <link rel="preload" as="image" href="https://media.stubhubstatic.com/stubhub-v2-catalog/d_defaultLogo.jpg/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/categories/58950/6437782">

    <link rel="icon" href="/favicon.ico">

<meta property="og:url" content="https://www.stubhub.com/"><meta property="og:title" content=""><meta property="og:type" content="article"><meta property="og:image" content="https://img.vggcdn.net/images/Assets/sh-logo-indigo.png"><meta property="og:description" content=""><meta property="og:site_name" content="stubhub.com"><meta property="fb:admins" content="1838832188,100004244673138,100001535457519"><meta property="fb:app_id" content="3021345037">
<link rel="canonical" href="https://www.stubhub.com/florida-tropics-sc-tickets/performer/100275935">



                    <link defer="" rel="stylesheet" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/vendor.BXBSz2qX.css">
                    <link defer="" rel="stylesheet" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/mapbox-gl.BfrFMvqD.css">
                    <script type="module" crossorigin="" src="https://ws.vggcdn.net/Scripts/d/e/v/sentry-init.B7wuzK7_.js"></script>
                    <link defer="" rel="stylesheet" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/viagogo-app-entrypoint.BQK_clNn.css">
                    <script type="module" crossorigin="" src="https://ws.vggcdn.net/Scripts/d/e/v/viagogo-home.DoJFGhxQ.js"></script>

<style data-styled="active" data-styled-version="6.3.0"></style><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/index.Ds73PPaa.chunk.js"><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/vendor.fVxZN0Qy.chunk.js"><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/mapbox-gl.CWCXES_M.chunk.js"><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/viagogo-modules.BcnTPjlp.chunk.js"><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/viagogo-app-entrypoint.K0d1JIx1.chunk.js"><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/SentryTags.CUvUo7Bg.chunk.js"><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/sentry.BLSkjsVY.chunk.js"><link rel="modulepreload" as="script" crossorigin="" href="https://ws.vggcdn.net/Scripts/d/e/v/broadway.BlggpwEh.chunk.js"><script id="__googleMapsScriptId" src="https://maps.googleapis.com/maps/api/js?libraries=geocoding%2Cplaces&amp;key=AIzaSyA7b9MlEm0ci6vgsOuxb5L2UcnxD3Yy4ec&amp;language=en&amp;callback=google.maps.__ib__"></script><script src="https://bat.bing.com/p/action/4031192.js" type="text/javascript" async="" data-ueto="ueto_179b9c2e25"></script><script src="https://maps.googleapis.com/maps-api-v3/api/js/62/13e/places.js"></script><script src="https://maps.googleapis.com/maps-api-v3/api/js/62/13e/main.js"></script><script type="text/javascript" async="" src="https://googleads.g.doubleclick.net/pagead/viewthroughconversion/1039308173/?random=1763399221116&amp;cv=11&amp;fst=1763399221116&amp;bg=ffffff&amp;guid=ON&amp;async=1&amp;en=gtag.config&amp;gtm=45be5bc1v887270597za200zd887270597xec&amp;gcd=13l3l3R3l5l1&amp;dma=0&amp;tag_exp=103116026~103200004~104527906~104528500~104684208~104684211~115497441~115583767~115938466~115938468~116217636~116217638~116474636&amp;u_w=1280&amp;u_h=720&amp;url=https%3A%2F%2Fwww.stubhub.com%2F&amp;frm=0&amp;tiba=Buy%20sports%2C%20concert%20and%20theater%20tickets%20on%20StubHub!&amp;hn=www.googleadservices.com&amp;npa=0&amp;pscdl=noapi&amp;auid=2072341785.1763399221&amp;uaa=x86&amp;uab=64&amp;uafvl=Not%253DA%253FBrand%3B24.0.0.0%7CChromium%3B140.0.7339.16&amp;uamb=0&amp;uam=&amp;uap=Windows&amp;uapv=10.0&amp;uaw=0&amp;data=event%3Dgtag.config&amp;rfmt=3&amp;fmt=4"></script><script type="text/javascript" async="" src="https://googleads.g.doubleclick.net/pagead/viewthroughconversion/1039308173/?random=1763399221130&amp;cv=11&amp;fst=1763399221130&amp;bg=ffffff&amp;guid=ON&amp;async=1&amp;en=page_view&amp;gtm=45be5bc1v887270597za200zd887270597xec&amp;gcd=13l3l3R3l5l1&amp;dma=0&amp;tag_exp=103116026~103200004~104527906~104528500~104684208~104684211~115497441~115583767~115938466~115938468~116217636~116217638~116474636&amp;u_w=1280&amp;u_h=720&amp;url=https%3A%2F%2Fwww.stubhub.com%2F&amp;frm=0&amp;tiba=Buy%20sports%2C%20concert%20and%20theater%20tickets%20on%20StubHub!&amp;hn=www.googleadservices.com&amp;npa=0&amp;pscdl=noapi&amp;auid=2072341785.1763399221&amp;uaa=x86&amp;uab=64&amp;uafvl=Not%253DA%253FBrand%3B24.0.0.0%7CChromium%3B140.0.7339.16&amp;uamb=0&amp;uam=&amp;uap=Windows&amp;uapv=10.0&amp;uaw=0&amp;data=event%3Dpage_view%3Bcatid%3D0%3Bcategorypagetype%3D0-Home&amp;rfmt=3&amp;fmt=4"></script></head>

<body class="go_L1033 go_A2189 go_CUAH v-L-1033 v-A-2189 v-C-UAH go_home_tablet v-home_tablet go_home_tablet_index v-home_tablet-index vt3" data-brand="stubhub" style="overflow: auto;">

<input type="hidden" id="x-csrf-token" name="x-csrf-token" value="9j199q6cpb_zJzQOddKvJ0NGqNIHM27AhyfVgLyKh21dMSbQ3wv4enRzmZeANu13rzqVInhWS4TqzVRQZgEJ114vzfUXlHuhL8rdcOwD3tY" style="">
    <input type="hidden" id="google-recaptcha-v2-sitekey" name="google-recaptcha-v2-sitekey" value="6LckUScUAAAAAN3Poew0YuQiT-o9ARG8sK0euTIM" style="">
    <input type="hidden" id="bot-protection-google-recaptcha-v2-sitekey" name="bot-protection-google-recaptcha-v2-sitekey" value="6Le3Fo4rAAAAABZoyfRFW6nS1qw-hUnTUb6tOB_m" style="">
    <input type="hidden" id="google-recaptcha-sitekey" name="google-recaptcha-sitekey" value="6LdM-_IUAAAAAFTKxGv8lySlDCe_HgO4ThLNdvZo" style="">


    <div id="app"><div class="sc-8db3838f-0 jiBQHw"><div class="sc-dc30b1d-0 fnLBAY"><div style="text-align: center;"><div class="sc-700c7ade-0 lfSmaq"><span class="sc-hQYpqj clvzKc"><span class="sc-ByBTN kJsAYw"><span class="sc-biHcxq eTRWIR">StubHub is the world's top destination for ticket buyers and resellers. Prices may be higher or lower than face value.</span>&nbsp;</span></span></div></div><div class="sc-ac72956f-0 gvbrPC"><div class="sc-8dbdee01-0"><div class="sc-lbVvkl kKjWCR"><div class="sc-8dbdee01-3 kaowDZ"><div style="position: relative; overflow: hidden; max-height: 50px; max-width: 100px;"><a href="https://www.stubhub.com" class="sc-jrsJWq kOyZWS"><img src="https://img.vggcdn.net/images/Assets/Icons/bfx/stubhub-purple-logo-light-theme.svg" alt="stubhub" style="object-fit: contain; height: 50px; width: 100px;"></a><h2 class="sc-iCoGMa biRRDK sc-kEqXSd hVTIas">Buy sports, concert and theater tickets on StubHub!</h2></div><div class="sc-8dbdee01-2 jvhmcW"><div class="sc-45ea0181-0 dHuvRp"><nav class="sc-5c91edb2-0 pBJkN"><ul class="sc-5c91edb2-1 frJzbX"><li tabindex="0" aria-expanded="false" aria-haspopup="dialog" class="sc-9f8c81bc-0 kia-dj"><p class="sc-9f8c81bc-1 bFToDo">Sports</p></li><li tabindex="0" aria-expanded="false" aria-haspopup="dialog" class="sc-9f8c81bc-0 kia-dj"><p class="sc-9f8c81bc-1 bFToDo">Concerts</p></li><li tabindex="0" aria-expanded="false" aria-haspopup="dialog" class="sc-9f8c81bc-0 kia-dj"><p class="sc-9f8c81bc-1 bFToDo">Theater</p></li><li tabindex="0" aria-expanded="false" aria-haspopup="dialog" class="sc-9f8c81bc-0 kia-dj"><p class="sc-9f8c81bc-1 bFToDo">Festivals</p></li><li tabindex="0" aria-expanded="false" aria-haspopup="dialog" class="sc-9f8c81bc-0 kia-dj"><p class="sc-9f8c81bc-1 bFToDo">Top Cities</p></li></ul></nav></div></div><div class="sc-8dbdee01-1 kXyyph"><div class="sc-8dbdee01-6 dWRiOY"><div class="sc-ikXwFL cErIVj"><div class="sc-fbIWvQ hXzgVg"><a class="sc-jrsJWq kOyZWS sc-FRrlJ bfcnBi" href="/gift-cards">Gift Cards</a></div></div></div><div class="sc-8dbdee01-6 dWRiOY"><div class="sc-ikXwFL cErIVj"><div class="sc-fbIWvQ hXzgVg"><a class="sc-jrsJWq kOyZWS sc-FRrlJ bfcnBi" href="/explore">Explore</a></div></div></div><div class="sc-8dbdee01-6 dWRiOY"><div class="sc-ikXwFL cErIVj"><div class="sc-fbIWvQ hXzgVg"><a class="sc-jrsJWq kOyZWS sc-FRrlJ bfcnBi" href="/selltickets">Sell</a><div class="sc-fXazdB iGCaNS"><a href="/selltickets" class="sc-jrsJWq kOyZWS"><div class="sc-dvXYtk bxIlvy">Sell Tickets</div></a><a href="/secure/myaccount/listings" class="sc-jrsJWq kOyZWS"><div class="sc-dvXYtk bxIlvy">My Tickets</div></a><a href="/secure/myaccount/sales" class="sc-jrsJWq kOyZWS"><div class="sc-dvXYtk bxIlvy">My Sales</div></a></div></div></div></div><div class="sc-8dbdee01-6 dWRiOY"><div class="sc-ikXwFL cErIVj"><div class="sc-fbIWvQ hXzgVg"><a class="sc-jrsJWq kOyZWS sc-FRrlJ bfcnBi" href="/favorites">Favorites</a></div></div></div><div class="sc-8dbdee01-6 dWRiOY"><div class="sc-ikXwFL cErIVj"><div class="sc-fbIWvQ hXzgVg"><a class="sc-jrsJWq kOyZWS sc-FRrlJ bfcnBi" href="/secure/myaccount">My Tickets</a><div class="sc-fXazdB iGCaNS"><a href="/secure/myaccount/purchases" class="sc-jrsJWq kOyZWS"><div class="sc-dvXYtk bxIlvy">Orders</div></a><a href="/secure/myaccount/listings" class="sc-jrsJWq kOyZWS"><div class="sc-dvXYtk bxIlvy">My Listings</div></a><a href="/secure/myaccount/sales" class="sc-jrsJWq kOyZWS"><div class="sc-dvXYtk bxIlvy">My Sales</div></a><a href="/secure/myaccount/payments" class="sc-jrsJWq kOyZWS"><div class="sc-dvXYtk bxIlvy">Payments</div></a></div></div></div></div><div class="sc-8dbdee01-6 dWRiOY"><div class="sc-ikXwFL cErIVj"><div class="sc-fbIWvQ hXzgVg"><a class="sc-jrsJWq kOyZWS sc-FRrlJ bfcnBi" href="/secure/login?ReturnUrl=https%3A%2F%2Fwww.stubhub.com%2F">Sign In</a></div></div></div><a href="/secure/myaccount" title="profile" class="sc-jrsJWq kOyZWS"><span class="sc-euEtCS gEWBzr"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 25 25" height="32px"><g fill="currentColor"><ellipse cx="12" cy="11.897" fill="#eff5f8" stroke="#eff5f8" rx="11.5" ry="11.397"></ellipse><path d="M20.439 20.356A12.014 12.014 0 0112 23.795a12.014 12.014 0 01-8.474-3.474l.478-3.33.362-.198c4.259-2.27 10.969-2.27 15.228 0l.361.199.484 3.364zM8.344 10.419l-.241-2.43a3.627 3.627 0 01.924-2.828 3.849 3.849 0 012.772-1.195c1.085 0 2.09.438 2.772 1.195.683.757 1.045 1.792.925 2.828l-.242 2.43c-.2 1.793-1.647 3.107-3.455 3.107s-3.295-1.354-3.455-3.107z"></path></g></svg></span></a></div></div><div class="sc-lbVvkl kKjWCR sc-8dbdee01-4 gZCwFm"><form action="/secure/search/process?" method="post"><input type="hidden" name="appname" value="viagogo-home.js" style=""><input type="hidden" name="keyword" value="" style=""><input type="hidden" name="searchguid" value="3B85FCCC-76E2-42E2-BD79-A53F39B41571" style=""><div><div class="sc-15a63049-0 fxltds sc-e976da86-1 sc-e976da86-2 fqPiPS iCKwId"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="24px" height="24px" fill="textPrimary" class="sc-hKFxyK bwxPHh sc-e976da86-3 rLAeF"><path fill="currentColor" fill-rule="evenodd" d="M13.391 14.452a7 7 0 1 1 1.06-1.06l3.33 3.328a.75.75 0 1 1-1.061 1.06zM14.5 9a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0" clip-rule="evenodd"></path></svg><input placeholder="Search events, artists, teams, and more" class="sc-15a63049-1 ODfrj" value="" style=""></div></div></form></div></div></div></div><div class="sc-dc30b1d-2 fPFWGP"><div class="sc-95c6a622-0 cwowiR"><div class="sc-95c6a622-1 hRDjeI"><a class="sc-jrsJWq kOyZWS sc-dc30b1d-4 itkhvO" href="/george-strait-tickets/performer/6382"><div class="sc-dc30b1d-5 FFdbg"><div class="sc-dc30b1d-3 euiBUv"><h2 class="sc-dc30b1d-7 bBoNPa">George Strait</h2><div class="sc-gtsrHU hPIxNx sc-dc30b1d-14 gQAbRk"><button class="sc-hHEiqM iBXfhe sc-dc30b1d-9 eEHlFf">See Tickets</button></div></div><ol class="sc-b49c0834-0 jsbnlX"><li><button id="dot-10669" aria-label="0 - George Strait" aria-current="true" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 cQRcwl"></div></button></li><li><button id="dot-5596" aria-label="1 - Las Vegas Raiders" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-5510" aria-label="2 - Philadelphia Eagles" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-421995" aria-label="3 - Formula 1" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-58950" aria-label="4 - Morgan Wallen" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li></ol></div><div class="sc-dc30b1d-10 gAYfsA"><img alt="" class="sc-5a8f775c-6 eqaALM sc-dc30b1d-11 jhSutk" src="https://media.stubhubstatic.com/stubhub-v2-catalog/d_defaultLogo.jpg/q_auto:low,f_auto,c_fill,g_auto,w_1600,h_800/categories/10669/6395464"><button aria-label="" class="sc-619925ea-3 bnYlsy sc-dc30b1d-13 fCcuGt"><div class="sc-619925ea-4 dzjMdZ"><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-6 dlecmV kmsdXn kLOAjF">Followed</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-7 dlecmV kmsdXn jUglYD">Follow</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-8 dlecmV kmsdXn bdZiCQ">31.8K</p></div><div class="sc-619925ea-0 ccRVJd"><div color="#FFFFFF" class="sc-bbeaa494-0 hHweBp"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="24px" height="24px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" fill-rule="evenodd" d="M4.348 2.33C1.383 3.447.202 6.778 1.56 9.465 2.714 11.745 5.14 14.737 10 18c4.86-3.264 7.286-6.255 8.44-8.535 1.358-2.687.177-6.018-2.788-7.135-1.947-.735-3.52-.11-4.53.584A6 6 0 0 0 10 3.908a6 6 0 0 0-1.123-.994c-1.01-.694-2.582-1.319-4.529-.584m4.52 2.563.755.867a.5.5 0 0 0 .754 0l.754-.867c.46-.528 1.944-1.932 3.992-1.16A3.616 3.616 0 0 1 17.1 8.789c-.948 1.874-2.965 4.466-7.101 7.39-4.136-2.924-6.154-5.517-7.101-7.39a3.617 3.617 0 0 1 1.979-5.055c2.048-.772 3.53.632 3.99 1.16" clip-rule="evenodd"></path></svg></div></div></button><div class="sc-dc30b1d-12 jLGBrw"></div></div></a></div><div class="sc-95c6a622-1 lgTLVl"><a class="sc-jrsJWq kOyZWS sc-dc30b1d-4 itkhvO" href="/las-vegas-raiders-tickets/performer/139"><div class="sc-dc30b1d-5 FFdbg"><div class="sc-dc30b1d-3 euiBUv"><h2 class="sc-dc30b1d-7 bBoNPa">Las Vegas Raiders</h2><div class="sc-gtsrHU hPIxNx sc-dc30b1d-14 gQAbRk"><button class="sc-hHEiqM iBXfhe sc-dc30b1d-9 eEHlFf">See Tickets</button></div></div><ol class="sc-b49c0834-0 jsbnlX"><li><button id="dot-10669" aria-label="0 - George Strait" aria-current="true" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 cQRcwl"></div></button></li><li><button id="dot-5596" aria-label="1 - Las Vegas Raiders" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-5510" aria-label="2 - Philadelphia Eagles" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-421995" aria-label="3 - Formula 1" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-58950" aria-label="4 - Morgan Wallen" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li></ol></div><div class="sc-dc30b1d-10 gAYfsA"><img alt="" class="sc-5a8f775c-6 eqaALM sc-dc30b1d-11 jhSutk" src="https://media.stubhubstatic.com/stubhub-dam/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/Team_Logos/NFL/Las_Vegas_Raiders/Las_Vegas_Raiders_SmallHelmetVariant_Desktop.png"><button aria-label="" class="sc-619925ea-3 bnYlsy sc-dc30b1d-13 fCcuGt"><div class="sc-619925ea-4 cBbceE"><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-6 dlecmV kmsdXn kLOAjF">Followed</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-7 dlecmV kmsdXn jUglYD">Follow</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-8 dlecmV kmsdXn bdZiCQ">23K</p></div><div class="sc-619925ea-0 ccRVJd"><div color="#FFFFFF" class="sc-bbeaa494-0 hHweBp"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="24px" height="24px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" fill-rule="evenodd" d="M4.348 2.33C1.383 3.447.202 6.778 1.56 9.465 2.714 11.745 5.14 14.737 10 18c4.86-3.264 7.286-6.255 8.44-8.535 1.358-2.687.177-6.018-2.788-7.135-1.947-.735-3.52-.11-4.53.584A6 6 0 0 0 10 3.908a6 6 0 0 0-1.123-.994c-1.01-.694-2.582-1.319-4.529-.584m4.52 2.563.755.867a.5.5 0 0 0 .754 0l.754-.867c.46-.528 1.944-1.932 3.992-1.16A3.616 3.616 0 0 1 17.1 8.789c-.948 1.874-2.965 4.466-7.101 7.39-4.136-2.924-6.154-5.517-7.101-7.39a3.617 3.617 0 0 1 1.979-5.055c2.048-.772 3.53.632 3.99 1.16" clip-rule="evenodd"></path></svg></div></div></button><div class="sc-dc30b1d-12 jLGBrw"></div></div></a></div><div class="sc-95c6a622-1 lgTLVl"><a class="sc-jrsJWq kOyZWS sc-dc30b1d-4 itkhvO" href="/philadelphia-eagles-tickets/performer/761"><div class="sc-dc30b1d-5 FFdbg"><div class="sc-dc30b1d-3 euiBUv"><h2 class="sc-dc30b1d-7 bBoNPa">Philadelphia Eagles</h2><div class="sc-gtsrHU hPIxNx sc-dc30b1d-14 gQAbRk"><button class="sc-hHEiqM iBXfhe sc-dc30b1d-9 eEHlFf">See Tickets</button></div></div><ol class="sc-b49c0834-0 jsbnlX"><li><button id="dot-10669" aria-label="0 - George Strait" aria-current="true" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 cQRcwl"></div></button></li><li><button id="dot-5596" aria-label="1 - Las Vegas Raiders" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-5510" aria-label="2 - Philadelphia Eagles" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-421995" aria-label="3 - Formula 1" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-58950" aria-label="4 - Morgan Wallen" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li></ol></div><div class="sc-dc30b1d-10 gAYfsA"><img alt="" class="sc-5a8f775c-6 eqaALM sc-dc30b1d-11 jhSutk" src="https://media.stubhubstatic.com/stubhub-dam/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/Team_Logos/NFL/Philadelphia_Eagles/Philadelphia_Eagles_SmallHelmetVariant_Desktop.png"><button aria-label="" class="sc-619925ea-3 bnYlsy sc-dc30b1d-13 fCcuGt"><div class="sc-619925ea-4 dzjMdZ"><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-6 dlecmV kmsdXn kLOAjF">Followed</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-7 dlecmV kmsdXn jUglYD">Follow</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-8 dlecmV kmsdXn bdZiCQ">42.1K</p></div><div class="sc-619925ea-0 ccRVJd"><div color="#FFFFFF" class="sc-bbeaa494-0 hHweBp"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="24px" height="24px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" fill-rule="evenodd" d="M4.348 2.33C1.383 3.447.202 6.778 1.56 9.465 2.714 11.745 5.14 14.737 10 18c4.86-3.264 7.286-6.255 8.44-8.535 1.358-2.687.177-6.018-2.788-7.135-1.947-.735-3.52-.11-4.53.584A6 6 0 0 0 10 3.908a6 6 0 0 0-1.123-.994c-1.01-.694-2.582-1.319-4.529-.584m4.52 2.563.755.867a.5.5 0 0 0 .754 0l.754-.867c.46-.528 1.944-1.932 3.992-1.16A3.616 3.616 0 0 1 17.1 8.789c-.948 1.874-2.965 4.466-7.101 7.39-4.136-2.924-6.154-5.517-7.101-7.39a3.617 3.617 0 0 1 1.979-5.055c2.048-.772 3.53.632 3.99 1.16" clip-rule="evenodd"></path></svg></div></div></button><div class="sc-dc30b1d-12 jLGBrw"></div></div></a></div><div class="sc-95c6a622-1 lgTLVl"><a class="sc-jrsJWq kOyZWS sc-dc30b1d-4 itkhvO" href="/formula-1-tickets/grouping/7948"><div class="sc-dc30b1d-5 FFdbg"><div class="sc-dc30b1d-3 euiBUv"><h2 class="sc-dc30b1d-7 bBoNPa">Formula 1</h2><div class="sc-gtsrHU hPIxNx sc-dc30b1d-14 gQAbRk"><button class="sc-hHEiqM iBXfhe sc-dc30b1d-9 eEHlFf">See Tickets</button></div></div><ol class="sc-b49c0834-0 jsbnlX"><li><button id="dot-10669" aria-label="0 - George Strait" aria-current="true" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 cQRcwl"></div></button></li><li><button id="dot-5596" aria-label="1 - Las Vegas Raiders" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-5510" aria-label="2 - Philadelphia Eagles" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-421995" aria-label="3 - Formula 1" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-58950" aria-label="4 - Morgan Wallen" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li></ol></div><div class="sc-dc30b1d-10 gAYfsA"><img alt="" class="sc-5a8f775c-6 eqaALM sc-dc30b1d-11 jhSutk" src="https://media.stubhubstatic.com/stubhub-v2-catalog/d_defaultLogo.jpg/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/categories/421995/6439975"><button aria-label="" class="sc-619925ea-3 bnYlsy sc-dc30b1d-13 fCcuGt"><div class="sc-619925ea-4 dzjMdZ"><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-6 dlecmV kmsdXn kLOAjF">Followed</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-7 dlecmV kmsdXn jUglYD">Follow</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-8 dlecmV kmsdXn bdZiCQ">19.6K</p></div><div class="sc-619925ea-0 ccRVJd"><div color="#FFFFFF" class="sc-bbeaa494-0 hHweBp"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="24px" height="24px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" fill-rule="evenodd" d="M4.348 2.33C1.383 3.447.202 6.778 1.56 9.465 2.714 11.745 5.14 14.737 10 18c4.86-3.264 7.286-6.255 8.44-8.535 1.358-2.687.177-6.018-2.788-7.135-1.947-.735-3.52-.11-4.53.584A6 6 0 0 0 10 3.908a6 6 0 0 0-1.123-.994c-1.01-.694-2.582-1.319-4.529-.584m4.52 2.563.755.867a.5.5 0 0 0 .754 0l.754-.867c.46-.528 1.944-1.932 3.992-1.16A3.616 3.616 0 0 1 17.1 8.789c-.948 1.874-2.965 4.466-7.101 7.39-4.136-2.924-6.154-5.517-7.101-7.39a3.617 3.617 0 0 1 1.979-5.055c2.048-.772 3.53.632 3.99 1.16" clip-rule="evenodd"></path></svg></div></div></button><div class="sc-dc30b1d-12 jLGBrw"></div></div></a></div><div class="sc-95c6a622-1 lgTLVl"><a class="sc-jrsJWq kOyZWS sc-dc30b1d-4 itkhvO" href="/morgan-wallen-tickets/performer/100271016"><div class="sc-dc30b1d-5 FFdbg"><div class="sc-dc30b1d-3 euiBUv"><h2 class="sc-dc30b1d-7 bBoNPa">Morgan Wallen</h2><div class="sc-gtsrHU hPIxNx sc-dc30b1d-14 gQAbRk"><button class="sc-hHEiqM iBXfhe sc-dc30b1d-9 eEHlFf">See Tickets</button></div></div><ol class="sc-b49c0834-0 jsbnlX"><li><button id="dot-10669" aria-label="0 - George Strait" aria-current="true" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 cQRcwl"></div></button></li><li><button id="dot-5596" aria-label="1 - Las Vegas Raiders" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-5510" aria-label="2 - Philadelphia Eagles" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-421995" aria-label="3 - Formula 1" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li><li><button id="dot-58950" aria-label="4 - Morgan Wallen" aria-current="false" class="sc-b49c0834-1 gqAfGc"><div color="white" class="sc-b49c0834-2 iQyUOE"></div></button></li></ol></div><div class="sc-dc30b1d-10 gAYfsA"><img alt="" class="sc-5a8f775c-6 eqaALM sc-dc30b1d-11 jhSutk" src="https://media.stubhubstatic.com/stubhub-v2-catalog/d_defaultLogo.jpg/q_auto:low,f_auto,c_fill,g_center,w_1600,h_800/categories/58950/6437782"><button aria-label="" class="sc-619925ea-3 bnYlsy sc-dc30b1d-13 fCcuGt"><div class="sc-619925ea-4 dzjMdZ"><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-6 dlecmV kmsdXn kLOAjF">Followed</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-7 dlecmV kmsdXn jUglYD">Follow</p><p class="sc-619925ea-2 sc-619925ea-5 sc-619925ea-8 dlecmV kmsdXn bdZiCQ">74.3K</p></div><div class="sc-619925ea-0 ccRVJd"><div color="#FFFFFF" class="sc-bbeaa494-0 hHweBp"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="24px" height="24px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" fill-rule="evenodd" d="M4.348 2.33C1.383 3.447.202 6.778 1.56 9.465 2.714 11.745 5.14 14.737 10 18c4.86-3.264 7.286-6.255 8.44-8.535 1.358-2.687.177-6.018-2.788-7.135-1.947-.735-3.52-.11-4.53.584A6 6 0 0 0 10 3.908a6 6 0 0 0-1.123-.994c-1.01-.694-2.582-1.319-4.529-.584m4.52 2.563.755.867a.5.5 0 0 0 .754 0l.754-.867c.46-.528 1.944-1.932 3.992-1.16A3.616 3.616 0 0 1 17.1 8.789c-.948 1.874-2.965 4.466-7.101 7.39-4.136-2.924-6.154-5.517-7.101-7.39a3.617 3.617 0 0 1 1.979-5.055c2.048-.772 3.53.632 3.99 1.16" clip-rule="evenodd"></path></svg></div></div></button><div class="sc-dc30b1d-12 jLGBrw"></div></div></a></div></div></div></div><div class="sc-eEVmNh jMNddC"><div class="sc-2b77336f-2 fDFNFi" style="overflow-x: hidden;"><div class="sc-lbVvkl buMxsB sc-2b77336f-0 igskr"><main class="sc-30d37666-0 kaPxWJ"><section class="sc-17678670-0 sc-17678670-1 jQSgWy jyVZiV"><section class="sc-17678670-0 sc-17678670-2 jQSgWy hhVspX"><div class="sc-93aad5f1-0 iCpjeZ"><div class="sc-b093cfc3-1 YyBmy"><div class="sc-b093cfc3-0 jdEEtP"><div class="sc-17678670-4 ejPgSl"><div><span class="sc-22a44024-1 gfgTjg"><span class="sc-60f6b272-0 huiunV"><button class="sc-hHEiqM gkyuSM sc-60f6b272-1 dmdwdu"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="20px" height="20px" fill="inherit" class="sc-hKFxyK jTStXh"><path fill="currentColor" fill-rule="evenodd" d="M8.742 10.499a1 1 0 0 1 .76.755l1.356 5.963c.22.972 1.57 1.058 1.913.123l5.163-13.995c.294-.8-.485-1.579-1.285-1.282l-14 5.213c-.935.347-.84 1.7.134 1.915z" clip-rule="evenodd"></path></svg></button></span></span><span class="sc-22a44024-1 hjbIyK"><div tabindex="0" role="combobox" aria-label="Filter by location" aria-expanded="false" class="sc-iJCRrD jxqrVh"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="presentation" width="20px" height="20px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" d="m9.517 18.825.483-.574.483.574a.75.75 0 0 1-.966 0"></path><path fill="currentColor" fill-rule="evenodd" d="M10 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6m1.5-3a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0" clip-rule="evenodd"></path><path fill="currentColor" fill-rule="evenodd" d="m9.517 18.825.483-.574.483.574.006-.005.016-.014.057-.049q.075-.064.208-.184a26.968 26.968 0 0 0 2.94-3.132c1.584-1.991 3.287-4.778 3.287-7.651 0-2.036-1-3.815-2.249-4.968C13.478 1.65 11.768 1 9.997 1s-3.482.649-4.752 1.82C3.995 3.977 3 5.755 3 7.79c0 2.873 1.704 5.66 3.288 7.652a27 27 0 0 0 2.942 3.132l.265.233.016.014.004.004zM6.263 3.924c.98-.905 2.323-1.423 3.734-1.423 1.41 0 2.753.518 3.734 1.423 1.001.924 1.767 2.324 1.767 3.866 0 2.337-1.421 4.78-2.961 6.718A25.5 25.5 0 0 1 10 17.245a25.491 25.491 0 0 1-2.538-2.737C5.922 12.57 4.5 10.126 4.5 7.788c0-1.543.762-2.941 1.763-3.865" clip-rule="evenodd"></path></svg><div class="sc-lmgQwQ cFXRPR">Kamen’-Kashirskiy</div><svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" role="presentation" width="16px" height="16px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" fill-rule="evenodd" d="M3.271 5.256a.9.9 0 0 1 1.273.015l3.277 3.357c.098.1.26.1.358 0l3.277-3.357a.9.9 0 1 1 1.288 1.258l-4.1 4.2a.9.9 0 0 1-1.288 0l-4.1-4.2a.9.9 0 0 1 .015-1.273" clip-rule="evenodd"></path></svg></div></span></div><div><div role="presentation" class="sc-f189bbb0-1 hWBGjU"><div tabindex="0" role="combobox" aria-label="Filter by date" aria-expanded="false" class="sc-iJCRrD bmkNyV"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="presentation" width="20px" height="20px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" d="M6 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2M7 13a1 1 0 1 1-2 0 1 1 0 0 1 2 0M10 14a1 1 0 1 0 0-2 1 1 0 0 0 0 2M11 9a1 1 0 1 1-2 0 1 1 0 0 1 2 0M14 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2"></path><path fill="currentColor" fill-rule="evenodd" d="M6.75 1.75a.75.75 0 0 0-1.5 0V3H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-1.25V1.75a.75.75 0 0 0-1.5 0V3h-6.5zm6.5 4V4.5h-6.5v1.25a.75.75 0 0 1-1.5 0V4.5H4a.5.5 0 0 0-.5.5v10a.5.5 0 0 0 .5.5h12a.5.5 0 0 0 .5-.5V5a.5.5 0 0 0-.5-.5h-1.25v1.25a.75.75 0 0 1-1.5 0" clip-rule="evenodd"></path></svg><div class="sc-lmgQwQ cFXRPR">All dates</div><svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" role="presentation" width="16px" height="16px" fill="currentColor" class="sc-hKFxyK lcCPsN"><path fill="currentColor" fill-rule="evenodd" d="M3.271 5.256a.9.9 0 0 1 1.273.015l3.277 3.357c.098.1.26.1.358 0l3.277-3.357a.9.9 0 1 1 1.288 1.258l-4.1 4.2a.9.9 0 0 1-1.288 0l-4.1-4.2a.9.9 0 0 1 .015-1.273" clip-rule="evenodd"></path></svg></div></div></div></div></div></div></div></section><div class="sc-5f8292b3-1 xcuUM"></div><section class="sc-17678670-0 sc-17678670-2 jQSgWy hhVspX"><div class="sc-93aad5f1-0 iCpjeZ"><div class="sc-b093cfc3-1 YyBmy"><div class="sc-b093cfc3-0 jdEEtP"><div class="sc-5f8292b3-0 bCXHEb"><div tabindex="0" role="checkbox" aria-checked="true" class="sc-iJCRrD fpIhhf"><div class="sc-lmgQwQ cFXRPR">All types</div></div><div tabindex="0" role="checkbox" aria-checked="false" class="sc-iJCRrD hdnwBH"><div class="sc-lmgQwQ cFXRPR">Sports</div></div><div tabindex="0" role="checkbox" aria-checked="false" class="sc-iJCRrD hdnwBH"><div class="sc-lmgQwQ cFXRPR">Concerts</div></div><div tabindex="0" role="checkbox" aria-checked="false" class="sc-iJCRrD hdnwBH"><div class="sc-lmgQwQ cFXRPR">Theater &amp; Comedy</div></div></div></div></div></div></section></section><div class="sc-214855ce-0 bcFtHL"><img alt="Spotify Logo" src="https://img.vggcdn.net/img/spotify/Spotify_Logo_RGB_Green.png" class="sc-5a8f775c-6 jVKHIM"><div class="sc-214855ce-1 eblAsx"><p>Connect your Spotify account and sync your favorite artists</p><p>Discover events from who you actually listen to</p></div><a class="sc-jrsJWq kOyZWS sc-2994c035-0 idhUzy" href="/Browse/Spotify/Redirect">Connect Spotify</a></div><section class="sc-71d62db2-0 bbPDQA"></section><section class="sc-fd697b3d-0 iunAog"><h2 class="sc-iCoGMa biRRDK sc-fd697b3d-1 iRRQLE">Popular categories</h2><div style="overflow-x: hidden; padding: 0px 20px; margin: 0px -20px;"><div class="sc-7f824cb3-0 eTVYee"><div class="sc-7f824cb3-1 cfXLZo"><div data-carousel-index="0" data-index="0"><div class="sc-9633b7fd-0 gsBWZu"><a class="sc-jrsJWq kOyZWS sc-9633b7fd-1 lhqZDJ" href="/concert-tickets/category/1"><div class="sc-9633b7fd-2 daGdIJ"></div><p class="sc-9633b7fd-4 dewRai">Concert Tickets</p></a></div></div><div data-carousel-index="1" data-index="1"><div class="sc-9633b7fd-0 gsBWZu"><a class="sc-jrsJWq kOyZWS sc-9633b7fd-1 lhqZDJ" href="/mlb-tickets/grouping/81"><div class="sc-9633b7fd-2 jrCXlV"></div><p class="sc-9633b7fd-4 dewRai">MLB</p></a></div></div><div data-carousel-index="2" data-index="2"><div class="sc-9633b7fd-0 gsBWZu"><a class="sc-jrsJWq kOyZWS sc-9633b7fd-1 lhqZDJ" href="/nba-tickets/grouping/115"><div class="sc-9633b7fd-2 jTQKod"></div><p class="sc-9633b7fd-4 dewRai">NBA</p></a></div></div><div data-carousel-index="3" data-index="3"><div class="sc-9633b7fd-0 gsBWZu"><a class="sc-jrsJWq kOyZWS sc-9633b7fd-1 lhqZDJ" href="/nfl-tickets/grouping/121"><div class="sc-9633b7fd-2 ceWzPx"></div><p class="sc-9633b7fd-4 dewRai">NFL</p></a></div></div><div data-carousel-index="4" data-index="4"><div class="sc-9633b7fd-0 gsBWZu"><a class="sc-jrsJWq kOyZWS sc-9633b7fd-1 lhqZDJ" href="/nhl-tickets/grouping/144"><div class="sc-9633b7fd-2 crcdEt"></div><p class="sc-9633b7fd-4 dewRai">NHL</p></a></div></div><div data-carousel-index="5" data-index="5"><div class="sc-9633b7fd-0 gsBWZu"><a class="sc-jrsJWq kOyZWS sc-9633b7fd-1 lhqZDJ" href="/mls-tickets/grouping/142"><div class="sc-9633b7fd-2 bQrnAJ"></div><p class="sc-9633b7fd-4 dewRai">MLS</p></a></div></div><div data-carousel-index="6" data-index="6"><div class="sc-9633b7fd-0 gsBWZu"><a class="sc-jrsJWq kOyZWS sc-9633b7fd-1 lhqZDJ" href="/theater-and-arts-tickets/category/174"><div class="sc-9633b7fd-2 dYbNNF"></div><p class="sc-9633b7fd-4 dewRai">Theater Tickets</p></a></div></div></div><button class="sc-e25aa712-0 dzFQfG responsive-carousel-next" aria-label="next page"><svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" role="img" width="24px" height="24px" fill="textPrimary" class="sc-hKFxyK bwxPHh"><path fill="currentColor" fill-rule="evenodd" d="M7.258 3.269a.9.9 0 0 0 .01 1.273l5.368 5.28c.1.098.1.258 0 .356l-5.367 5.28a.9.9 0 0 0 1.262 1.284l6.2-6.1a.9.9 0 0 0 0-1.283l-6.2-6.1a.9.9 0 0 0-1.273.01" clip-rule="evenodd"></path></svg></button></div></div></section><div class="sc-30d37666-0 kaPxWJ"><div class="sc-gtsrHU cJzxJv"><div><div class="sc-gGLxEy gbsVcC"><div span="12" class="sc-ckTSur kZFuFN"><div style="width: 0px; height: 0px; position: absolute;"></div><div class="sc-gGLxEy sc-efaf59f-1 gbsVcC fSedWo"><div class="sc-e85a86ee-13 hDlJkj sc-efaf59f-2 cvEzjp"><div class="sc-ckTSur kosdiF"><div class="sc-b8145763-0 jtSpFF">Concerts</div></div></div><a href="/explore?tlcId=3" class="sc-fujyAr fvcSEr">Explore Concerts</a></div><div wrap="false" class="sc-gGLxEy AjyRH" style="position: relative;"><div class="sc-e85a86ee-15 hCTtPH"><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-20 jeJsPn"><p class="sc-e85a86ee-21 fXJYJq">Uh oh! We didn't find anything. </p><p>Try different dates or locations.</p></div></div></div></div></div></div></div></div><div class="sc-30d37666-0 kaPxWJ"><div class="sc-gtsrHU cJzxJv"><div><div class="sc-gGLxEy gbsVcC"><div span="12" class="sc-ckTSur kZFuFN"><div style="width: 0px; height: 0px; position: absolute;"></div><div class="sc-gGLxEy sc-efaf59f-1 gbsVcC fSedWo"><div class="sc-e85a86ee-13 hDlJkj sc-efaf59f-2 cvEzjp"><div class="sc-ckTSur kosdiF"><div class="sc-b8145763-0 jtSpFF">Sports</div></div></div><a href="/explore?tlcId=2" class="sc-fujyAr fvcSEr">Explore Sports</a></div><div wrap="false" class="sc-gGLxEy AjyRH" style="position: relative;"><div class="sc-e85a86ee-15 hCTtPH"><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-20 jeJsPn"><p class="sc-e85a86ee-21 fXJYJq">Uh oh! We didn't find anything. </p><p>Try different dates or locations.</p></div></div></div></div></div></div></div></div><div class="sc-30d37666-0 kaPxWJ"><div class="sc-gtsrHU cJzxJv"><div><div class="sc-gGLxEy gbsVcC"><div span="12" class="sc-ckTSur kZFuFN"><div style="width: 0px; height: 0px; position: absolute;"></div><div class="sc-gGLxEy sc-efaf59f-1 gbsVcC fSedWo"><div class="sc-e85a86ee-13 hDlJkj sc-efaf59f-2 cvEzjp"><div class="sc-ckTSur kosdiF"><div class="sc-b8145763-0 jtSpFF">Theater</div></div></div><a href="/explore?tlcId=1" class="sc-fujyAr fvcSEr">Explore Theater</a></div><div wrap="false" class="sc-gGLxEy AjyRH" style="position: relative;"><div class="sc-e85a86ee-15 hCTtPH"><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-20 jeJsPn"><p class="sc-e85a86ee-21 fXJYJq">Uh oh! We didn't find anything. </p><p>Try different dates or locations.</p></div></div></div></div></div></div></div></div><div><div class="sc-b40c06b1-0 fEAevL"><div style="display: flex; align-items: center;"><img src="https://img.vggcdn.net/img/home/email_opt_in_image-1.jpg" alt="" style="width: 100px; height: 60px; border-radius: 200px; border: 2px solid white; object-fit: cover; z-index: 3;"><img src="https://img.vggcdn.net/img/home/email_opt_in_image-2.jpg" alt="" style="width: 100px; height: 60px; border-radius: 200px; border: 2px solid white; margin-left: -33px; object-fit: cover; z-index: 2;"><img src="https://img.vggcdn.net/img/home/email_opt_in_image-3.jpg" alt="" style="width: 100px; height: 60px; border-radius: 200px; border: 2px solid white; margin-left: -33px; object-fit: cover; z-index: 1;"></div><p class="sc-b40c06b1-1 exGmsM">Discover when your favorite artists are on tour </p><button class="sc-hHEiqM hjxpO sc-b40c06b1-2 lnbtQB"><p class="sc-b40c06b1-3 jRXLkU">Subscribe </p></button></div></div><div class="sc-30d37666-0 kaPxWJ"><div class="sc-gtsrHU frENqG"><div class="sc-gGLxEy gbsVcC"><div span="12" class="sc-ckTSur kZFuFN"><div style="width: 0px; height: 0px; position: absolute;"></div><div class="sc-gGLxEy sc-efaf59f-1 gbsVcC fSedWo"><div class="sc-e85a86ee-13 hDlJkj sc-efaf59f-2 cvEzjp"><div class="sc-ckTSur kosdiF"><div class="sc-b8145763-0 jtSpFF"><p class="sc-b380faab-0 gzpmC">Comedy</p></div></div></div><a href="/explore?tlcId=1&amp;catId=1015" class="sc-fujyAr fvcSEr">Explore Comedy</a></div><div wrap="false" class="sc-gGLxEy AjyRH" style="position: relative;"><div class="sc-e85a86ee-15 hCTtPH"><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-16 fYmpaI"><div class="sc-e85a86ee-18 dgbhrp" style="flex-basis: 198px;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div><div class="sc-e85a86ee-18 dgbhrp" style="flex-grow: 1;"></div></div><div class="sc-e85a86ee-20 jeJsPn"><p class="sc-e85a86ee-21 fXJYJq">Uh oh! We didn't find anything. </p><p>Try different dates or locations.</p></div></div></div></div></div></div></div><section class="sc-d59e8bfa-1 gxPEqA"><div class="sc-d59e8bfa-2 gbAENh"><div class="sc-d59e8bfa-3 jywJaU"><p>Download the StubHub app</p><p>Discover your favorite events with ease</p></div><div class="sc-d59e8bfa-4 dDLsly"><a class="sc-jrsJWq kOyZWS sc-f04914e7-0 ejAwhs" href="https://stubhub.go.link/lgTci?webAnonymousId=558E6984-A7F1-450C-AD8A-8F4A4334DEC8&amp;webSiteVisitId=7B9DC7EB-0D5B-473F-89F1-349015296967&amp;webApplicationClientId=3"><img alt="Download on the App Store" class="sc-5a8f775c-6 iqCpsh sc-d59e8bfa-0 laXRgr" src="https://img.vggcdn.net/img/apple-app-store-badge/en.svg" style="max-width: 100%; padding: 6%;"></a><a class="sc-jrsJWq kOyZWS sc-f04914e7-0 ejAwhs" href="https://stubhub.go.link/lgTci?webAnonymousId=558E6984-A7F1-450C-AD8A-8F4A4334DEC8&amp;webSiteVisitId=7B9DC7EB-0D5B-473F-89F1-349015296967&amp;webApplicationClientId=3"><img alt="Get it on Google Play" class="sc-5a8f775c-6 iqCpsh sc-d59e8bfa-0 laXRgr" src="https://img.vggcdn.net/img/google-play-store-badge/en.png"></a><div class="sc-d59e8bfa-5 ecEHDY"><div style="width: 0px; height: 0px; position: absolute;"></div><img alt="Scan this QR code with your phone to be sent to the app store to download the StubHub app" class="sc-5a8f775c-6 kLGnhN sc-d2edb844-0 gkphKa" src="https://img.vggcdn.net/img/app-install/sh-adjust-home-qr-code.webp" loading="lazy"></div></div></div></section></main></div></div></div><div class="sc-fmdNqK eBpkLu"><footer class="sc-ef26e2dc-0 dMzzDf"><div class="sc-1aeafcdb-1 ejPNnv"><div class="sc-lbVvkl buMxsB"><div class="sc-gtsrHU fqdQfx"><div class="sc-gGLxEy Galoy"><div class="sc-ckTSur sc-1aeafcdb-0 VTrgG" style="order: 3;"><p class="sc-1aeafcdb-4 gTfNjx">Live events all over the world</p><button class="sc-e86c81c-0 chLtNs"><div class="sc-gGLxEy sc-1aeafcdb-11 gbsVcC jYXHa-D"><div class="sc-ckTSur sc-1aeafcdb-25 jZIgJr EwdJK"><div style="width: 0px; height: 0px; position: absolute;"></div><div class="sc-1aeafcdb-27 fTCUxs"><div class="sc-hOPeYa sc-dsXzNT bNlmWA jJgiEE sc-1aeafcdb-28 dEgDNg" size="2"></div></div></div><div class="sc-ckTSur kosdiF">United States</div></div></button><button type="button" style="cursor: pointer; width: 100%; text-align: left;"><div class="sc-1aeafcdb-14 dPbrgJ"><div class="sc-1aeafcdb-16 lhKiEu"><svg width="19px" height="17px" viewBox="0 0 19 17" version="1.1" role="img"><title>Language_20x20</title><g id="Page-1" stroke="none" stroke-width="1" fill="none" fill-rule="evenodd"><g id="1280---Footer-Spec" transform="translate(-1127.000000, -108.000000)"><g id="Column-4---Language-and-Region" transform="translate(967.000000, 56.000000)"><g id="Language" transform="translate(159.000000, 51.000000)"><g id="Language_20x20"><rect id="Container" x="0" y="0" width="20" height="20"></rect><path d="M11.0869885,2.7667286 L11.1610498,3.93936529 C9.65513739,4.0257701 7.81594931,4.08748782 5.63114198,4.12451846 C5.59411135,4.50716833 5.56942426,4.8898182 5.54473717,5.28481161 C6.06316603,5.18606326 6.60628197,5.13668908 7.18642855,5.13668908 C7.33455108,5.13668908 7.49501716,5.13668908 7.64313969,5.14903263 C7.70485741,4.93919237 7.76657513,4.72935212 7.81594931,4.50716833 L9.03796018,4.79106984 C8.988586,4.98856655 8.92686828,5.18606326 8.87749411,5.38355996 C9.29717461,5.50699541 9.67982448,5.69214857 10.0501308,5.93901945 C10.9635531,6.55619666 11.4326078,7.39555767 11.4326078,8.46944601 C11.4326078,9.60505208 11.0376143,10.4691002 10.2476275,11.0862774 C9.5193584,11.6417369 8.42078297,12.0243867 6.93955767,12.2218834 L6.49519008,11.1109645 C7.69251386,10.9628419 8.58124905,10.691284 9.17373917,10.3086341 C9.81560346,9.86426651 10.1488792,9.25943284 10.1488792,8.46944601 C10.1488792,7.74117691 9.80325992,7.18571742 9.11202145,6.790724 C8.91452474,6.6796321 8.71702803,6.5932273 8.51953132,6.53150957 C8.149225,7.58071083 7.70485741,8.48178956 7.21111564,9.2470893 C6.10019666,10.8764371 4.7424068,11.7034546 3.12540251,11.7034546 C2.49588176,11.7034546 1.98979645,11.4936143 1.60714658,11.0986209 C1.21215316,10.691284 1.027,10.148168 1.027,9.48161664 C1.027,8.32132348 1.60714658,7.30915286 2.77978328,6.45744831 C3.22415087,6.12417262 3.71789263,5.85261464 4.24866503,5.65511794 C4.26100858,5.14903263 4.29803921,4.64294731 4.34741339,4.14920555 C3.35992985,4.14920555 2.32307214,4.16154909 1.23684025,4.16154909 L1.22449671,2.97656885 C2.38478986,2.97656885 3.47102175,2.9642253 4.48319237,2.9642253 C4.54491009,2.47048354 4.6313149,1.97674177 4.73006326,1.483 L5.98910477,1.75455797 C5.90269996,2.14955139 5.82863869,2.5445448 5.77926451,2.93953821 C7.9270412,2.90250758 9.70451157,2.84078986 11.0869885,2.7667286 Z M7.27283336,6.32166932 L7.18642855,6.32166932 C6.59393843,6.32166932 6.03847894,6.38338704 5.52005009,6.50682249 C5.52005009,7.45727539 5.56942426,8.34601057 5.6928597,9.16068449 C5.82863869,8.98787487 5.96441768,8.80272171 6.11254021,8.605225 C6.5569078,7.93867361 6.95190121,7.18571742 7.27283336,6.32166932 Z M4.23632149,6.98822071 C4.03882478,7.08696906 3.85367162,7.19806096 3.680862,7.3214964 C2.75509619,7.9633607 2.29838505,8.67928626 2.29838505,9.48161664 C2.29838505,10.1728551 2.56994302,10.5308179 3.12540251,10.5308179 C3.61914428,10.5308179 4.1005425,10.3950389 4.56959718,10.1358245 C4.37210048,9.17302803 4.26100858,8.12382678 4.23632149,6.98822071 Z" id="あ" fill="#5C6570"></path><path d="M13.642295,8 L15.4102704,8 L19.0658585,17.491236 L17.2845901,17.491236 L16.3939559,14.97885 L12.6054373,14.97885 L11.7148031,17.491236 L10,17.491236 L13.642295,8 Z M13.0574009,13.7160105 L15.9552853,13.7160105 L14.5329292,9.63504485 L14.4930501,9.63504485 L13.0574009,13.7160105 Z" id="A" fill="#5C6570"></path></g></g></g></g></g></svg><span class="sc-1aeafcdb-18 ecSOOe">English (US)</span></div><div title="UAH Ukrainian Hryvnia" class="sc-1aeafcdb-17 QloQf"><span class="sc-1aeafcdb-24 dGmuma">UAH</span> Ukrainian Hryvnia</div></div></button></div><div class="sc-ckTSur sc-1aeafcdb-0 VTrgG" style="order: -1;"><div class="sc-1aeafcdb-6 drxBdG"><a href="/promise" title="Learn more about our promise ›" class="sc-jrsJWq kOyZWS"><img alt="fan protect gurantee" src="https://img.vggcdn.net/images/Assets/Icons/bfx/fanprotect.724c822d.svg" class="sc-5a8f775c-6 igKcnA"></a></div><ul class="sc-1aeafcdb-8 iughO"><li class="sc-1aeafcdb-7 cdpxHv"><svg xmlns="http://www.w3.org/2000/svg" height="32px" viewBox="0 0 24 24" fill="currentColor"><path fill="#e4eef3" d="M24 12c0 6.627-5.373 12-12 12S0 18.627 0 12 5.373 0 12 0s12 5.373 12 12z"></path><path fill="#0774ca" d="M17.149 9.185c-.267-.073-.607-.073-.607-.073h-5.174V6.215h.559c.304.44.806.725 1.374.725h.011-.001.011c.568 0 1.069-.284 1.37-.718l.004-.006h.559v2.413l.972-.482V5.25h-2.114l-.122.266a.735.735 0 01-.681.451.75.75 0 01-.676-.423l-.002-.004-.098-.29H10.42v2.486h-.607c-.365 0-.729.146-.996.386L6 10.681V16.5h8.551c.291 0 .583-.12.802-.314.097-.098.169-.145.267-.314.165-.26.264-.577.267-.917v-.097c.267-.048.51-.169.705-.337l.048-.049a1.36 1.36 0 00.412-.99v-.579l.05-.049c.267-.265.413-.603.413-.99v-.506c.025-.024.025-.024.049-.024s.024-.025.049-.025c.243-.241.389-.555.389-.917a1.469 1.469 0 00-.841-1.204l-.009-.004zm-.266 1.425a.362.362 0 01-.217.097H12.632v.965h3.886v.193a.503.503 0 01-.122.314l.001-.001a.51.51 0 01-.314.121h-3.427v.966h3.401v.193a.51.51 0 01-.121.314.512.512 0 01-.315.12h-2.989v.966h2.284v.193c0 .24-.195.435-.435.435H6.973v-4.37l2.502-2.293a.584.584 0 01.339-.121h.608v1.376h6.243a.32.32 0 01.315.314c0 .073-.048.145-.097.217z"></path></svg><p class="sc-1aeafcdb-10 estnJ">Buy and sell with confidence</p></li><li class="sc-1aeafcdb-7 cdpxHv"><svg xmlns="http://www.w3.org/2000/svg" height="32px" viewBox="0 0 24 24" fill="currentColor"><path fill="#e4eef3" d="M24 12c0 6.627-5.373 12-12 12S0 18.627 0 12 5.373 0 12 0s12 5.373 12 12z"></path><path fill="#0774ca" d="M17 10.5V12H9V8.5c0-.825.675-1.5 1.5-1.5h3c.825 0 1.5.675 1.5 1.5v3l1-.5V8.5C16 7.125 14.875 6 13.5 6h-3A2.508 2.508 0 008 8.499V12H7v-1.5H6V14c0 .649.425 1.2 1 1.399v2.6h1v-2.5h7.999v2.5h1v-2.6c.575-.199 1-.75 1-1.399v-3.5h-1zm0 3.5c0 .274-.225.5-.5.5h-9a.501.501 0 01-.5-.499V13h10.001v1z"></path></svg><p class="sc-1aeafcdb-10 estnJ">Customer service all the way to your seat</p></li><li class="sc-1aeafcdb-7 cdpxHv"><svg xmlns="http://www.w3.org/2000/svg" height="32px" viewBox="0 0 24 24" fill="currentColor"><path fill="#e4eef3" d="M24 12c0 6.627-5.373 12-12 12S0 18.627 0 12 5.373 0 12 0s12 5.373 12 12z"></path><path fill="#0774ca" d="M17.582 14.019c-.148-.247-.394-.494-.394-.494l-.738-.692-4.155-3.882-1.648.223-.984 1.088a.341.341 0 01-.468.025.344.344 0 01-.024-.47v.001l2.458-2.67a.497.497 0 01.355-.149h.014-.001c.344.025.664.124.983.247.96.42 2.705 1.087 2.779 1.112l.099.025h1.155v4.401l.984.297-.025-5.687h-1.967c-.369-.149-1.844-.717-2.655-1.063a3.675 3.675 0 00-1.267-.321l-.012-.001a1.4 1.4 0 00-1.179.444l-.001.001-.836.964H5.998v5.983l4.55 4.228c.27.247.615.371.958.371h.05c.369-.025.737-.173.983-.47l.172-.173c.221.148.492.223.762.223h.05c.369-.025.737-.173.983-.47l.394-.42h.049c.369-.025.738-.173.984-.47l.344-.37h.098c.345-.025.664-.172.91-.42.442-.371.517-.94.295-1.41zm-.934.766c-.049.075-.148.099-.221.099s-.172-.025-.221-.074l-3.025-2.794-.664.717 2.877 2.695-.148.149c-.05.099-.173.149-.27.149l-.028.001a.405.405 0 01-.293-.125l-2.557-2.374-.664.717 2.533 2.349-.148.173a.383.383 0 01-.294.149l-.027.001a.404.404 0 01-.292-.124l-2.213-2.078-.688.742 1.697 1.582-.148.148c-.172.173-.442.198-.615.025l-4.254-3.956V8.407h2.14l-.664.742c-.492.544-.467 1.36.074 1.854.246.248.59.371.935.346s.664-.172.91-.42l.762-.816.836-.124 4.648 4.327a.344.344 0 01.024.47v-.001z"></path></svg><p class="sc-1aeafcdb-10 estnJ">Every order is 100% guaranteed</p></li></ul></div><div class="sc-ckTSur sc-1aeafcdb-0 cohOuH"><p class="sc-1aeafcdb-4 gTfNjx">Our Company</p><ul class="sc-1aeafcdb-8 iughO"><li class="sc-1aeafcdb-3 iUnqbR"><a href="/about" title="About Us" class="sc-pNWdL htwqAn">About Us</a></li><li class="sc-1aeafcdb-3 iUnqbR"><a href="/partners" title="Partners" class="sc-pNWdL htwqAn">Partners</a></li><li class="sc-1aeafcdb-3 iUnqbR"><a href="/affiliates" title="Affiliate Program" class="sc-pNWdL htwqAn">Affiliate Program</a></li><li class="sc-1aeafcdb-3 iUnqbR"><a href="https://investors.stubhub.com" title="Investors" class="sc-pNWdL htwqAn">Investors</a></li><li class="sc-1aeafcdb-3 iUnqbR"><a href="/careers" title="Careers" class="sc-pNWdL htwqAn">Careers</a></li></ul></div><div class="sc-ckTSur sc-1aeafcdb-0 cohOuH"><p class="sc-1aeafcdb-4 gTfNjx">Have Questions?</p><ul class="sc-1aeafcdb-8 iughO"><li class="sc-1aeafcdb-3 iUnqbR"><a href="/helpCenter" title="Help Center" class="sc-pNWdL htwqAn">Help Center</a></li><li class="sc-1aeafcdb-3 iUnqbR"><a href="/gift-cards" title="Gift Cards" class="sc-pNWdL htwqAn">Gift Cards</a></li></ul></div></div></div><hr><div class="sc-gGLxEy sc-1aeafcdb-9 jsEgoa eBqfXo"><div class="sc-ckTSur sc-1aeafcdb-2 iGPYuD dnUwEh"><span>© 2000-2025 StubHub. All Rights Reserved. Use of this website signifies your agreement to our  <a href="/legal?section=ua" rel="nofollow" data-modal="true">User Agreement</a>, <a href="/legal?section=pp" rel="nofollow">Privacy Notice</a> and <a href="/legal?section=cn" rel="nofollow">Cookie Notice</a>. You are buying tickets from a third party; StubHub is not the ticket seller. Prices are set by sellers and may be above face value. <a href="/legal?section=ua" rel="nofollow" data-modal="true">User Agreement change notifications</a></span><button class="sc-hHEiqM jvZTXz sc-1aeafcdb-30 cQexbb">&nbsp; Do Not Share My Personal Information/Your Privacy Choices</button></div></div></div></div></footer></div></div><section class="Toastify" aria-live="polite" aria-atomic="false" aria-relevant="additions text" aria-label="Notifications Alt+T"></section><div class="sc-cvdZrT ldhwSP"><div class="sc-fTZpSq fqBAKg"></div></div></div>
    <div id="modal-root"></div>




            <script nomodule="" crossorigin="" src="https://ws.vggcdn.net/scripts/d/nm/runtime.0b20b8b0.js"></script>
            <script nomodule="" crossorigin="" src="https://ws.vggcdn.net/scripts/d/nm/vendors.791aec31.chunk.js"></script>
            <script nomodule="" crossorigin="" src="https://ws.vggcdn.net/scripts/d/nm/viagogo-upgrade-browser.bcdf2345.chunk.js"></script>
            <script nomodule="" crossorigin="" src="https://ws.vggcdn.net/scripts/d/nm/vgo-web-vitals.20c6f947.chunk.js"></script>



            <script type="application/ld+json">{"@context":"http://schema.org","@type":"Organization","name":"StubHub","url":"https://www.stubhub.com/","logo":"https://media.stubhubstatic.com/stubhub-product/image/upload/v1621550995/GraphicsIllustrationsMarks/StubhubLogoDefault.svg","sameAs":["https://www.facebook.com/StubHub","https://www.twitter.com/stubhub","https://www.instagram.com/stubhub/","https://en.wikipedia.org/wiki/StubHub"]}</script>
            <script type="application/ld+json">{"@context":"http://schema.org","@type":"WebSite","url":"https://www.stubhub.com/","potentialAction":{"@type":"SearchAction","target":{"@type":"EntryPoint","urlTemplate":"https://www.stubhub.com/secure/search/?q={search_term}"},"query-input":"required name=search_term"}}</script>
<script>
    (function () {
        function uuidv4() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
        function getSessionId() {
            var sessionId = sessionStorage.getItem('_ppc_sid');
            if (!sessionId) {
                sessionId = uuidv4();
                sessionStorage.setItem('_ppc_sid', sessionId);
            }
            return sessionId;
        }
        function getAnonId() {
            var anonId = localStorage.getItem('_ppc_aid');
            if (!anonId) {
                anonId = uuidv4();
                localStorage.setItem('_ppc_aid', anonId);
            }
            return anonId;
        }
        function outputImg(src) {
            var img = document.createElement("img");
            img.src = src;
            img.style.height = "1px";
            img.style.width = "1px";
            // This next line will just add it to the <body> tag
            document.body.appendChild(img);
        }

        var url = location.href;
        var glcid = url.toLowerCase().indexOf('gclid=');
        if (glcid > -1) {
            var queryStringStart = url.indexOf('?');
            if (queryStringStart > -1) {
                var query = url.substring(queryStringStart);
                var sid = getSessionId();
                var anid = getAnonId();
                query += '&sId=' + sid;
                query += '&anId=' + anid;
                query += '&ref=' + window.location.hostname;

                outputImg('https://fa-ppctelemetry-prod.azurewebsites.net/vis' + query);
            }
        }
    })();
</script>

<script async="" src="https://www.googletagmanager.com/gtag/js?id=AW-1039308173"></script><iframe height="0" width="0" style="display: none; visibility: hidden;"></iframe><div id="batBeacon554191770993" style="width: 0px; height: 0px; display: none; visibility: hidden;"><img id="batBeacon354380362891" width="0" height="0" alt="" src="https://bat.bing.com/action/0?ti=4031192&amp;Ver=2&amp;mid=fd8e6394-4d7b-46db-b2a7-ae983df3f5fc&amp;bo=2&amp;sid=d51d7e30c3d711f09716f5dea1cc71fa&amp;vid=d51d8e90c3d711f097170fda024c531c&amp;vids=1&amp;msclkid=N&amp;uach=pv%3D10.0&amp;pi=918639831&amp;lg=en-US&amp;sw=1280&amp;sh=720&amp;sc=24&amp;nwd=1&amp;tl=Buy%20sports,%20concert%20and%20theater%20tickets%20on%20StubHub!&amp;kw=StubHub,%20buy%20tickets,%20sell%20tickets,%20concert,%20sport,%20theater&amp;p=https%3A%2F%2Fwww.stubhub.com%2F&amp;r=&amp;lt=3131&amp;evt=pageLoad&amp;sv=2&amp;asc=G&amp;cdb=AQAQ&amp;rn=474180" style="width: 0px; height: 0px; display: none; visibility: hidden;"></div></body></html>
    """

    print("=" * 80)
    print("ORIGINAL HTML LENGTH:", len(messy_html))
    print("=" * 80)

    # Clean as HTML
    cleaner = HTMLCleaner()
    cleaned = cleaner.clean(messy_html)

    print("\n" + "=" * 80)
    print("CLEANED HTML:")
    print("=" * 80)
    print(cleaned)
    print(
        f"\nLength: {len(cleaned)} (reduced by {100 * (1 - len(cleaned) / len(messy_html)):.1f}%)"
    )

    # Clean as text tree
    # text_tree = cleaner.clean_to_text_tree(messy_html)

    # print("\n" + "=" * 80)
    # print("TEXT TREE FORMAT:")
    # print("=" * 80)
    # print(text_tree)

    # # Get interactive elements
    # elements = get_interactive_elements(messy_html)

    # print("\n" + "=" * 80)
    # print("INTERACTIVE ELEMENTS:")
    # print("=" * 80)
    # for i, elem in enumerate(elements, 1):
    #     print(f"{i}. {elem['tag']}: {elem['text'][:50]}")
    #     print(f"   Attributes: {elem['attributes']}")
