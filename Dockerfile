FROM python:3.11-slim AS downloader

RUN apt update && \
    apt install -y curl jq git unzip && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /build/db

COPY requirements-common.txt requirements-prod.txt /

RUN pip install --no-cache-dir -r requirements-prod.txt && \
    pip cache purge

COPY downloaders /build/downloaders
COPY download_schemes.py /build/download_schemes.py
COPY schemes.json /build/schemes.json

WORKDIR /build/

ARG COMMAND=full
ARG BUILD_DATE
LABEL build_data=$BUILD_DATE

ENV COMMAND="${COMMAND}"

RUN python download_schemes.py ${COMMAND} -o db/

FROM alpine:3.20 AS archive

COPY --from=downloader /build/db /db

COPY --from=downloader /build/selected_schemes.json /db/schemes.json

WORKDIR /db/

ENTRYPOINT ["cat", "/db/schemes.json"]

