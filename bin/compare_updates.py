#!/usr/bin/env python3

import gzip
import os
import sys
import traceback
from git import Repo
from Bio import pairwise2
from Bio.pairwise2 import format_alignment
from os.path import realpath, dirname, join, basename

def read_sequences(fz):
  f = gzip.GzipFile(fileobj=fz)
  lines = (l.strip() for l in f)
  lines = (l for l in lines if l)
  lines = [l[1:] if l[0] == ord(b'>') else l for l in lines]
  return set(zip(lines[::2], lines[1::2]))

def detailed_diff(path, seqsA, seqsB):
  seqsA = { name: seq for name,seq in seqsA }
  seqsB = { name: seq for name,seq in seqsB }
  removed = set(seqsA) - set(seqsB)

  for i in range(100):
    if str(i).encode('utf8') in seqsB:
      example_name = str(i).encode('utf8')
      break
  print(f"Example: {path} ({example_name.decode('utf8')})\n{seqsA[example_name].decode('utf8')}\n")

  for name in removed:
    print(f"Removed {path} {name.decode('utf8')}\n{seqsA[name].decode('utf8')}\n")

  for name, seqB in seqsB.items():
    seqA = seqsA.get(name)
    if seqA and seqA != seqB:
      print(f"Changed {path} {name.decode('utf8')}")
      alignments = pairwise2.align.globalms(seqA.decode('utf8'), seqB.decode('utf8'), 2, -1, -0.5, -0.1)
      alignment = alignments[0]
      print(format_alignment(*alignment))
    sys.stdout.flush()

def get_changes(scheme, commit="origin/master"):
  scheme = realpath(scheme)
  total_before, total_after, total_added, total_removed, total_changed, genes_unchanged = 0, 0, 0, 0, 0, 0
  interesting = []
  to_add = []
  repo = Repo(scheme, search_parent_directories=True)
  root_dir = dirname(repo.git_dir)
  for diff in repo.commit(commit).diff(None, paths=scheme):
    assert diff.change_type == 'M', f"Only expected updates, not {diff.change_type}"
    assert diff.a_path == diff.b_path, f"Didn't expected {diff.a_path} to move to {diff.b_path}"
    to_add.append(diff.a_path)
    if diff.a_path.endswith('.fa.gz'):
      seqsA = read_sequences(diff.a_blob.data_stream)
      namesA = {s[0] for s in seqsA}
      b_path = join(root_dir, diff.b_path)
      with open(b_path, 'rb') as fz:
        seqsB = read_sequences(fz)
      namesB = {s[0] for s in seqsB}
      added = namesB - namesA
      removed = namesA - namesB
      changed = {s for s,_ in ((seqsA - seqsB) | (seqsB - seqsA)) if s not in added and s not in removed}
      total_before += len(seqsA)
      total_after += len(seqsB)
      total_added += len(added)
      total_removed += len(removed)
      total_changed += len(changed)
      if len(added) + len(removed) + len(changed) == 0:
        genes_unchanged += 1
      if len(removed) + len(changed):
        interesting.append(dict(path=basename(diff.a_path), before=len(seqsA), after=len(seqsB), added=len(added), removed=len(removed), changed=len(changed)))
        if os.getenv("DEBUG"):
          detailed_diff(diff.a_path, seqsA, seqsB)

  return dict(
    total_before=total_before,
    total_after=total_after,
    total_added=total_added,
    total_removed=total_removed,
    total_changed=total_changed,
    genes_unchanged=genes_unchanged,
    interesting=interesting
  ), to_add

def print_results(scheme, interesting, **others):
  def format(**d):
    return " ".join(f"{k}={v}" for k,v in d.items())
  print(format(scheme=scheme, **others))
  for d in interesting:
    print(" " + format(scheme=scheme, **d))
  sys.stdout.flush()

if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser(description='Download an Enterobase cgMLST scheme')
  parser.add_argument("-c", "--commit", default="origin/master")
  parser.add_argument("scheme", nargs="+")
  args = parser.parse_args()

  for scheme in args.scheme:
    try:
      changes, _ = get_changes(scheme, args.commit)
      print_results(scheme=scheme, **changes)
    except KeyboardInterrupt:
      raise
    except:
      print(f"Error checking {scheme}")
      print(traceback.format_exc())
