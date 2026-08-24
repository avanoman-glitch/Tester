"""
Pet Supplies Deal Alert Bot
----------------------------
Watches Slickdeals' own public search RSS feed (an official, documented
feature of their site, not a scrape) for pet-related deals, and posts new
Amazon listings to a Telegram channel with your Associates tracking tag
attached.

Run manually:      python deal_bot.py
Run on a schedule:  see .github/workflows/deal-bot.yml (runs hourly via
                     GitHub Actions, free, no server needed)
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import feedparser
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("deal_bot")

# ---- Config, edit freely -------------------------------------------------
KEYWORDS = ["dog", "cat", "pet"]        # the niche; change to whatever you picked
LOOKBACK_MINUTES = 75                   # covers the gap since the last hourly run, plus buffer
SLICKDEALS_RSS = "https://slickdeals.net/newsearch.php"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
AMAZON_TAG = os.environ.get("AMAZON_TAG")   # e.g. "yourtag-20"

# Public webpage: rebuilt every run, published free via GitHub Pages.
# This is the "automatic audience" piece — a page search engines can index
# over time, with zero ongoing work once it's turned on.
DEALS_STORE = Path("docs/deals.json")
INDEX_HTML = Path("docs/index.html")
MAX_STORED = 200


# ---- Core ------------------------------------------------------------

def fetch_deals(keyword: str):
    """Pull Slickdeals' own public RSS search feed for one keyword.
    This is a documented, intended-for-syndication feature of their site,
    not a scrape of pages meant only for browsers."""
    params = {"rss": 1, "q": keyword, "searcharea": "deals", "searchin": "first"}
    url = f"{SLICKDEALS_RSS}?{urlencode(params)}"
    feed = feedparser.parse(url)
    if feed.bozo:
        log.warning("Feed parse issue for '%s': %s", keyword, feed.bozo_exception)
    return feed.entries


def is_recent(entry, cutoff) -> bool:
    if not getattr(entry, "published_parsed", None):
        return False
    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return published >= cutoff


def is_amazon(entry) -> bool:
    """Slickdeals' feed sometimes links straight to the retailer and
    sometimes to the Slickdeals deal-thread page instead. Either way the
    title reliably names the store (e.g. 'Amazon has ...' or
    'Amazon [amazon.com] has ...'), so check both title and link."""
    title = entry.get("title", "").lower()
    link = entry.get("link", "")
    return "amazon.com" in urlparse(link).netloc or "amazon" in title


def is_direct_amazon_link(url: str) -> bool:
    return "amazon.com" in urlparse(url).netloc


ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")


def extract_asin(url: str):
    """Pull the ASIN out of a direct Amazon product URL, if present.
    Used so the Chrome extension can match a live product page against
    something this bot already tracked."""
    match = ASIN_RE.search(urlparse(url).path)
    return match.group(1) if match else None


def add_affiliate_tag(url: str, tag: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["tag"] = [tag]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def format_message(title: str, link: str, tagged: bool) -> str:
    note = "" if tagged else "\n<i>(click through to find the Amazon link)</i>"
    return f"🐾 <b>{title}</b>\n{link}{note}"


def send_to_telegram(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID; skipping send.")
        return
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        api_url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    if resp.status_code != 200:
        log.error("Telegram send failed: %s", resp.text)


def load_deals() -> list:
    if DEALS_STORE.exists():
        try:
            return json.loads(DEALS_STORE.read_text())
        except json.JSONDecodeError:
            log.warning("deals.json was unreadable, starting fresh.")
    return []


def save_deals(deals: list):
    DEALS_STORE.parent.mkdir(parents=True, exist_ok=True)
    DEALS_STORE.write_text(json.dumps(deals, indent=2))


def render_page(deals: list):
    """Rebuild the public deals page. Newest first, capped at MAX_STORED."""
    rows = "\n".join(
        f'<li><a href="{d["link"]}" target="_blank" rel="nofollow noopener">{d["title"]}</a>'
        f'<span class="ts">{d["seen_at"]}</span></li>'
        for d in deals
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Today's Pet Supply Deals</title>
<meta name="description" content="Fresh pet supply deals, updated automatically every hour.">
<style>
  body{{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px;background:#fdfaf3;color:#242424;}}
  h1{{font-size:22px;}}
  p.sub{{color:#6b6252;font-size:13px;}}
  ul{{list-style:none;padding:0;}}
  li{{padding:12px 0;border-bottom:1px solid #e6ddc4;}}
  a{{color:#b8842d;text-decoration:none;font-weight:600;}}
  a:hover{{text-decoration:underline;}}
  .ts{{display:block;font-size:11px;color:#8a8068;margin-top:3px;}}
</style>
</head>
<body>
  <h1>🐾 Today's Pet Supply Deals</h1>
  <p class="sub">Updated automatically every hour. Also posted live in our <a href="#">Telegram channel</a> — swap this link for yours.</p>
  <ul>
  {rows}
  </ul>
</body>
</html>"""
    INDEX_HTML.write_text(html)


def run():
    if not AMAZON_TAG:
        log.warning("AMAZON_TAG not set; Amazon links will post without your tracking tag.")

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    seen_links = set()
    posted = 0

    stored_deals = load_deals()
    known_links = {d["link"] for d in stored_deals}

    for keyword in KEYWORDS:
        entries = fetch_deals(keyword)
        log.info("Fetched %d entries for '%s'", len(entries), keyword)

        for entry in entries:
            link = entry.get("link", "")
            title = entry.get("title", "").strip()

            if not link or link in seen_links:
                continue
            if not is_recent(entry, cutoff):
                continue
            if not is_amazon(entry):
                continue  # MVP only monetizes Amazon deals; other retailers need their own affiliate programs

            seen_links.add(link)
            direct = is_direct_amazon_link(link)
            final_link = add_affiliate_tag(link, AMAZON_TAG) if (direct and AMAZON_TAG) else link
            send_to_telegram(format_message(title, final_link, tagged=direct and bool(AMAZON_TAG)))
            posted += 1

            if link not in known_links:
                stored_deals.insert(0, {
                    "title": title,
                    "link": final_link,
                    "asin": extract_asin(link),
                    "seen_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                })
                known_links.add(link)

            time.sleep(1)  # stay well under Telegram's rate limit

    stored_deals = stored_deals[:MAX_STORED]
    save_deals(stored_deals)
    render_page(stored_deals)

    log.info("Done. Posted %d new deal(s). Page now has %d listed.", posted, len(stored_deals))


if __name__ == "__main__":
    run()
