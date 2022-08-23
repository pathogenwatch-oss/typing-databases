#!/usr/bin/env python3

import gzip
import os
import sys

def parse_exclusions(fin, fout, exclusions):
  skip=False
  for line in fin:
    if skip:
      skip = False
      continue
    if line.startswith('>') and line[1:].strip() in exclusions:
      print("Removing '{}'".format(line.strip()), file=sys.stderr)
      skip=True
      continue
    fout.write(line)

if __name__ == "__main__":
  import argparse

  parser = argparse.ArgumentParser(description='Remove alleles')
  parser.add_argument('input', help='input file')
  parser.add_argument('exclusions', nargs='*', help='list of alleles to remove')

  args = parser.parse_args()
  if args.input.endswith('.gz'):
    open = gzip.open

  with open(args.input, 'rt') as fin, open(args.input + '.tmp', 'wt') as fout:
    parse_exclusions(fin, fout, args.exclusions)
  os.rename(args.input + '.tmp', args.input)