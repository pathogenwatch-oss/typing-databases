# Typing databases

This repository holds the build scripts and Dockerfile for building the typing database schemes for the MLST/cgMLST tool as an image.

Create a release by running the Dockerfile with no arguments and push the versioned container or create a scheme or scheme-type specific release.

This README will describe both how to get the files locally, and how to run the Dockerfile.

## Warning:

The NG-STAR update script requires `pip install xlrd==1.2.0`. Ideally either (a) the dependency should be replaced as it
no longer handles `.xlsx` files or (b) this is put into a Docker container for consistency.

## Quick usage (local)

```
./bin/update
```

This command will download each of the schemes.

The script is "polite" and will download the schemes slowly. It may take a an hour or more, even on a good internet
connection.

## Quick usage (docker)
### Full build
```
%> docker build --rm -t typing-databases:202208191648 .
```
### MLST build
```
%> docker build --rm -t typing-databases:202208191648-mlst --build-arg TYPE=mlst.
```
### Scheme build
```
%> docker build --rm -t typing-databases:202208191648-saureus --build-arg SCHEME=saureus
```

## Adding a new scheme

1. Make a directory for the scheme. It can be anywhere but maybe reuse `cgmlst_schemes` or `mlst_schemes` if it makes
   sense.
1. Create a `.bin` directory within the scheme directory
1. Add a file called `genes.txt` to the `.bin` directory. Each line should include the name of gene used in the scheme
1. Create a script called `.bin/download` in your language of choice. This script must download the alleles for each
   gene into a file called
   `${gene}.fa.gz` in gzipped Fasta format. Each allele should be on one and only one line and only include the upper
   case characters `ACGT`.  
   The sequences should be called `>1`, `>2`, etc. There is a script (and Python functions)
   called [NormalizeFasta.py](bin/NormalizeAlleles.py)
   which will make this easier.
1. If "profiles" are available for the scheme (e.g. for MLST schemes) then these should also be downloaded
   by `.bin/download` into `profiles.tsv`. These should be a tab delimited file. The header row should have a column
   called `ST` and be followed by each of the names of genes from `.bin/genes.txt`.
1. You can check your scheme has output files in the correct format by running `./bin/check.py -d SCHEME_DIRECTORY`. You
   can update the scheme using
   `./bin/update -s SCHEME_SHORTNAME`
1. When your scripts are working update [schemes.json](schemes.json) with the details of your scheme (see below).
1. You can now test your download script by running `./bin/update -s SCHEME_SHORTNAME`.

## Warnings

Git gets a bit funny if you change loads of files at once. It can take a long time to run `git status`, `git add`
, `git commit` etc (i.e. minutes for each command).

## Usage

You can update a scheme using `bin/update`. The script can take a scheme directory `--directory DIR`, scheme
shortname `--scheme SHORTNAME` or type of scheme
`--type cgmlst` (in which case it will update all matching schemes). You can pass the `--commit` flag so that changes
are committed after each scheme is updated. This is useful because Git commands can run slowly if there are a large
number of files with uncommitted changes.

## Examples

[Alleles file](mlst_schemes/saureus/arcC.fa.gz):

```
>1
TTATTAATCCAACAAGCTAAATCGAACAGTG...
>2
TTATTAATCCAACAAGCTAAATCGAACAGTG...
>3
TTATTAATCCAACAAGCTAAATCGAACAGTG...
>4
TTATTAATCCAACAAGCTAAATCGAACAGTG...
>5
TTATTAATCCAACAAGCTAAATCGAACAGTG...
```

Contigs are numbered. They each appear on one line and only include uppercase 'ACGT'

[Profiles file](mlst_schemes/saureus/profiles.tsv)

|ST|arcC|aroE|glpF|gmk|pta|tpi|yqiL|clonal_complex| |--|----|----|----|---|---|---|----|--------------| |1 |1 |1 |1 |1
|1 |1 |1 |CC1 | |2 |2 |2 |2 |2 |2 |2 |26 |CC30 | |3 |1 |1 |1 |9 |1 |1 |12 |CC1 | |4 |10 |10 |8 |6 |10 |3 |2 |CC45 |

This file must include a column per gene and an ST column but it can contain extra columns as well.

[List of genes](mlst_schemes/saureus/.bin/genes.txt)

```
arcC
aroE
glpF
gmk
pta
tpi
yqiL
```

[Download script](mlst_schemes/saureus/.bin/download)

```bash
#!/bin/bash

set -eu -o pipefail

SCHEME="saureus"

# From https://stackoverflow.com/a/246128 by Dave Dopson
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

SCHEME_DIR="$( cd $DIR/.. && pwd; )"
BIN_DIR="$( cd $DIR/../../../bin && pwd; )"

${BIN_DIR}/pubmlst_mlst_download.py $SCHEME ${DIR}/genes.txt $SCHEME_DIR
```

[Schemes file](schemes.json)

```
      ...
      "type": "mlst",
      "path": "mlst_schemes/sagalactiae"
    },
    {
      "name": "Staphylococcus aureus",
      "scheme_version": "0",
      "shortname": "saureus",
      "url": "https://pubmlst.org/saureus",
      "cite": "This tool made use of the Staphylococcus aureus MLST website (https://pubmlst.org/saureus/) sited at the University of Oxford (Jolley et al. Wellcome Open Res 2018, 3:124 [version 1; referees: 2 approved]). The development of PubMLST has been funded by the Wellcome Trust.",
      "targets": [{ "name": "Staphylococcus aureus", "taxid": 1280 }],
      "type": "mlst",
      "path": "mlst_schemes/saureus"
    },
    {
      "name": "Streptococcus bovis/equinus complex (SBSEC)",
      "scheme_version": "0",
      ...
```

Required fields:

| Field          | Description                                                                                                                                |
|----------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| name           | The name of the scheme                                                                                                                     |
| scheme_version | 0 unless there are multiple version of the scheme                                                                                          |
| shortname      | a unique name for the scheme (this can be shared between schemes of different types)                                                       |
| url            | where you can find more details of the scheme                                                                                              |
| cite           | a citation for the source of the scheme                                                                                                    |
| targets        | a list of species this scheme can be applied to. This should include the name of the species and the highest taxid it should be applied to |
| type           | the type of the scheme, currently mlst or cgmlst                                                                                           |
| path           | the relative path from this file to the directory containing the scheme                                                                    |