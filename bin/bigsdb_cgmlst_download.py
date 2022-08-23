#!/usr/bin/env python3

import gzip
import logging
import os
import shutil
import sys

from NormalizeAlleles import normalize_fasta
from pubmlst_mlst_download import download
from retry import retry


@retry(backoff=2, delay=1, max_delay=1200)
def download_profiles(url_prefix, out_file):
    url = f"{url_prefix}/profiles_csv"
    print(url, file=sys.stderr)
    r = download(url, timeout=600)
    shutil.copyfileobj(r, out_file)
    logging.debug(f"Downloaded scheme profiles")


@retry(backoff=2, delay=1, max_delay=1200)
def download_alleles(url_prefix, gene, out_file):
    url = f"{url_prefix}/{gene}/alleles_fasta"
    logging.debug(f"Downloading alleles for {gene}")
    r = download(url)
    normalize_fasta(r, out_file)
    logging.debug(f"Downloaded alleles for {gene}")


if __name__ == "__main__":
    if os.environ.get("DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    import argparse

    parser = argparse.ArgumentParser(description='Download a PubMLST cgMLST scheme')
    parser.add_argument('genes', help='path to file containing a list of genes')
    parser.add_argument('url', help='URL prefix for the scheme')
    parser.add_argument('out', help='directory to hold the outputs')
    parser.add_argument('--scheme_url', help='URL including the scheme number for profiles', required=False)
    parser.add_argument('--profiles', help='Download profiles', required=False)

    args = parser.parse_args()

    with open(args.genes, 'r') as f:
        genes = {l for l in (line.strip() for line in f) if l}

    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, mode=0o755, exist_ok=True)

    for gene in genes:
        with gzip.open(os.path.join(out_dir, f"{gene}.fa.gz"), 'wb') as f:
            download_alleles(args.url, gene, f)

    print(f"Downloaded alleles to {os.path.basename(out_dir)}")

    if args.profiles:
        with open(os.path.join(out_dir, "profiles.tsv"), 'wb') as f:
            download_profiles(args.scheme_url, f)
