from core.crawler import Crawler
from core.logger import Logger
from modules.technical_seo import TechnicalSEO


class AnalysisEngine:

    def __init__(self, url):

        self.url = url
        self.logger = Logger()

    def analyze(self):

        self.logger.info("Starting analysis")

        crawler = Crawler(self.url)

        pages = crawler.crawl()

        seo = TechnicalSEO()

        analyzed_pages = []

        for page in pages:

            analyzed_pages.append({

                "url": page["url"],

                "seo": seo.analyze(page["html"])

            })

        report = {

            "target": self.url,

            "pages_crawled": len(analyzed_pages),

            "pages": analyzed_pages

        }

        self.logger.info("Analysis completed")

        return report