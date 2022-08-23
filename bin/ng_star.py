#!/usr/bin/env python3

import gzip
import logging
import os
import shutil
import tempfile

try:
    import xlrd
except:
    logging.critical(f"Please make sure xlrd is installed")

from retry import retry
from NormalizeAlleles import normalize_fasta
from pubmlst_mlst_download import download


@retry(backoff=2, delay=1, max_delay=1200)
def download_alleles(gene, out_file):
    url = f"https://ngstar.canada.ca/alleles/download?lang=en&loci_name={gene}"
    logging.debug(f"Downloading {gene} from {url}.")
    r = download(url)
    alleles_ids = normalize_fasta(r, out_file)
    logging.debug(f"Downloaded alleles for {gene}")
    return alleles_ids


def parse_profiles(profile_file):
    with tempfile.NamedTemporaryFile('wb', delete=False) as _tmp:
        shutil.copyfileobj(profile_file, _tmp)
        profile_path = _tmp.name

    try:
        with xlrd.open_workbook(profile_path) as input_xlsx:
            sheet = input_xlsx.sheet_by_index(0)
            header = sheet.row_values(0)
            header[0] = 'ST'
            yield header
            for i in range(1, sheet.nrows):
                yield sheet.row_values(i)
    finally:
        os.remove(profile_path)


@retry(backoff=2, delay=1, max_delay=1200)
def download_profiles(allele_names, out_file):
    input_profiles = download('https://ngstar.canada.ca/sequence_types/download?lang=en', timeout=180)
    rows = parse_profiles(input_profiles)
    header_row = next(rows)
    print("\t".join(header_row), file=out_file)
    for row in rows:
        for i, (column, value) in enumerate(zip(header_row, row)):
            if column == 'ST':
                row[i] = str(int(value))
            elif column not in allele_names:
                row[i] = str(value)
            elif str(value).encode('utf8') in allele_names[column]:
                row[i] = str(value)
            elif str(int(value)).encode('utf8') in allele_names[column]:
                row[i] = str(int(value))
            else:
                raise ValueError(f"{value} is not recognised for {column}")
        print("\t".join(row), file=out_file)
    logging.debug(f"Writen profies for ng_star")


if __name__ == "__main__":
    if os.environ.get("DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    import argparse

    parser = argparse.ArgumentParser(description='Download a PubMLST MLST scheme')
    parser.add_argument('genes', help='path to file containing a list of genes')
    parser.add_argument('out', help='directory to hold the outputs')

    args = parser.parse_args()

    with open(args.genes, 'r') as f:
        genes = {l for l in (line.strip() for line in f) if l}

    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, mode=0o755, exist_ok=True)

    allele_names = {}

    for gene in genes:
        with gzip.open(os.path.join(out_dir, f"{gene}.fa.gz"), 'wb') as f:
            allele_names[gene] = download_alleles(gene, f)

    print(f"Downloaded alleles to {os.path.basename(out_dir)}")

    with open(os.path.join(out_dir, "profiles.tsv"), 'w') as f:
        download_profiles(allele_names, f)

    print(f"Downloaded profiles to {os.path.basename(out_dir)}")
