#!/usr/bin/env python3
"""
NGA BBS CLI - Browse forums, topics, and replies from NGA.cn

Usage:
  python -m nga_client categories              # List all forum categories
  python -m nga_client threads <fid>           # List topics in a forum
  python -m nga_client read <tid>              # Read replies in a topic
  python -m nga_client search <keyword>        # Search for forums
  python -m nga_client login --cookie "..."    # Save auth cookies

Examples:
  python -m nga_client threads 650 --page 1
  python -m nga_client read 46826141
  python -m nga_client search genshin
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required.")
    print("Install with: pip install requests")
    sys.exit(1)

DEFAULT_DOMAIN = "https://bbs.nga.cn"
COOKIE_FILE = os.path.join(os.path.expanduser("~"), ".nga_cookies.json")

DOMAINS = [
    "https://bbs.ngacn.cc",
    "https://bbs.nga.cn",
    "https://nga.178.com",
    "https://nga.donews.com",
    "https://ngabbs.com",
]

# Console-safe output for Windows (GBK terminal)
_CONSOLE_ENCODING = sys.stdout.encoding or "utf-8"


def _safe_print(text="", end="\n", **kwargs):
    """Print text safely, encoding Unicode for Windows GBK consoles."""
    try:
        print(text, end=end, **kwargs)
    except UnicodeEncodeError:
        encoded = text.encode(_CONSOLE_ENCODING, errors="replace").decode(_CONSOLE_ENCODING)
        print(encoded, end=end, **kwargs)


class NGAClient:
    def __init__(self, domain=DEFAULT_DOMAIN, cookie_str=None, insecure=False):
        self.domain = domain
        self.insecure = insecure
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Nga_Official/80023"})
        self.session.verify = not insecure

        if cookie_str:
            self.session.cookies.update(self._parse_cookie(cookie_str))
        self._load_cookies()

        # If first domain fails SSL, try alternatives
        self._domains_to_try = [d for d in DOMAINS if d != domain]

        # Rate limiting: 1 second between requests
        self._last_request_time = 0.0
        self._min_interval = 1.0

    def _enforce_rate_limit(self):
        """Ensure at least 1 second between consecutive API requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.monotonic()

    @staticmethod
    def _parse_cookie(cookie_str):
        cookies = {}
        for part in cookie_str.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k] = v
        return cookies

    def _load_cookies(self):
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r") as f:
                self.session.cookies.update(json.load(f))

    def save_cookies(self):
        with open(COOKIE_FILE, "w") as f:
            json.dump(dict(self.session.cookies), f)
        _safe_print(f"Cookies saved to {COOKIE_FILE}")

    def _clean_js(self, text):
        """Remove JS wrappers and fix JSON edge cases from NGA responses."""
        if text.startswith("window.script_muti_get_var_store="):
            text = text[len("window.script_muti_get_var_store="):]
        if "/*error fill content" in text:
            text = text[:text.index("/*error fill content")]
        text = re.sub(r'/\*\$\s*js\s*\$\*/', '', text)
        # Fix numeric values that should be strings (leading zeros, + prefix)
        text = re.sub(r'"content":\+(\d+),', r'"content":"+\1",', text)
        text = re.sub(r'"content":(0\d+),', r'"content":"\1",', text)
        text = re.sub(r'"subject":\+(\d+),', r'"subject":"+\1",', text)
        text = re.sub(r'"subject":(0\d+),', r'"subject":"\1",', text)
        text = re.sub(r'"author":(0\d+),', r'"author":"\1",', text)
        text = re.sub(r'"alterinfo":"\[(\w|\s)+\]\s+",', '', text)
        # Strip invalid control characters (raw tabs break Python's JSON parser)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        text = text.replace('\t', ' ')
        return text

    def _get(self, url, params=None):
        self._enforce_rate_limit()
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.encoding = "GBK"
            return resp.text
        except requests.exceptions.SSLError:
            # Try alternative domains
            for alt in self._domains_to_try:
                try:
                    alt_url = url.replace(self.domain, alt, 1)
                    resp = self.session.get(alt_url, params=params, timeout=30)
                    resp.encoding = "GBK"
                    # Success — update domain so subsequent requests use the working one
                    self.domain = alt
                    return resp.text
                except requests.exceptions.SSLError:
                    continue
            raise

    def get_categories(self):
        """Fetch forum category tree."""
        url = f"{self.domain}/app_api.php"
        params = {"__lib": "home", "__act": "category"}
        raw = self._get(url, params)
        return json.loads(raw)

    def get_forum_topics(self, fid, page=1, stid=None):
        """Fetch topic list for a given forum."""
        url = f"{self.domain}/thread.php"
        params = {"page": page, "lite": "js", "noprefix": ""}
        if stid:
            params["stid"] = stid
        else:
            params["fid"] = fid
        return json.loads(self._clean_js(self._get(url, params)))

    def read_topic(self, tid, page=1):
        """Fetch replies for a given topic."""
        url = f"{self.domain}/read.php"
        params = {"tid": tid, "page": page, "__output": "8", "noprefix": "", "v2": ""}
        return json.loads(self._clean_js(self._get(url, params)))

    def search_forum(self, keyword):
        """Search forums by keyword."""
        url = f"{self.domain}/forum.php"
        params = {"__output": "8", "key": keyword}
        return json.loads(self._clean_js(self._get(url, params)))


# ── Helpers ──────────────────────────────────────────────────────────────

def strip_html(text):
    if not isinstance(text, str):
        return str(text)
    return re.sub(r'<[^>]+>', '', text)


def unescape(text):
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ')
    text = text.replace('<br/>', '\n')
    text = text.replace('<br>', '\n')
    return text


def fmt_ts(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except (ValueError, TypeError):
        return str(ts)


def wrap_text(text, width=64):
    """Yield wrapped lines."""
    from textwrap import wrap
    for line in text.split('\n'):
        for chunk in wrap(line.strip(), width=width) if line.strip() else ['']:
            yield chunk


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_categories(args, client):
    data = client.get_categories()
    if data.get("code") != 0:
        _safe_print(f"Error: {data.get('msg', 'unknown')}")
        return

    for cat in data.get("result", []):
        _safe_print(f"\n{'=' * 60}")
        _safe_print(f"  {cat['name']}")
        _safe_print(f"{'=' * 60}")
        for group in cat.get("groups", []):
            _safe_print(f"\n  > {group['name']}")
            for forum in group.get("forums", []):
                tag = f"  stid={forum['stid']}" if forum.get("stid") else f" fid={forum['id']}"
                _safe_print(f"    {forum['name']:30s} {tag}")


def cmd_threads(args, client):
    data = client.get_forum_topics(args.fid, args.page, args.stid)
    if "error" in data:
        _safe_print(f"Error: {data.get('error', {}).get('0', 'unknown')}")
        return

    d = data.get("data", {})
    f_info = d.get("__F") or {}
    name = f_info.get("name", f"fid={args.fid}")
    topics = d.get("__T") or {}
    total = d.get("__T__ROWS", 0)
    per_page = d.get("__T__ROWS_PAGE", 1) or 1
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1

    _safe_print(f"## {name} (Page {args.page}/{total_pages}) [{total} topics]")

    items = []
    for i in range(total):
        t = topics.get(str(i))
        if t:
            items.append(t)

    for idx, t in enumerate(items, 1):
        tid = t.get("tid", "?")
        author = t.get("author", "?")
        # Strip "UID:" prefix for cleaner display
        if author.startswith("UID:") and author[4:].isdigit():
            author = author[4:]
        subject = strip_html(t.get("subject", "?"))
        # Strip BBCode from subject
        subject = re.sub(r'\[/?[a-z_]+(?::[^\]]*)?\]', '', subject)
        subject = re.sub(r'\[/?[a-z_]+\]', '', subject)
        replies = t.get("replies", 0)
        postdate = fmt_ts(t.get("postdate", 0))

        _safe_print(f"\n[{idx}] {subject}")
        _safe_print(f"    author={author} replies={replies} date={postdate} tid={tid}")

    _safe_print(f"\n--- Page {args.page}/{total_pages} ---")


def cmd_read(args, client):
    data = client.read_topic(args.tid, args.page)
    if "error" in data:
        _safe_print(f"Error: {data.get('error', {}).get('0', 'unknown')}")
        return

    d = data.get("data", {})
    t_info = d.get("__T")
    if isinstance(t_info, dict):
        subject = strip_html(t_info.get("subject", ""))
        op_name = t_info.get("author") or ""
        op_authorid = str(t_info.get("authorid", ""))
    else:
        subject = ""
        op_name = ""
        op_authorid = ""

    # Build user info map from __U (authorid -> username)
    # Note: __U always returns "UID:xxxxx" for non-OP users (server anonymization)
    user_map = {}
    u_info = d.get("__U") or {}
    for uid_str, u_data in u_info.items():
        if isinstance(u_data, dict) and "username" in u_data:
            user_map[uid_str] = u_data["username"]
        elif isinstance(u_data, str):
            user_map[uid_str] = u_data

    # Override with OP's real name from __T (which has the actual display name)
    if op_name and op_authorid:
        user_map[op_authorid] = op_name

    # Strip "UID:" prefix for users whose display name is just their UID
    for uid_str in user_map:
        name = user_map[uid_str]
        if name.startswith("UID:") and name[4:].isdigit():
            user_map[uid_str] = name[4:]

    replies_raw = d.get("__R") or {}
    r_rows = d.get("__R__ROWS", 0)
    all_rows = d.get("__ROWS", 0)
    total_pages = max(1, (all_rows + 19) // 20) if all_rows else 1

    # Header
    _safe_print(f"# {subject}")
    _safe_print(f"tid={args.tid} | Page {args.page}/{total_pages} | {all_rows} replies\n")

    items = []
    for i in range(r_rows):
        r = replies_raw.get(str(i))
        if r:
            items.append(r)

    for r in items:
        lou = r.get("lou", "?")
        authorid = str(r.get("authorid", ""))
        author = user_map.get(authorid) or r.get("author", "?")
        content = strip_html(unescape(r.get("content", "")))
        postdate = fmt_ts(r.get("postdate", 0))
        pid = r.get("pid", "?")

        # Strip BBCode
        content = re.sub(r'\[quote\].*?\[/quote\]', ' [quote] ', content, flags=re.DOTALL)
        # [uid=X]name[/uid]: keep OP's name, otherwise replace with UID number
        content = re.sub(
            r'\[uid=(\d+)\](.*?)\[/uid\]',
            lambda m: m.group(2) if m.group(1) == op_authorid else m.group(1),
            content,
        )
        content = re.sub(r'\[/?\w+(?::[^\]]*)?(?:=[^\]]*)?\]', '', content)
        # Remove any remaining square-bracket artifacts like [pid=...,46825948,1]
        content = re.sub(r'\[[a-z_/][^\]]*\]', '', content)

        # Collapse repeated newlines
        content = re.sub(r'\n{3,}', '\n\n', content.strip())

        _safe_print(f"## #{lou} {author}")
        _safe_print(f"pid={pid} | {postdate}")
        if content:
            _safe_print(content)
        _safe_print("")  # blank line between posts

    _safe_print(f"--- Page {args.page}/{total_pages} ---")


def cmd_search(args, client):
    data = client.search_forum(args.keyword)
    d = data.get("data", {})
    results = d.get("__T") or {}
    rows = d.get("__T__ROWS", 0)

    if rows == 0:
        f_data = d.get("__F")
        if f_data:
            fid = f_data.get("fid")
            name = f_data.get("name")
            if fid and name:
                _safe_print(f"\n  {name:40s} fid={fid}")
                return
        _safe_print(f"No forums found for '{args.keyword}'")
        return

    _safe_print(f"\n{'=' * 60}")
    _safe_print(f"  Search results for '{args.keyword}':")
    _safe_print(f"{'=' * 60}")
    for i in range(rows):
        r = results.get(str(i))
        if r:
            _safe_print(f"  {r.get('name', '?'):40s} fid={r.get('fid', '?')}")


def cmd_login(args, client):
    if args.cookie:
        client.session.cookies.update(client._parse_cookie(args.cookie))
        client.save_cookies()
        _safe_print("Authentication cookies saved.")
    else:
        _safe_print("Usage: python -m nga_client login --cookie \"ngaPassportUid=xxx; ngaPassportCid=yyy\"")
        _safe_print("You can get these cookies by logging into NGA in your browser and inspecting cookies.")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NGA BBS CLI - Browse forums, topics, and replies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--domain", default=DEFAULT_DOMAIN, choices=DOMAINS,
        help="NGA domain (default: %(default)s)",
    )
    parser.add_argument(
        "--cookie", help="Cookie string, e.g. \"ngaPassportUid=X; ngaPassportCid=Y\"",
    )
    parser.add_argument(
        "--insecure", action="store_true",
        help="Skip SSL verification (use if certificate errors occur)",
    )

    sub = parser.add_subparsers(dest="command", metavar="")

    p = sub.add_parser("categories", aliases=["cat"], help="List forum categories & forums")
    p = sub.add_parser("threads", aliases=["t"], help="List topics in a forum")
    p.add_argument("fid", type=int, help="Forum ID (e.g. 275)")
    p.add_argument("-p", "--page", type=int, default=1, help="Page number")
    p.add_argument("--stid", type=int, help="Sub-forum STID (optional)")

    p = sub.add_parser("read", aliases=["r"], help="Read replies in a topic")
    p.add_argument("tid", type=int, help="Topic ID")
    p.add_argument("-p", "--page", type=int, default=1, help="Page number")

    p = sub.add_parser("search", aliases=["s"], help="Search forums by keyword")
    p.add_argument("keyword", help="Forum name keyword")

    p = sub.add_parser("login", help="Save auth cookies for authenticated requests")
    p.add_argument("--cookie", help="Cookie string")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    client = NGAClient(domain=args.domain, cookie_str=args.cookie, insecure=args.insecure)

    dispatch = {
        "categories": cmd_categories, "cat": cmd_categories,
        "threads": cmd_threads, "t": cmd_threads,
        "read": cmd_read, "r": cmd_read,
        "search": cmd_search, "s": cmd_search,
        "login": cmd_login,
    }
    dispatch[args.command](args, client)


if __name__ == "__main__":
    main()
