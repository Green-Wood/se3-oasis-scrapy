from typing import List

from fastapi import FastAPI, BackgroundTasks, status
from scrapy.crawler import CrawlerProcess
from pydantic import BaseModel
from fastapi.responses import JSONResponse
import uvicorn
from ieee.spiders.conference_crawler import ConferenceCrawler
from scrapy.utils.project import get_project_settings
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
process = CrawlerProcess(get_project_settings())

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Proceeding(BaseModel):
    proceedings: List[str]


def crawl(proceedings: List[str]):
    process.crawl(ConferenceCrawler, proceedings=proceedings)
    process.start()


@app.post("/crawl")
async def crawl(proceeding: Proceeding, background_tasks: BackgroundTasks):
    background_tasks.add_task(crawl, proceeding.proceedings)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={'message': 'task successfully created'})


@app.get("/health")
def health():
    return {"message": "healthy"}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
