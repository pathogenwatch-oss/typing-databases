import dataclasses
import gzip
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import requests
from retry import retry

from downloaders.normalise_alleles import normalise_fasta


@retry(tries=10, backoff=2, delay=1, max_delay=1200)
def retry_fetch(url: str, headers: dict[str, str] = None) -> requests.Response:
    if headers is None:
        headers = {}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print(r, file=sys.stderr)
        r.raise_for_status()
    return r


@retry(tries=10, backoff=2, delay=1, max_delay=1200)
def download(url, timeout=10):
    req = urllib.request.Request(
        url,
        data=None,
        headers={
            "User-Agent": "mlst-downloader (https://gist.github.com/bewt85/16f2b7b9c3b331f751ce40273240a2eb)"
        },
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=timeout)
        print(f"Downloaded {url}", file=sys.stderr)
    except KeyboardInterrupt:
        raise
    except socket.timeout:
        raise Exception(f"GET '{url}' timed out after {timeout} seconds")
    if r.getcode() != 200:
        raise Exception(f"GET '{url}' returned {r.getcode()}")
    return r


def enterobase_api_download(
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
        json_r = r.json()
        if r.json() is None:
            break
        offset += limit
        # print(f"{datetime.now()},{offset},{json['links']['total____records']}")
        yield json_r
        if json_r["links"]["total____records"] < offset:
            break


@dataclasses.dataclass
class PubmlstDownloader:
    host_path: str
    scheme_id: int
    type: str
    api_url: str = "https://rest.pubmlst.org/db"

    def __post_init__(self):
        self.name = f"{self.host_path.replace('_seqdef','')}_{self.scheme_id}"
        self.base_url = f"{self.api_url}/{self.host_path}"
        self.scheme_url = f"{self.base_url}/schemes/{self.scheme_id}"
        self.loci_url = f"{self.scheme_url}/loci"
        self.alleles_url = f"{self.base_url}/loci"

    def download_loci(self) -> list[str]:
        r = retry_fetch(self.loci_url)
        loci: list[str] = []
        stem = f"{self.alleles_url}/"
        for locus in json.loads(r.text)["loci"]:
            loci.append(locus.replace(stem, ""))
        return loci

    @retry(
        tries=10,
        backoff=2,
        delay=1,
        max_delay=1200,
    )
    def download_profiles(self, out_dir: Path):
        p = subprocess.run(
            [
                "curl",
                "-o",
                out_dir / "profiles.tsv",
                f"{self.scheme_url}/profiles_csv",
            ]
        )
        if p.returncode != 0:
            raise Exception(f"Failed to download profiles: {p.stderr}")

    def fetch_timestamp(self):
        url = self.scheme_url
        r = retry_fetch(url)
        scheme_metadata = json.loads(r.text)
        return (
            scheme_metadata["last_updated"]
            if "last_updated" in scheme_metadata
            else datetime.today().strftime("%Y-%m-%d")
        )

    def download(self, out_dir: Path) -> tuple[Path, str]:
        scheme_subdir = Path(f"{self.type}_schemes") / f"{self.name}"
        scheme_dir: Path = out_dir / scheme_subdir
        scheme_dir.mkdir(parents=True, exist_ok=True)
        scheme_metadata = {"last_updated": self.fetch_timestamp(), "genes": []}

        for locus in self.download_loci():
            alleles_url = f"{self.alleles_url}/{locus}/alleles_fasta"
            r = download(alleles_url)
            # PubMLST puts a apostrophe in front of RNA genes it seems
            clean_locus = locus.replace("'", "")
            scheme_metadata["genes"].append(clean_locus)
            with gzip.open(f"{scheme_dir}/{clean_locus}.fa.gz", "wb") as out_f:
                normalise_fasta(r, out_f)

        if self.type != "cgmlst":
            self.download_profiles(scheme_dir)
        with open(f"{scheme_dir}/metadata.json", "w") as out_f:
            json.dump(scheme_metadata, out_f, indent=4)
        return scheme_subdir, scheme_metadata["last_updated"]


# Basis of working downloader, but not maintained as it seems the FTP site is more robust
# @dataclasses.dataclass
# class EnterobaseApiDownloader:
#     host_path: str  # e.g.senterica/cgMLST_v2
#     scheme_id: str  # Salmonella.cgMLSTv2
#     type: str
#     api_key: str
#     api_url: str = "https://enterobase.warwick.ac.uk/api/v2.0"
#     ftp_base_url: str = "https://enterobase.warwick.ac.uk/schemes"
#
#     def __post_init__(self):
#         self.scheme_url = f"{self.api_url}/{self.host_path}"
#         self.loci_url = f"{self.scheme_url}/loci"
#         self.alleles_url = f"{self.scheme_url}/alleles"
#         self.name = f"enterobase_{self.host_path.split('/')[0]}"
#         self.profiles_url = f"{self.ftp_base_url}{self.scheme_id}/profiles.list.gz"
#
#     def download_alleles(self, out_dir: str):
#         for locus_batch in enterobase_api_download(self.loci_url, self.api_key):
#             for locus in locus_batch["loci"]:
#                 fasta = []
#                 filters: dict[str, str] = {"locus": locus["locus"]}
#                 for allele_batch in enterobase_api_download(
#                     self.alleles_url, self.api_key, filters=filters
#                 ):
#                     for allele in allele_batch["alleles"]:
#                         fasta.append(f">{allele['allele_id']}".encode("utf-8"))
#                         fasta.append(allele["seq"].encode("utf-8"))
#                 with gzip.open(f"{out_dir}/{locus['locus']}.fa.gz", "wb") as out_file:
#                     normalise_fasta(fasta, out_file)
#                 print(
#                     f"Downloaded alleles for {locus['locus']} to {out_file}",
#                     file=sys.stderr,
#                 )
#
#     def download_profiles(self, out_dir: Path):
#         r = download(self.scheme_url)
#         rz = gzip.GzipFile(fileobj=r)
#         with open(out_dir / "profiles.tsv.gz", "wb") as out_file:
#             shutil.copyfileobj(rz, out_file)
#
#     def download(self, out_dir: Path):
#         out_dir: Path = out_dir / f"{self.type}_schemes" / self.name
#         # metadata = {"last_updated": self.fetch_timestamp(), "genes": []}
#         self.download_alleles(str(out_dir))
#         if self.type != "cgmlst":
#             self.download_profiles(out_dir)


@dataclasses.dataclass
class EnterobaseFtpDownloader:
    scheme_id: str  # Salmonella.cgMLSTv2
    type: str
    base_url: str = "https://enterobase.warwick.ac.uk/schemes"

    def __post_init__(self):
        self.scheme_url = f"{self.base_url}{self.scheme_id}"
        self.name = f"enterobase_{self.scheme_id}"
        self.profiles_url = f"{self.scheme_url}/profiles.list.gz"

    def download_loci_list(self) -> list[str]:
        r = download(self.profiles_url)
        rz = gzip.GzipFile(fileobj=r)
        loci = None
        for line in rz:
            loci = line.decode("utf-8").strip().split("\t")[1:]
            break
        if loci is None:
            raise Exception(f"Unable to download the list of loci for {self.scheme_id}")
        return loci

    def download_profiles(self, out_dir: Path):
        r = download(self.profiles_url)
        rz = gzip.GzipFile(fileobj=r)
        with open(out_dir / "profiles.tsv", "wb") as out_file:
            shutil.copyfileobj(rz, out_file)

    def download_alleles(self, loci: list[str], out_dir: Path):
        for locus in loci:
            url = f"{self.scheme_url}/{locus}.fasta.gz"
            r = download(url)
            rz = gzip.GzipFile(fileobj=r)
            with gzip.open(f"{out_dir}/{locus}.fa.gz", "wb") as out_f:
                normalise_fasta(rz, out_f)

    def fetch_timestamp(self):
        r = download(self.scheme_url)
        date = None
        for line in r:
            if ".fasta.gz" in line.decode("utf-8"):
                date = line.decode("utf-8").strip().split()[2]
                break
        if date is None:
            raise Exception(f"Unable to download the timestamp for {self.scheme_id}")
        return datetime.strptime(date, "%d-%b-%Y").strftime("%Y-%m-%d")

    def download(self, out_dir: Path) -> tuple[Path, str]:
        scheme_subdir = Path(f"{self.type}_schemes") / self.name
        scheme_dir = out_dir / scheme_subdir
        scheme_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"Downloading alleles for {self.scheme_id} to {scheme_dir}", file=sys.stderr
        )
        loci = self.download_loci_list()
        metadata = {"last_updated": self.fetch_timestamp(), "genes": loci}
        self.download_alleles(loci, scheme_dir)
        if self.type != "cgmlst":
            self.download_profiles(scheme_dir)
        with open(f"{scheme_dir}/metadata.json", "w") as out_f:
            json.dump(metadata, out_f, indent=4)
        return scheme_subdir,  metadata["last_updated"]


@dataclasses.dataclass
class RidomCgmlstDownloader:
    scheme_id: str
    short_name: str
    base_url: str = "https://www.cgmlst.org/ncs/schema/"
    type: str = "cgmlst"

    def __post_init__(self):
        self.scheme_url = f"{self.base_url}/{self.scheme_id}"
        self.alleles_url = f"{self.scheme_url}/alleles"
        self.name = f"ridom_{self.short_name.split('_')[0]}_{self.scheme_id}"

    def fetch_timestamp(self):
        print(
            f"Warning: Unable to fetch timestamp for Ridom schemes: {self.short_name}",
            file=sys.stderr,
        )
        return datetime.now().strftime("%Y-%m-%d")

    def download(self, out_dir: Path):
        # Download as a zip file
        alleles_zip_file = "alleles.zip"
        urllib.request.urlretrieve(self.alleles_url, alleles_zip_file)
        temp_dir = Path(f"scratch_{uuid.uuid4()}")
        scheme_subdir = Path(f"{self.type}_schemes") / self.name
        scheme_dir: Path = out_dir / scheme_subdir
        scheme_dir.mkdir(parents=True, exist_ok=True)

        # Extract to a scratch directory
        with zipfile.ZipFile(alleles_zip_file, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        metadata = {"last_updated": self.fetch_timestamp(), "genes": []}
        # Normalise the files into the correct directory.
        for fasta_file in temp_dir.glob("*.fasta"):
            metadata["genes"].append(fasta_file.stem)
            with gzip.open(f"{scheme_dir}/{fasta_file.stem}.fa.gz", "wb") as out_file:
                with open(fasta_file, "rb") as in_file:
                    normalise_fasta(in_file, out_file)

        # Clean up
        os.unlink(alleles_zip_file)
        shutil.rmtree(temp_dir)
        with open(f"{scheme_dir}/metadata.json", "w") as out_f:
            json.dump(metadata, out_f, indent=4)
        return scheme_subdir, metadata["last_updated"]


def initialise(metadata: dict[str, Any]) -> Any:
    if "host" in metadata.keys() and metadata["host"] == "pubmlst":
        return PubmlstDownloader(
            metadata["host_path"], metadata["scheme_id"], metadata["type"]
        )
    elif "host" in metadata.keys() and metadata["host"] == "pasteur":
        return PubmlstDownloader(
            metadata["host_path"],
            metadata["scheme_id"],
            metadata["type"],
            api_url="https://bigsdb.pasteur.fr/api/db",
        )
    elif "host" in metadata.keys() and metadata["host"] == "enterobase":
        return EnterobaseFtpDownloader(
            metadata["scheme_id"],
            metadata["type"],
        )
    elif "host" in metadata.keys() and metadata["host"] == "ridom":
        return RidomCgmlstDownloader(
            metadata["scheme_id"],
            metadata["shortname"],
        )
    else:
        print(f"Skipping {metadata['short_name']}", file=sys.stderr)
