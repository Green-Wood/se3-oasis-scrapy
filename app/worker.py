from scrapy.crawler import CrawlerRunner
from ieee.spiders.conference_crawler import ConferenceCrawler
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor
from billiard import Process
from typing import List
from celery import Celery

celery_app = Celery('worker', broker='redis://localhost:6379/0')


class CrawlerScriptProcess(Process):
    def __init__(self, proceedings: List[str]):
        Process.__init__(self)
        self.proceedings = proceedings
        self.runner = CrawlerRunner(get_project_settings())

    def run(self):
        d = self.runner.crawl(ConferenceCrawler, proceedings=self.proceedings)
        d.addBoth(lambda _: reactor.stop())
        reactor.run()


@celery_app.task
def crawl_proceedings(proceedings: List[str]):
    crawler = CrawlerScriptProcess(proceedings)
    crawler.start()
    crawler.join()
