#!/usr/bin/env python3

import gzip
import re

bad_char = re.compile(b'[^ACGT]')


def parse(f):
    lines = [line.strip() for line in f]
    contigs = []
    for line in lines:
        if line.startswith(b'>'):
            if line.startswith(b'>MTRR_CONTIG'):
                continue
            contigs.append((line[1:], []))
        elif not line:
            continue
        else:
            contigs[-1][1].append(line)
    return [(name, b''.join(parts).upper()) for name, parts in contigs]


def normalize_fasta(input_, output):
    contigs = parse(input_)
    contig_names = []
    for name, contig in contigs:
        m = re.match(b'^(.+[_-])?([0-9]+(\\.[0-9]+)?)$', name)
        assert m is not None, f"Badly formated allele '{name}'"
        if bad_char.search(contig):
            # Some schemes had non-ACGT characters
            continue
        if len(contig.strip()) == 0:
            # pubmlst_neisseria_62/NEIS1690.fa.gz has an allele with
            # no content.  I assume it is because it needs to be removed
            continue
        output.write(b'>%s\n%s\n' % (m[2], contig))
        contig_names.append(m[2])
    assert len(contigs) > 0, "Expected there to be some contigs"
    return contig_names


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Format allele file')
    parser.add_argument('input', help='input file ("-" for stdin)')
    parser.add_argument('output', help='output file')

    args = parser.parse_args()

    input_file = None
    try:
        if args.input == '-':
            input_file = sys.stdin.buffer
        else:
            input_file = open(args.input, 'rb')

        with gzip.open(args.output, 'wb') as output_file:
            normalize_fasta(input_file, output_file)
    finally:
        if input_file != None and args.input != '-':
            input_file.close()
