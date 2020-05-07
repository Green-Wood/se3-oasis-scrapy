FROM python:3.7.4

WORKDIR /usr/app

COPY ./requirements.txt ./
RUN pip install -r requirements.txt
COPY ./ ./

ENTRYPOINT ["scrapyrt", "-i", "0.0.0.0", "-p", "9080", "-s", "DOWNLOAD_DELAY=0.5"]
