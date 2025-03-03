# Typing databases

This repository holds the build scripts and Dockerfile for building the typing database schemes for the MLST/cgMLST tool
as an image.

Create a release by running the Dockerfile with no arguments and push the versioned container or create a scheme or
scheme-type specific release.

This README will describe both how to get the files locally, and how to run the Dockerfile. If you just want
to get on with building some production images for Pathogenwatch skip straight to 
[the instructions for running build.py in Docker](#running-buildpy-via-docker).

## Quick Build instructions

See the [image builder instructions](Running `build.py` via Docker) for quick instructions on building all the images 
for a release.

## Working with `download_schemes.py`

### Quick usage (local)

```
python download_schemes.py all
```

This command will download each of the schemes.

The script is "polite" and will download the schemes slowly. It will take an hour or more, even on a good internet
connection. The metadata for the downloaded schemes, including the update timestamp and location within the produced
image, is printed to STDOUT along with being written to `selected_schemes.json`.

### Quick usage (docker)

NB: The BUILD_DATE argument is required to prevent Docker caching the download requests. A random string can be used,
and it doesn't need to be the date for this to work, but it does provide a handy date label for the image.

```
docker build --pull --rm --build-arg BUILD_DATE=2024-12-25 -t registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:2024-07-01-all .
```

#### Full build in a single image

For ease of testing

```
%> docker build --rm --build-arg BUILD_DATE=2024-12-25 -t typing-databases:all .
```

#### Single scheme build

```
%> docker build --rm  --build-arg BUILD_DATE=2024-12-25 --build-arg COMMAND="one klebsiella_1" -t typing-databases:24-07-01_klebsiella_cgmlst .
```

## Easy builds with `build.py`

The [`build.py`](build.py) script is provided for conveniently building individual scheme images for all or selected
schemes. It can be run from the command line or via Docker. It outputs a simple CSV containing the scheme shortname(s), the image tag(s) and the full image name(s).

### Basic CLI

#### Help and usage info

```
%> python build.py --help
```

#### Build all images

```
%> python build.py
```

#### Build a scheme image

`${short_name}` - the short name of the scheme as in the schemes.json file

```
%> python build.py -n ${short_name}
```

#### Build all MLST schemes

```
%> python build.py -t mlst
```

### Running `build.py` via Docker

For further convenience, it's possible to run `build.py` within a Docker image, creating images on the host machine.

#### Build the builder image

```
%> docker build --rm --pull -t download-runner -f Dockerfile.build .
%> docker run --rm download-runner --help
```

This image can then be used to generate all the single scheme images or just a selected one.

#### Build all images

To create a complete set of fresh scheme images with only Docker installed, run the following:

```
docker run -v /var/run/docker.sock:/var/run/docker.sock --rm download-runner
```

## Adding a new scheme

Schemes are managed using the [`schemes.json`](schemes.json) file. To add a scheme, add a new record.

### Example PubMLST scheme record.

_Note_: Pasteur records take the same format, just replace the host field with `"host": "pasteur"`

_Note2_: `taxid` must be a species or genus level NCBI taxonomy code if being used with Pathogenwatch.

```
{
   "shortname": "borrelia",
   "host": "pubmlst",
   "host_path": "pubmlst_borrelia_seqdef"
   "scheme_id": "1",
   "type": "mlst",
   "cite": "This tool made use of the Borrelia MLST website (https://pubmlst.org/borrelia/) sited at the University of Oxford (Jolley et al. Wellcome Open Res 2018, 3:124 [version 1; referees: 2 approved]). The development of PubMLST has been funded by the Wellcome Trust.",
   "name": "Borrelia spp.",
   "targets": [
       {
           "name": "Borrelia",
           "taxid": 138
       }
   ],
}
```

### Example Enterobase scheme record
_Note_: `host_path` is not required for Enterobase.
```
{
    "shortname": "senterica_1",
    "host": "enterobase",
    "scheme_id": "Salmonella.cgMLSTv2",
    "type": "cgmlst",
    "cite": [
        {
            "text": "Alikhan et al. (2018) PLoS Genet 14 (4): e1007261",
            "url": "https://doi.org/10.1371/journal.pgen.1007261"
        }
    ],
    "name": "Salmonella enterica cgMLST V2",
    "targets": [
        {
            "name": "Salmonella enterica",
            "taxid": 28901
        }
    ]
}
```

### Example Ridom (cgMLST-only) record
```
{
    "shortname": "p_aeruginosa_1",
    "host": "ridom",
    "scheme_id": "16115339",
    "type": "cgmlst",
    "cite": [
        {
            "text": "Tonnies H et al. (2020) J. Clin. Microbiol.",
            "url": "https://www.ncbi.nlm.nih.gov/pubmed/33328175",
            "long": "Tonnies H, Prior K, Harmsen D, and Mellmann A. Establishment and evaluation of a core genome multilocus sequence typing scheme for whole-genome sequence-based typing of Pseudomonas aeruginosa. J Clin Microbiol. 2020"
        }
    ],
    "name": "Pseudamonas aeruginosa",
    "targets": [
        {
            "name": "Pseudomonas aeruginosa",
            "taxid": 287
        }
    ]
}
```


## Output examples

### Allele file

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

### Profile file

|ST|arcC|aroE|glpF|gmk|pta|tpi|yqiL|clonal_complex| |--|----|----|----|---|---|---|----|--------------| |1 |1 |1 |1 |1
|1 |1 |1 |CC1 | |2 |2 |2 |2 |2 |2 |2 |26 |CC30 | |3 |1 |1 |1 |9 |1 |1 |12 |CC1 | |4 |10 |10 |8 |6 |10 |3 |2 |CC45 |

This file must include a column per gene and an ST column but it can contain extra columns as well.

### Metadata file

The metadata file contains the time stamp of when the scheme was last updated on the host server (except for Ridom
schemes), along with the list of genes in the required order for the scheme.

```
{
    "last_updated": "2024-06-30",
    "genes": [
        "NEIS1753",
        "mtrR",
        "NG_porB",
        "NG_ponA",
        "NG_gyrA",
        "NG_parC",
        "NG_23S"
    ]
}
```