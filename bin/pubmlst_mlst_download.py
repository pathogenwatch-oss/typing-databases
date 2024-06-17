#!/usr/bin/env python3

import gzip
import logging
import os
import shutil
import socket
import ssl
import sys
import urllib.request
from datetime import datetime
from typing import Any, Iterable

import requests
from retry import retry

from NormalizeAlleles import normalize_fasta

profilesTemplate = "{server}?db=pubmlst_{scheme}_seqdef&page=downloadProfiles&scheme_id={scheme_id}"
locusTemplate = "{server}?db=pubmlst_{scheme}_seqdef&page=downloadAlleles&locus={gene}"


# def retry(func):
#     MAX_RETRIES = 5
#
#     def func_wrapper(*args, **kwargs):
#         for i in range(MAX_RETRIES):
#             try:
#                 return func(*args, **kwargs)
#             except KeyboardInterrupt:
#                 raise
#             except:
#                 if i < (MAX_RETRIES - 1):
#                     t = 5 * (i + 1)
#                     logging.exception(f"Encountered issue; will retry in {t} seconds")
#                     time.sleep(t)
#                 else:
#                     raise
#
#     return func_wrapper


def download(url, timeout=10):
    req = urllib.request.Request(
        url,
        data=None,
        headers={
            'User-Agent': 'mlst-downloader (https://gist.github.com/bewt85/16f2b7b9c3b331f751ce40273240a2eb)'
        }
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=timeout)
        logging.debug(f"Downloaded {url}")
    except KeyboardInterrupt:
        raise
    except socket.timeout:
        raise Exception(f"GET '{url}' timed out after {timeout} seconds")
    if r.getcode() != 200:
        raise Exception(f"GET '{url}' returned {r.getcode()}")
    return r


@retry(backoff=2, delay=1, max_delay=1200)
def download_profiles(server, scheme, scheme_id, genes, out_file):
    url = profilesTemplate.format(server=server, scheme=scheme, scheme_id=scheme_id)
    logging.debug(f"Downloading profiles from {url}.")
    r = download(url)
    line = next(r)
    columns = {c for c in line.decode('utf-8').strip().split('\t')}
    out_file.write(line)
    shutil.copyfileobj(r, out_file)
    logging.debug(f"Downloaded {scheme} profiles")


@retry(backoff=2, delay=1, max_delay=1200)
def download_alleles(server, scheme, gene, out_file):
    url = locusTemplate.format(server=server, scheme=scheme, gene=gene)
    r = download(url)
    normalize_fasta(r, out_file)
    logging.debug(f"Downloaded {scheme} alleles")


if __name__ == "__main__":
    if os.environ.get("DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    import argparse

    parser = argparse.ArgumentParser(description='Download a PubMLST MLST scheme')
    parser.add_argument('scheme', help='short name for PubMLST scheme')
    parser.add_argument('--scheme-id', help='scheme id', default=1, type=int, dest='scheme_id')
    parser.add_argument('--server', help='server prefix', choices=['pubmlst', 'pasteur'], default='pubmlst')
    parser.add_argument('genes', help='path to file containing a list of genes')
    parser.add_argument('out', help='directory to hold the outputs')

    args = parser.parse_args()
    args.server = {
        "pasteur": "https://bigsdb.pasteur.fr/cgi-bin/bigsdb/bigsdb.pl",
        "pubmlst": "https://pubmlst.org/bigsdb"
    }[args.server]

    with open(args.genes, 'r') as f:
        genes = {l for l in (line.strip() for line in f) if l}

    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, mode=0o755, exist_ok=True)
    with open(os.path.join(out_dir, 'profiles.tsv'), 'wb') as f:
        download_profiles(args.server, args.scheme, args.scheme_id, genes, f)
    for gene in genes:
        with gzip.open(os.path.join(out_dir, f"{gene}.fa.gz"), 'wb') as f:
            download_alleles(args.server, args.scheme, gene, f)
    print(f"Downloaded {args.scheme} to {out_dir}", file=sys.stderr)
