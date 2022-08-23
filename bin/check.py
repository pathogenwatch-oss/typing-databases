#!/usr/bin/env python3

import datetime
import gzip
import json
import logging
import os
import re


def found_all_genes(path, genes):
    found_genes = {f.replace('.fa.gz', '') for f in os.listdir(path) if f.endswith('.fa.gz')}
    missing = list(genes - found_genes)
    if len(missing) > 0:
        logging.warning(
            f"{path} did not contain gzipped fasta files for {len(missing)} genes (like {', '.join(missing[:3])})")
        for m in missing:
            logging.debug(f"- {path} did not contain {m}.fa.gz")
        logging.debug(f"{path} contains:")
        for p in sorted(os.listdir(path)):
            logging.debug(f"- {p}")
        return False
    extra = list(found_genes - genes)
    if len(extra) > 0:
        logging.warning(f"{path} contains extra gzipped fasta files (like {', '.join(extra[:3])})")
        for e in extra:
            logging.debug(f"- {path} contains {e}.fa.gz")
        return False
    return True


def alleles_ok(path):
    with gzip.open(path, 'r') as f:
        lines = [l for l in f.read().split(b'\n') if l]
    if len(lines) == 0:
        logging.warning(f"{path} is empty")
        return False
    if len(lines) % 2:
        logging.warning(f"{path} has {len(lines)} lines, should be even")
        return False
    seqs = ((i * 2 + 1, name, contig) for (i, (name, contig)) in enumerate(zip(lines[::2], lines[1::2])))
    for ln, name_line, contig_line in seqs:
        if not re.match(b'^>[0-9]+(\.[0-9]+)?$', name_line):
            logging.warning(f"{path}:{ln} Bad contig name '{name_line.strip()}'")
            return False
        bad_characters = set(contig_line.strip()) - set(b'ACGT')
        if len(bad_characters) > 0:
            logging.warning(f"{path}:{ln + 1} Contig contains illegal characters '{''.join(map(chr, bad_characters))}'")
            return False
    return True


def profiles_ok(path, genes):
    with open(path, 'r') as f:
        header = set(next(f).strip().split('\t'))
    if len(header.intersection(genes)) != len(genes):
        logging.warning(f"Expected {len(genes)} in the header for the profiles")
        for g in genes.difference(header):
            logging.debug(f"- {g} was missing")
        return False
    if 'ST' not in header and 'scgST' not in header:
        logging.warning(f"Expected header for ST in the profiles")
        return False
    return True


def scheme_ok(scheme_dir):
    if not os.path.isdir(scheme_dir):
        logging.warning(f"{scheme_dir} could not be found")
        return False

    with open(os.path.join(scheme_dir, '.bin', 'genes.txt'), 'r') as f:
        expected_genes = {g for g in (line.strip() for line in f) if g}
    if not found_all_genes(scheme_dir, expected_genes):
        return False

    for gene in expected_genes:
        if not alleles_ok(os.path.join(scheme_dir, f"{gene}.fa.gz")):
            return False

    profiles_path = os.path.join(scheme_dir, 'profiles.tsv')
    if os.path.isfile(profiles_path):
        if not profiles_ok(profiles_path, expected_genes):
            logging.warning(f"'{scheme_dir}/profiles.tsv' was badly formatted")
            return False

    update_details_path = os.path.join(scheme_dir, 'updated.txt')
    try:
        with open(update_details_path, 'r') as f:
            date_string = next(f).strip()
            d = datetime.datetime.strptime(date_string, '%Y%m%d%H%M')
    except KeyboardInterrupt:
        raise
    except FileExistsError:
        logging.warning(f"Expected 'updated.txt' in {scheme_dir}")
        return False
    except:
        logging.warning(
            f"Expected a UTC datetime in YYYYmmddHHMM format (e.g. 201907251554 is '2019-07-25T15:54:10.110361' UTC)' in {scheme_dir}/updated.txt'")
        return False

    return True


if __name__ == '__main__':
    if os.environ.get("DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Check a scheme is well formatted')
    parser.add_argument('-s', '--scheme', action='append', help='shortname of scheme')
    parser.add_argument('-t', '--type', help='filter by type of scheme')
    parser.add_argument('-d', '--directory', action='append', help='directory containing the scheme')
    args = parser.parse_args()

    BIN_DIR = os.path.dirname(os.path.realpath(__file__))
    ROOT_DIR = os.path.dirname(BIN_DIR)
    with open(os.path.join(ROOT_DIR, 'schemes.json'), 'r') as f:
        schemes = json.load(f)['schemes']

    if args.type:
        schemes = [s for s in schemes if s['type'] == args.type]

    if args.scheme and args.directory:
        scheme_dirs = [os.path.join(ROOT_DIR, s['path']) for s in schemes if s['shortname'] in args.scheme]
        scheme_dirs += args.directory
    elif args.scheme:
        scheme_dirs = [os.path.join(ROOT_DIR, s['path']) for s in schemes if s['shortname'] in args.scheme]
    elif args.directory:
        scheme_dirs = args.directory
    else:
        scheme_dirs = [os.path.join(ROOT_DIR, s['path']) for s in schemes]

    errors = False
    for scheme in scheme_dirs:
        if not scheme_ok(scheme):
            errors = True
        else:
            logging.warning(f"{scheme} is OK")

    if errors:
        sys.exit(1)
