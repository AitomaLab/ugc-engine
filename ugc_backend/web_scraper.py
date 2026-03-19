"""
UGC Engine — Web Scraper Client

Scrapes a product's website URL to extract key marketing copy (benefits,
features, taglines) for use in AI script generation.

Dependencies: requests, beautifulsoup4 (both already in requirements.txt)
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional


class WebScraperClient:
    """Fetches and extracts the most relevant marketing text from a product URL."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    MAX_CHARS = 3000  # Cap to avoid exceeding LLM context limits

    def scrape(self, url: str) -> Optional[str]:
        """
        Fetches the URL and returns a clean, condensed string of the most
        relevant marketing content on the page.

        Returns None if the URL is unreachable or parsing fails.
        """
        if not url or not url.startswith("http"):
            return None
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove noise: scripts, styles, nav, footer, cookie banners
            for tag in soup(["script", "style", "nav", "footer", "header",
                              "aside", "form", "noscript", "iframe"]):
                tag.decompose()

            # Priority 1: Extract from semantic marketing elements
            priority_text = []
            for selector in ["h1", "h2", "h3", "[class*='hero']", "[class*='benefit']",
                              "[class*='feature']", "[class*='tagline']", "[class*='headline']"]:
                for el in soup.select(selector)[:5]:
                    text = el.get_text(strip=True)
                    if text and len(text) > 10:
                        priority_text.append(text)

            # Priority 2: All paragraph text as fallback
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 30]

            combined = "\n".join(priority_text + paragraphs)

            # Clean up whitespace
            combined = re.sub(r'\n{3,}', '\n\n', combined).strip()

            return combined[:self.MAX_CHARS] if combined else None

        except requests.RequestException as e:
            print(f"      !! WebScraperClient: Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            print(f"      !! WebScraperClient: Parsing error for {url}: {e}")
            return None
