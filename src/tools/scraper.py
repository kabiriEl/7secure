"""Scraping tools for SafariNewsletter.

Ce module :
- lit une liste de flux RSS/Atom (~100 sources),
- récupère les derniers articles,
- télécharge le HTML des pages (avec timeout court),
- renvoie une liste d'articles bruts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import requests

# Liste de flux RSS/Atom issus du document de spécification (~100 sources)
FEED_URLS: List[str] = [
    # A. High-value independent research & journalism
    "https://krebsonsecurity.com/feed/",
    "https://thehackernews.com/feeds/posts/default?alt=rss",
    "https://www.bleepingcomputer.com/rss/",
    "https://arstechnica.com/feed/",
    "https://www.wired.com/feed/category/security/latest/rss",
    "https://www.darkreading.com/rss.xml",
    "https://www.theregister.com/headlines.atom",
    "https://threatpost.com/feed/",
    "https://www.vice.com/en/topic/cybersecurity/rss",
    "https://techcrunch.com/tag/security/feed/",
    "https://www.schneier.com/blog/atom.xml",
    "https://netlas.io/blog/rss.xml",
    "https://podcast.darknetdiaries.com/rss",

    # B. Vendor & commercial research blogs
    "https://blog.talosintelligence.com/atom.xml",
    "https://unit42.paloaltonetworks.com/feed/",
    "https://www.crowdstrike.com/blog/feed/",
    "https://www.mandiant.com/resources/rss.xml",
    "https://www.microsoft.com/security/blog/feed/",
    "https://cloud.google.com/blog/topics/security/rss.xml",
    "https://www.trendmicro.com/vinfo/us/security/news.rss",
    "https://news.sophos.com/en-us/feed/",
    "https://research.checkpoint.com/feed/",
    "https://www.bitdefender.com/blog/api/rss/labs/",
    "https://www.kaspersky.com/blog/rss.xml",
    "https://www.fortinet.com/blog.rss",
    "https://www.akamai.com/blog/security/rss.xml",
    "https://www.rapid7.com/blog/rss.xml",
    "https://blogs.vmware.com/security/feed/",
    "https://www.splunk.com/en_us/blog/security.html?format=rss",
    "https://www.f5.com/services/resources/rss.xml",
    "https://nakedsecurity.sophos.com/feed/",
    "https://www.elastic.co/blog/tag/security?format=rss",

    # C. CERTs / Government / Standards
    "https://www.cisa.gov/uscert/ncas/alerts.xml",
    "https://www.ncsc.gov.uk/rss.xml",
    "https://www.enisa.europa.eu/feed/",
    "https://www.ssi.gouv.fr/feed/",
    "https://csrc.nist.gov/feeds/news.xml",
    "https://cert.europa.eu/rss",
    "https://www.cyber.gov.au/news-and-events/rss-feeds",
    "https://cyber.gc.ca/en/rss",
    "https://www.cert.govt.nz/rss",

    # D. Threat-intel and feeds (IoCs)
    "https://abuse.ch/feeds/",
    "https://otx.alienvault.com/feeds/",
    "https://www.team-cymru.org/Resources/",
    "https://blog.virustotal.com/atom.xml",
    "https://www.shadowserver.org/feed/",
    "https://urlhaus.abuse.ch/downloads/rss/",
    "https://rules.emergingthreats.net/rss",
    "https://blog.malwarebytes.com/feed/",
    "https://isc.sans.edu/rssfeed.xml",
    "https://umbrella.cisco.com/blog/rss.xml",
    "https://www.greynoise.io/blog/rss.xml",

    # E. Academic / standards / crypto research
    "https://eprint.iacr.org/rss/",
    "https://export.arxiv.org/rss/cs.CR",
    "https://export.arxiv.org/rss/cs.CC",
    "https://cryptomator.org/blog/feed/",
    "https://research.google/blog/rss/",

    # F. AI security / model safety / alignment
    "https://openai.com/blog/rss/",
    "https://www.anthropic.com/index.rss",
    "https://www.centerforaisafety.org/rss",
    "https://www.alignmentforum.org/feeds.rss",
    "https://deepmind.com/blog/rss.xml",
    "https://huggingface.co/blog/rss.xml",

    # G. Cryptography & engineering blogs
    "https://blog.cloudflare.com/tag/security/rss/",
    "https://letsencrypt.org/feed/",
    "https://www.eff.org/rss/",
    "https://aws.amazon.com/blogs/security/feed/",

    # H. Newsletters, aggregators & topic collections
    "https://rss.feedspot.com/ai_rss_feeds/",
    "https://rss.feedspot.com/cyber_security_rss_feeds/",
    "https://hnrss.org/frontpage",
    "https://www.reddit.com/r/cybersecurity/.rss",
    "https://security.stackexchange.com/feeds",
    "https://medium.com/feed/tag/cybersecurity",

    # I. Regional / specialized security sources
    "https://www.zdnet.com/topic/security/rss.xml",
    "https://www.securityweek.com/rss.xml",
    "https://www.csoonline.com/index.rss",
    "https://portswigger.net/daily-swig/rss.xml",
    "https://www.bankinfosecurity.com/rss",

    # J. Podcasts, interviews & long-form
    "https://risky.biz/feed/",
    "https://www.recordedfuture.com/blog/rss.xml",
    "https://www.smashingsecurity.com/rss",
    "https://www.thecyberwire.com/rss/news.xml",

    # K. Misc / GitHub curated / others
    "https://security.stackexchange.com/feeds/tag?tagnames=cve",
    "https://github.blog/changelog/",
    "https://snyk.io/blog/rss.xml",
    "https://owasp.org/feed.xml",
]

# Certains sites ont un flux avec contenu suffisant (on n'a pas besoin de re-télécharger la page)
RSS_ONLY_DOMAINS = {
    "www.bleepingcomputer.com",
    "arstechnica.com",
    "www.wired.com",
    "www.securityweek.com",
    "www.csoonline.com",
    "www.bankinfosecurity.com",
}


def scrape_sources(
    max_items_per_feed: int = 1,
    feed_timeout: int = 10,
    page_timeout: int = 10,
) -> List[Dict[str, Any]]:
    """Scraper tous les flux et retourner une liste d'articles bruts.

    Chaque élément de la liste contient :
    - title
    - url
    - published (iso)
    - summary_html (le summary du flux)
    - html (le HTML complet de la page ou le summary si RSS-only)
    """
    articles: List[Dict[str, Any]] = []

    for feed_url in FEED_URLS:
        print(f"[SCRAPING] Lecture du flux : {feed_url}")
        feed_items = _fetch_rss_feed(feed_url, max_items_per_feed, feed_timeout)

        for item in feed_items:
            url = item.get("link")
            title = item.get("title", "")
            published = item.get("published")
            summary_html = item.get("summary", "")

            if not url:
                continue

            domain = urlparse(url).netloc.lower()

            try:
                if domain in RSS_ONLY_DOMAINS and summary_html:
                    html = summary_html
                else:
                    html = _fetch_web_page(url, timeout=page_timeout)

                articles.append(
                    {
                        "title": title,
                        "url": url,
                        "published": published,
                        "summary_html": summary_html,
                        "html": html,
                    }
                )
                print(f"  -> Article récupéré : {title!r}")

            except Exception as exc:
                print(f"  !! Échec pour {url} : {exc}")

    print(f"[SCRAPING] Total articles bruts : {len(articles)}")
    return articles


def _fetch_rss_feed(feed_url: str, limit: int, timeout: int) -> List[Dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/110.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(feed_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  !! Impossible de lire le flux {feed_url} : {exc}")
        return []

    feed = feedparser.parse(resp.content)
    items: List[Dict[str, Any]] = []
    for entry in feed.entries[:limit]:
        items.append(
            {
                "title": entry.get("title", ""),
                "link": entry.get("link"),
                "published": _parse_date(entry.get("published")),
                "summary": entry.get("summary", "") or entry.get("description", ""),
            }
        )
    return items


def _fetch_web_page(url: str, timeout: int) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/110.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _parse_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    try:
        dt = datetime(*feedparser._parse_date(date_str)[:6])  # type: ignore[attr-defined]
        return dt.isoformat()
    except Exception:
        return None




























# """Scraping tools for SafariNewsletter.

# Ce module :
# - lit une liste de flux RSS/Atom,
# - récupère les derniers articles,
# - télécharge le HTML des pages (avec timeout court),
# - renvoie une liste d'articles bruts.
# """

# from datetime import datetime
# from typing import Any, Dict, List, Optional
# from urllib.parse import urlparse

# import feedparser
# import requests

# # Liste de flux. Tu peux la réduire ou l'étendre.
# FEED_URLS: List[str] = [
#     # "https://krebsonsecurity.com/feed/",
#     "https://www.bleepingcomputer.com/rss/",
#     "https://arstechnica.com/feed/",
#     "https://www.wired.com/feed/category/security/latest/rss",
#     "https://www.darkreading.com/rss.xml",
#     "https://www.securityweek.com/rss.xml",
#     "https://www.csoonline.com/index.rss",
#     "https://portswigger.net/daily-swig/rss.xml",
#     "https://www.bankinfosecurity.com/rss",
# ]

# # Certains sites ont un flux avec contenu suffisant (on n'a pas besoin de re-télécharger la page)
# RSS_ONLY_DOMAINS = {
#     "www.bleepingcomputer.com",
#     "arstechnica.com",
#     "www.wired.com",
#     "www.securityweek.com",
#     "www.csoonline.com",
#     "www.bankinfosecurity.com",
# }


# def scrape_sources(
#     max_items_per_feed: int = 3,
#     feed_timeout: int = 4,
#     page_timeout: int = 4,
# ) -> List[Dict[str, Any]]:
#     """Scraper tous les flux et retourner une liste d'articles bruts.

#     Chaque élément de la liste contient :
#     - title
#     - url
#     - published (iso)
#     - summary_html (le summary du flux)
#     - html (le HTML complet de la page ou le summary si RSS-only)
#     """
#     articles: List[Dict[str, Any]] = []

#     for feed_url in FEED_URLS:
#         print(f"[SCRAPING] Lecture du flux : {feed_url}")
#         feed_items = _fetch_rss_feed(feed_url, max_items_per_feed, feed_timeout)

#         for item in feed_items:
#             url = item.get("link")
#             title = item.get("title", "")
#             published = item.get("published")
#             summary_html = item.get("summary", "")

#             if not url:
#                 continue

#             domain = urlparse(url).netloc.lower()

#             try:
#                 if domain in RSS_ONLY_DOMAINS and summary_html:
#                     html = summary_html
#                 else:
#                     html = _fetch_web_page(url, timeout=page_timeout)

#                 articles.append(
#                     {
#                         "title": title,
#                         "url": url,
#                         "published": published,
#                         "summary_html": summary_html,
#                         "html": html,
#                     }
#                 )
#                 print(f"  -> Article récupéré : {title!r}")

#             except Exception as exc:
#                 print(f"  !! Échec pour {url} : {exc}")

#     print(f"[SCRAPING] Total articles bruts : {len(articles)}")
#     return articles


# def _fetch_rss_feed(feed_url: str, limit: int, timeout: int) -> List[Dict[str, Any]]:
#     headers = {
#         "User-Agent": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) "
#             "Chrome/110.0 Safari/537.36"
#         )
#     }

#     try:
#         resp = requests.get(feed_url, headers=headers, timeout=timeout)
#         resp.raise_for_status()
#     except requests.RequestException as exc:
#         print(f"  !! Impossible de lire le flux {feed_url} : {exc}")
#         return []

#     feed = feedparser.parse(resp.content)
#     items: List[Dict[str, Any]] = []
#     for entry in feed.entries[:limit]:
#         items.append(
#             {
#                 "title": entry.get("title", ""),
#                 "link": entry.get("link"),
#                 "published": _parse_date(entry.get("published")),
#                 "summary": entry.get("summary", "") or entry.get("description", ""),
#             }
#         )
#     return items


# def _fetch_web_page(url: str, timeout: int) -> str:
#     headers = {
#         "User-Agent": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) "
#             "Chrome/110.0 Safari/537.36"
#         )
#     }
#     resp = requests.get(url, headers=headers, timeout=timeout)
#     resp.raise_for_status()
#     return resp.text


# def _parse_date(date_str: Optional[str]) -> Optional[str]:
#     if not date_str:
#         return None
#     try:
#         dt = datetime(*feedparser._parse_date(date_str)[:6])  # type: ignore[attr-defined]
#         return dt.isoformat()
#     except Exception:
#         return None
