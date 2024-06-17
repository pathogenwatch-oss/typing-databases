#!/usr/bin/env python3

import gzip
import logging
import os
import sys
from datetime import datetime
from typing import Any, Iterable

import requests
from retry import retry

from NormalizeAlleles import normalize_fasta


@retry(backoff=2, delay=1, max_delay=1200)
def retry_fetch(url: str, headers: dict[str, str]) -> requests.Response:
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(r, file=sys.stderr)
        r.raise_for_status()
    return r


def api_download(
    url: str,
    api_key: str,
    filters: dict[str, str] = None,
    offset: int = 0,
    limit: int = 10000,
    safety_valve: int = 1000000,
) -> Iterable[dict[str, Any]]:
    if filters is None:
        filters = {}
    combined_filters = "&".join(
        [
            f"{field[0]}={field[1]}"
            for field in (
                filters | {"limit": str(limit), "offset": str(offset)}
            ).items()
        ]
    )
    while offset < safety_valve:
        r = retry_fetch(
            f"{url}?{combined_filters}",
            {"Authorization": f"Basic {api_key}"},
        )
        json = r.json()
        if r.json() is None:
            break
        offset += limit
        logging.debug(f"{datetime.now()},{offset},{json['links']['total____records']}")
        yield json
        if json["links"]["total____records"] < offset:
            break


# @retry(backoff=2, delay=1, max_delay=1200)
# def download_profiles(url_prefix, api_key, out_file):
#     url = f"{url_prefix}/profiles.list.gz"
#     r = download(url, api_key)
#     rz = gzip.GzipFile(fileobj=r)
#     shutil.copyfileobj(rz, out_file)
#     logging.debug("Downloaded scheme profiles")


def download_alleles(url_prefix: str, api_key: str, out_dir: str):
    url = f"{url_prefix}/loci"
    allele_url: str = f"{url_prefix}/alleles"

    for locus_batch in api_download(url, api_key):
        for locus in locus_batch["loci"]:
            fasta = []
            filters: dict[str, str] = {"locus": locus["locus"]}
            for allele_batch in api_download(allele_url, api_key, filters=filters):
                for allele in allele_batch["alleles"]:
                    fasta.append(f">{allele['allele_id']}".encode("utf-8"))
                    fasta.append(allele['seq'].encode("utf-8"))
            with gzip.open(f"{out_dir}/{locus['locus']}.fa.gz", "wb") as out_file:
                normalize_fasta(fasta, out_file)
            logging.debug(f"Downloaded alleles for {locus['locus']} to {out_file}")


def main(args) -> None:
    with open(args.api_key, "r") as f:
        api_key = f.read().strip()

    out_dir: str = os.path.expanduser(args.out)
    os.makedirs(out_dir, mode=0o755, exist_ok=True)

    download_alleles(args.url, api_key, out_dir)
    print(f"Downloaded alleles to {os.path.basename(out_dir)}")

    # if args.profiles:
    #     with open(os.path.join(out_dir, "profiles.tsv"), "wb") as f:
    #         download_profiles(args.url, api_key, f)


if __name__ == "__main__":
    if os.environ.get("DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    import argparse

    parser = argparse.ArgumentParser(description="Download an Enterobase cgMLST scheme")
    parser.add_argument(
        "--profiles", help="Download profiles", action="store_true", default=False
    )
    # parser.add_argument("genes", help="path to file containing a list of genes")
    parser.add_argument("url", help="URL prefix for the scheme")
    parser.add_argument("out", help="directory to hold the outputs")
    parser.add_argument(
        "--api-key", help="API key for the Enterobase API", default="api_key.txt"
    )

    main(parser.parse_args())
