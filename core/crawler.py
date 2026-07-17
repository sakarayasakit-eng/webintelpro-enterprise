import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque

from core.logger import Logger
from core.config import Config


class Crawler:

    def __init__(self, start_url):

        self.start_url = start_url
        self.config = Config()
        self.logger = Logger()

        self.timeout = self.config.get("crawler", "timeout")
        self.max_pages = self.config.get("crawler", "max_pages")
        self.user_agent = self.config.get("crawler", "user_agent")

        self.domain = urlparse(start_url).netloc

        self.visited = set()
        self.queue = deque([start_url])

        self.headers = {
            "User-Agent": self.user_agent
        }

    def crawl(self):

        pages = []

        while self.queue and len(self.visited) < self.max_pages:

            url = self.queue.popleft()

            if url in self.visited:
                continue

            self.logger.info(f"Crawling {url}")

            try:

                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                )

                if response.status_code != 200:
                    continue

                html = response.text

                pages.append({
                    "url": url,
                    "html": html
                })

                self.visited.add(url)

                soup = BeautifulSoup(html, "lxml")

                for a in soup.find_all("a", href=True):

                    link = urljoin(url, a["href"])

                    parsed = urlparse(link)

                    if parsed.netloc == self.domain:

                        clean = parsed.scheme + "://" + parsed.netloc + parsed.path

                        if clean not in self.visited:
                            self.queue.append(clean)

            except Exception as e:

                self.logger.error(str(e))

        self.logger.info(f"Discovered {len(pages)} pages")

        return pages