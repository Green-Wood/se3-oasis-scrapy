from typing import List

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from app.worker import crawl_proceedings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Proceeding(BaseModel):
    proceedings: List[str]


@app.post("/crawl")
def crawl(proceeding: Proceeding):
    crawl_proceedings.delay(proceeding.proceedings)
    return {'message': 'task successfully created'}


@app.get("/health")
def health():
    return {"message": "healthy"}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
