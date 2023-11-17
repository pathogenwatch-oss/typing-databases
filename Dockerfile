FROM python:3.10-slim

RUN apt update && \
    apt install -y curl jq git unzip && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir xlrd==1.2.0 PyYAML==5.1.2 retry && \
    pip cache purge

RUN mkdir -p /db

COPY requirements.txt /db/

COPY bin /db/bin

COPY cgmlst_schemes /db/cgmlst_schemes

COPY mlst_schemes /db/mlst_schemes

COPY other_schemes/other_schemes /db/other_schemes

COPY schemes.json /db/schemes.json

WORKDIR /db/

ARG SCHEME

ARG TYPE

ENV SCHEME=${SCHEME:-IGNORE}

ENV TYPE=${TYPE:-IGNORE}

RUN /db/bin/update -t "${TYPE}" -s "${SCHEME}"

ENTRYPOINT /bin/bash

