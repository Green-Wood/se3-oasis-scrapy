import json
import re
import logging
import random
import re

import scrapy
from pymongo import MongoClient
# from crawlab import save_item
from ieee.spiders.utils import get_keywords

client = MongoClient("mongodb://se3-shard-mongos-0.se3-shard-svc.mongodb.svc.cluster.local,se3-shard-mongos-1.se3-shard-svc.mongodb.svc.cluster.local")
db = client['oasis']
collection = db['large']


class IEEESpider(scrapy.Spider):
    name = "ieee"
    base_url = "https://ieeexplore.ieee.org/document/"
    pattern = '[^A-Z]+'

    def start_requests(self):

        start = 1000000
        end = 9080201

        while True:
            link_num = random.randrange(start, end)
            if collection.find_one({'ieeeId': link_num}):
                continue
            link_num = str(link_num)
            url = self.base_url + link_num
            yield scrapy.Request(url=url, callback=self.parse_paper, meta={'link_num': link_num})

    def parse_paper(self, response):
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

                # 如果会议名不全是大写字母的话
                if not re.search(self.pattern, publication_name):
                    paper['publicationName'] = publication_name

                    ref_url = "https://ieeexplore.ieee.org/rest/document/" + response.meta['link_num'] + "/references"
                    yield scrapy.Request(url=ref_url, callback=self.parse_reference, meta={'item': paper})

    def parse_reference(self, response):
        content = json.loads(response.text)
        paper = response.meta['item']

        if 'references' in content:
            refs = []
            for r in content['references']:
                if 'title' in r and 'googleScholarLink' in r and r['title'] and r['title'] != '':
                    refs.append({
                        'title': r['title'],
                        'googleScholarLink': r['googleScholarLink']
                    })

            logging.log(logging.INFO, 'insert to DB, ieeeId: {}'.format(paper['ieeeId']))
            paper['references'] = refs
            # save_item({'ieeeId': paper['ieeeId']})
            collection.insert_one(paper)




