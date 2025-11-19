import re
from typing import Dict


def build_url(host: str, port: int, secure: bool = False) -> str:
    """Build a URL from host, port, and security flag."""
    scheme = "https" if secure else "http"
    return f"{scheme}://{host}:{port}"


def parse_tags(str_with_tags: str) -> Dict[str, str]:
    """the target str contains tags in the format of <tag_name> ... </tag_name>, parse them out and return a dict"""

    tags = re.findall(r"<(.*?)>(.*?)</\1>", str_with_tags, re.DOTALL)
    return {tag: content.strip() for tag, content in tags}
