import json
import logging
import random
import re
import os

import scrapy
from pymongo import MongoClient
from ieee.spiders.utils import get_keywords
from datetime import datetime, timedelta


collection_name = os.getenv('COLLNAME', 'test_conf')
url = os.getenv('MONGOHOST', 'mongodb://localhost')

client = MongoClient(url)
db = client['oasis']
collection = db[collection_name]
task_coll = db['task']


class ConferenceCrawler(scrapy.Spider):
    name = "conferences"
    pattern = '[^A-Z]+'
    header = {'Origin': 'https://ieeexplore.ieee.org'}
    header_with_contentType = {'Content-Type': 'application/json', 'Origin': 'https://ieeexplore.ieee.org'}
    meta_url = 'https://ieeexplore.ieee.org/rest/publication/home/metadata?pubid='
    proceedings_url = 'https://ieeexplore.ieee.org/rest/search/pub/{}/issue/{}/toc'
    base_url = "https://ieeexplore.ieee.org/document/"
    task_id = None

    def liveness_probe(self, response):
        pass

    def start(self, response):
        """
        初始化爬虫
        :param: response.meta['proceedings'] 需要爬取的论文集编号
        :return:
        """
        now = datetime.utcnow() + timedelta(hours=8)
        proceedings = response.meta['proceedings']

        cursor = db.conferences.find({"proceedings.proceedingId": {"$in": proceedings}})

        proceeding_objs = []
        for conf in cursor:
            for pro_obj in conf['proceedings']:
                if pro_obj['proceedingId'] in proceedings:
                    proceeding_objs.append(pro_obj)

        # 新建任务
        self.task_id = task_coll.insert_one({
            'proceedings': proceeding_objs,
            'start_time': now,
            'end_time': None,
            'is_finished': False,
            'description': None,
            'paper_count': 0
        }).inserted_id

        logging.log(logging.INFO, 'TASK ID: {}'.format(self.task_id))

        logging.log(logging.INFO, 'Now start crawling {}'.format(proceedings))
        for pubid in proceedings:
            url = self.meta_url + pubid
            yield scrapy.Request(url=url, callback=self.parse_metadata, headers=self.header)

    def closed(self, reason):
        """
        结束爬虫任务
        """
        now = datetime.utcnow() + timedelta(hours=8)
        task_coll.update_one(
            filter={'_id': self.task_id},
            update={
                '$set': {
                    'end_time': now,
                    'is_finished': True,
                    'description': reason
                }
            }
        )

    def parse_metadata(self, response):
        """
        获取metadata，比如isnumber
        :param response:
        :return:
        """
        content = json.loads(response.text)
        pubid = content['publicationNumber']
        isnumber = content['currentIssue']['issueNumber']
        url = self.proceedings_url.format(pubid, isnumber)
        body = {
            'punumber': pubid,
            'pageNumber': 1,
            'isnumber': int(isnumber)
        }
        yield scrapy.Request(url=url,
                             callback=self.parse_proceeding,
                             headers=self.header_with_contentType,
                             method='POST',
                             body=json.dumps(body),
                             meta={'body': body, 'url': url}
                             )

    def parse_proceeding(self, response):
        """
        对于每一页上的论文记录进行爬取
        :param response:
        :return:
        """
        content = json.loads(response.text)
        for rec in content['records']:
            link_num: str = rec['articleNumber']

            # 如果已经有论文记录了
            if collection.find_one({'ieeeId': link_num}):
                continue

            url = self.base_url + link_num
            yield scrapy.Request(url=url, callback=self.parse_paper, meta={'link_num': link_num})

        url = response.meta['url']
        body = response.meta['body']
        # 爬取下一页
        if body['pageNumber'] < content['totalPages']:
            body['pageNumber'] += 1
            yield scrapy.Request(url=url,
                                 callback=self.parse_proceeding,
                                 headers=self.header_with_contentType,
                                 method='POST',
                                 body=json.dumps(body),
                                 meta={'body': body, 'url': url}
                                 )

    def parse_paper(self, response):
        """
        解析单独的文章
        :param response:
        :return:
        """
        pattern = re.compile('metadata={.*};')
        search_res = pattern.search(response.text)
        if search_res:
            content = json.loads(search_res.group()[9:-1])

            required = ['title', 'authors', 'abstract',
                        'publicationTitle', 'doi', 'publicationYear', 'metrics',
                        'contentType']
            # contentType: conference, journal, book
            paper = {k: content.get(k, None) for k in required}

            paper['keywords'] = get_keywords(content)

            if paper['publicationYear']:
                paper['publicationYear'] = int(paper['publicationYear'])

            paper['link'] = self.base_url + response.meta['link_num']
            paper['ieeeId'] = int(response.meta['link_num'])

            # 如果没有doi号或者文档类型
            if paper['authors'] and paper['doi'] and paper['contentType'] and paper['contentType'] != 'standards':
                
                for author in paper['authors']:
                    if 'firstName' in author:
                        author.pop('firstName')
                    if 'lastName' in author:
                        author.pop('lastName')
                    if author['affiliation'] in {"", "missing"}:
                        author['affiliation'] = None

                doi = paper['doi']
                right_doi = doi.split('/')[1]
                publication_name = right_doi.split('.')[0]

                paper['publicationName'] = publication_name

                ref_url = "https://ieeexplore.ieee.org/rest/document/" + response.meta['link_num'] + "/references"
                yield scrapy.Request(url=ref_url, callback=self.parse_reference, meta={'item': paper})

    def parse_reference(self, response):
        content = json.loads(response.text)
        paper = response.meta['item']

        if 'references' in content and not collection.find_one({'ieeeId': paper['ieeeId']}):
            refs = []
            for r in content['references']:
                if 'title' in r and 'googleScholarLink' in r and r['title'] and r['title'] != '':
                    refs.append({
                        'title': r['title'],
                        'googleScholarLink': r['googleScholarLink']
                    })

            logging.log(logging.INFO, 'insert to DB, ieeeId: {}'.format(paper['ieeeId']))
            paper['references'] = refs
            collection.insert_one(paper)
            task_coll.update_one(
                filter={'_id': self.task_id},
                update={
                    '$inc': {
                        'paper_count': 1
                    }
                }
            )





