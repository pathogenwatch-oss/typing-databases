import dataclasses
import gzip
import io
import json
import logging
import os
import shutil
import socket
import ssl
import urllib.request
import uuid
import zipfile
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Iterable

import requests
from rauth import OAuth1Session
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from download_schemes.keycache import KeyCache
from download_schemes.normalise_alleles import normalise_fasta


# @retry(
#     stop=stop_after_attempt(10),
#     wait=wait_exponential(multiplier=1, min=1, max=1200),
# )
def retry_oauth_fetch(host: str, keycache: KeyCache, database: str, url: str) -> requests.Response:
    logging.debug(f"Fetching data from authenticated {host} - {database}...")
    consumer_key = keycache.get_consumer_key(host)
    session_key = keycache.get_session_key(host, database)
    session = OAuth1Session(
        consumer_key[0],
        consumer_key[1],
        access_token=session_key[0],
        access_token_secret=session_key[1],
    )
    response = session.get(url)
    if response.status_code == 301 or response.status_code == 401:
        logging.error(f"Session access denied. Attempting to regenerate keys as needed for {host}")
        keycache.delete_key("session", host)
        response = retry_oauth_fetch(host, keycache, database, url)
    else:
        response.raise_for_status()
    return response


@retry(
    stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=1, max=1200)
)
def retry_fetch(url: str, headers: dict[str, str] = None) -> requests.Response:
    if headers is None:
        headers = {}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        logging.error(f"Failed to fetch {url}: {r.status_code}")
        r.raise_for_status()
    return r



@retry(
    stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=1, max=1200)
)
def download(url, timeout=10) -> urllib.request.urlopen:
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
        logging.debug(f"Downloaded {url}")
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
        logging.debug(f"{datetime.now()},{offset},{json_r['links']['total____records']}")
        yield json_r
        if json_r["links"]["total____records"] < offset:
            break


@dataclasses.dataclass
class PubmlstDownloader:
    host: str
    host_path: str
    scheme_id: int
    type: str
    keycache: KeyCache

    def __post_init__(self):
        self.database = f"{self.host_path.replace('pubmlst_', '').replace('_seqdef','')}"
        self.name = f"{self.host_path.replace('_seqdef','')}_{self.scheme_id}"
        self.base_url = f"{self.keycache.get_rest_url(self.host)}/{self.host_path}"
        self.scheme_url = f"{self.base_url}/schemes/{self.scheme_id}"
        self.loci_url = f"{self.scheme_url}/loci"
        self.alleles_url = f"{self.base_url}/loci"
        self.__retry_oauth_fetch: Callable[[str], requests.Response] = partial(retry_oauth_fetch, self.host, self.keycache, self.database)


    def download_loci(self) -> list[str]:
        logging.debug(f"Downloading loci for {self.name}...")
        r = self.__retry_oauth_fetch(self.loci_url)
        loci: list[str] = []
        stem = f"{self.alleles_url}/"
        for locus in json.loads(r.text)["loci"]:
            loci.append(locus.replace(stem, ""))
        return loci

    def download_profiles(self, out_dir: Path):
        response = self.__retry_oauth_fetch(f"{self.scheme_url}/profiles_csv")

        if response.status_code == 200:
            with open(out_dir / "profiles.tsv", "wb") as out_file:
                out_file.write(response.content)
        else:
            raise Exception(
                f"Failed to download profiles: HTTP status {response.status_code}"
            )

    def fetch_timestamp(self):
        logging.debug(f"Fetching timestamp for {self.name}...")
        url = self.scheme_url
        r = self.__retry_oauth_fetch(url)
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

        logging.debug(f"Downloading alleles for {self.name} from {self.host}")
        for locus in self.download_loci():
            alleles_url = f"{self.alleles_url}/{locus}/alleles_fasta"
            logging.debug(f"Downloading alleles for {locus} from {alleles_url}")

            # PubMLST puts an apostrophe in front of RNA genes it seems
            clean_locus = locus.replace("'", "")
            scheme_metadata["genes"].append(clean_locus)
            allele_file = Path(f"{scheme_dir}/{clean_locus}.fa.gz")
            # Remove any existing file to deal with failed downloads.
            allele_file.unlink(missing_ok=True)
            with gzip.open(allele_file, "wt") as out_f:
                response = self.__retry_oauth_fetch(alleles_url)
                normalise_fasta(response.text, out_f)

        if self.type != "cgmlst":
            logging.debug(f"Downloading profiles for {self.name}")
            self.download_profiles(scheme_dir)
        logging.debug(f"Writing metadata for {self.name}")
        with open(f"{scheme_dir}/metadata.json", "w") as out_f:
            json.dump(scheme_metadata, out_f, indent=4)
        return scheme_subdir, scheme_metadata["last_updated"]


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

            # Create a file-like object from the response content
            gzip_file = io.BytesIO(r.read())

            # Open the gzip file and read its content
            with gzip.open(gzip_file, "rt") as gz_content, gzip.open(
                f"{out_dir}/{locus}.fa.gz", "wt"
            ) as out_f:
                normalise_fasta(gz_content.read(), out_f)

            logging.debug(f"Downloaded and normalized alleles for {locus}")

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
        logging.info(f"Downloading alleles for {self.scheme_id} to {scheme_dir}")
        loci = self.download_loci_list()
        metadata = {"last_updated": self.fetch_timestamp(), "genes": loci}
        self.download_alleles(loci, scheme_dir)
        if self.type != "cgmlst":
            self.download_profiles(scheme_dir)
        with open(f"{scheme_dir}/metadata.json", "w") as out_f:
            json.dump(metadata, out_f, indent=4)
        return scheme_subdir, metadata["last_updated"]


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
        logging.warning(f"Unable to fetch timestamp for Ridom schemes: {self.short_name}")
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
            with gzip.open(f"{scheme_dir}/{fasta_file.stem}.fa.gz", "wt") as out_file:
                with open(fasta_file, "rt") as in_file:
                    normalise_fasta(in_file.read(), out_file)

        # Clean up
        os.unlink(alleles_zip_file)
        shutil.rmtree(temp_dir)
        with open(f"{scheme_dir}/metadata.json", "w") as out_f:
            json.dump(metadata, out_f, indent=4)
        return scheme_subdir, metadata["last_updated"]


def initialise(metadata: dict[str, Any], keycache: KeyCache = None) -> Any:
    if "host" in metadata.keys() and metadata["host"] in ["pubmlst", "pasteur"]:
        return PubmlstDownloader(
            metadata["host"],
            metadata["host_path"],
            metadata["scheme_id"],
            metadata["type"],
            keycache=keycache,
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
        logging.info(f"Skipping {metadata['short_name']}")
