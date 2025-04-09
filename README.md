# Typing database downloader

This repository holds the build scripts and Dockerfile for building the typing database schemes for the MLST/cgMLST tool
as an image.

Note that in order to build PubMLST or Pasteur-based schemes it is now required to have a user account and a "consumer
key and secret" for each host.

The core tool is designed to download one or more schemes into a single folder and can be run within Docker to create an
image containing the data. A second script called [build.py](build.py) is provided that can generate individual images
for each record in [schemes.json](config/schemes.json).

If you just want to get on with building some production images for Pathogenwatch skip straight
to [the instructions for running build.py in Docker](#running-buildpy-via-docker).

## Running the code

To run the python code directly, the simplest way is to use `uv`. It is also possible to install download_schemes as a
package using `uv` or `pip` by using them to compile the binary and then installing it. However, docker is the primary
supported method.

## Quick Build instructions

See the [image builder instructions](#running-buildpy-via-docker) for quick instructions on building all the images
for a release.

## Authentication

PubMLST and the Pasteur Institute require users to be logged in order to access the latest scheme data. Before running
the downloader you will need to obtain a user account and consumer token+secret for both. The downloader can then do the
required authentication steps. The generated keys can also be kept and re-used. For more details
see [Key Management](#key-management) below.

## Key Management

### secrets.json

The `secrets.json` file contains initial credentials and keys for accessing various MLST databases. It should include:

- User credentials for each host (e.g., PubMLST, Pasteur)
- Consumer keys for each host
- Any initial access or session keys (optional)

Example structure:

```
{
  "pubmlst": {
    "user": {
      "TOKEN": "your_username",
      "TOKEN SECRET": "your_password"
    },
    "consumer": {
      "TOKEN": "your_consumer_key",
      "TOKEN SECRET": "your_consumer_secret"
    }
  }
}
```

This is a minimal example. It is possible to also store request, access, and session tokens in this file.

### The key cache

The key cache mechanism allows for the reuse of generated keys (like access and session keys) between runs.
This improves efficiency and reduces the need for repeated authentication, especially when using Docker.

- The cache is initially populated with non-sensitive keys from secrets.json.
- As new keys are generated during the build process, they are stored in the cache.
- Subsequent builds can reuse these cached keys, speeding up the process.

For details on how to easily cache the keys between Docker builds see

## Easy builds with `build.py`

The [`build.py`](build.py) script is provided for conveniently building individual scheme images for all or selected
schemes. It can be run from the command line or via Docker. It outputs a simple CSV containing the scheme shortname(s),
the image tag(s) and the full image name(s).

### Basic CLI

#### Help and usage info

```
%> uv run --script build.py --help
```

#### Build all images

```
%> uv run --script build.py
```

#### Build a scheme image

`${short_name}` - the short name of the scheme as in the schemes.json file

```
%> uv run --script build.py -n ${short_name}
```

#### Build all MLST schemes

```
%> uv run --script build.py -t mlst
```

### Running `build.py` via Docker

For further convenience, it's possible to run `build.py` within a Docker image, creating images on the host machine.

#### Notes

It is best to run this on a clean copy of the repository as things like python venv directories may clash
with the build process.

Also, make sure the `secrets.json` file has been created and placed in the top leve of the repository and a directory
called `cache_dir` has also been created in the top level of the repository.

#### Build the builder image

```
%> docker build --rm --pull --build-arg VERSION=3.0.0 -t download-runner -f Dockerfile.build .
%> docker run --rm download-runner --help
```

This image can then be used to generate all the single scheme images or just a selected one.

#### Build all images

To create a complete set of fresh scheme images with only Docker installed, run the following:

```
docker run -v /var/run/docker.sock:/var/run/docker.sock -v $PWD:/data --rm download-runner:latest
```

## Working with `download_schemes.py`

### Quick usage (local)

```
uv run download_schemes
```

This command will download all the schemes into a local directory.

The script is "polite" and will download the schemes slowly. It will take an hour or more, even on a good internet
connection. The metadata for the downloaded schemes, including the update timestamp and location within the produced
image, is printed to STDOUT along with being written to `selected_schemes.json`.

### Quick usage (docker)

This command will download the `lmonocytogenes` scheme into a docker image, i.e. for use in building CGPS `mlst` images.

NB: The BUILD_DATE argument is required to prevent Docker caching the download requests. A random string can be used,
and it doesn't need to be the date for this to work, but it does provide a handy date label for the image.

```
docker build --rm \
  --build-arg SCHEME="-S lmonocytogenes" \
  --build-arg BUILD_DATE=$(date +%Y-%m-%d) \
  --build-arg VERSION=3.0.0 \
  --secret id=secrets,src="$PWD/secrets.json" \
  --cache-from type=local,src=cache_dir \
  --cache-to type=local,dest=cache_dir \
  -t typing-databases:2024-12-25-all .
```

### Running with Docker

#### Mounting the secrets at build time

Using this approach ensures that keys are not stored in the image. It will create a `cache_dir` directory

- `id=secrets,src="path/to/secrets.json"`: Path to your secrets.json file
- `--cache-from type=local,src=cache_dir --cache-to type=local,dest=cache_dir`: Configure `cache_dir` to cache keys.

#### Extracting the cached keys

If you wish to store the keys in the cache for future use, you can use the utility Dockerfile.read_cache to extract the
keys and update your `secrets.json` file.

1. Create the image for reading keys.
2. Run the image in the parent directory of `cache_dir`.

```
> docker build --cache-from type=local,src=cache_dir -t read_cache -f Dockerfile.read_cache .
> docker run --rm read_cache:latest
{output as JSON}
```

#### Full build in a single image

Note that the cache dir is optional in this case.

```
docker build --rm \
  --build-arg BUILD_DATE=$(date +%Y-%m-%d) \
  --build-arg VERSION=3.0.0 \
  --secret id=secrets,src="$PWD/secrets.json" \
  --cache-from type=local,src=cache_dir \
  --cache-to type=local,dest=cache_dir \
  -t typing-databases:latest .
```

#### Single scheme build

```
%> docker build --rm \
  --build-arg BUILD_DATE=$(date +%Y-%m-%d) \
  --build-arg VERSION=3.0.0 \
  --secret id=secrets,src="$PWD/secrets.json" \
  --cache-from type=local,src=cache_dir \
  --cache-to type=local,dest=cache_dir \
  --build-arg SCHEME="-S lmonocytogenes" \
  -t typing-databases:24-07-01_lmonocytogenes_cgmlst .
```

#### Multiple schemes

```
%> docker build --rm \
  --build-arg BUILD_DATE=$(date +%Y-%m-%d) \
  --build-arg VERSION=3.0.0 \
  --secret id=secrets,src="$PWD/secrets.json" \
  --cache-from type=local,src=cache_dir \
  --cache-to type=local,dest=cache_dir \
  --build-arg SCHEME="-S lmonocytogenes -S ecoli" \
  -t typing-databases:24-07-01_lmonocytogenes-ecoli_cgmlst .
```

## Adding a new scheme

Schemes are managed using the [`schemes.json`](config/schemes.json) file. To add a scheme, add a new record.

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

| ST | arcC | aroE | glpF | gmk | pta | tpi | yqiL | clonal_complex |
|----|------|------|------|-----|-----|-----|------|----------------|
| 1  | 1    | 1    | 1    | 1   | 1   | 1   | 1    | CC1            |
| 2  | 2    | 2    | 2    | 2   | 2   | 2   | 26   | CC30           | 
| 3  | 1    | 1    | 1    | 9   | 1   | 1   | 12   | CC1            | 
| 4  | 10   | 10   | 8    | 6   | 10  | 3   | 2    | CC45           |

The profiles are output in tab-delimited CSV file called `profiles.tsv`. This file must include a column per gene and an
ST column, but it can contain extra columns as well.

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

