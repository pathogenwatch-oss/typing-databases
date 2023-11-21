#!/usr/bin/env python3

import gzip
import logging
import os
import subprocess
import sys

from retry import retry

from NormalizeAlleles import normalize_fasta
from pubmlst_mlst_download import download


@retry(tries=1, backoff=2, delay=1, max_delay=1200)
def download_profiles(url_prefix, out_file):
    p = subprocess.run(['curl', '-o', out_file, f'{url_prefix}/profiles_csv'])
    if p.returncode != 0:
        logging.error(f"Failed to download profiles: {p.stderr}")
        sys.exit(1)
    logging.debug("Downloaded scheme profiles")


@retry(tries=3, backoff=2, delay=1, max_delay=1200)
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
        logging.debug("Downloading scheme profiles to profiles.tsv")
        download_profiles(args.scheme_url, os.path.join(out_dir, "profiles.tsv"))
