import json
import logging
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from download_schemes import downloaders
from download_schemes.keycache import KeyCache

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_short=False)


def setup_logging(log_level: str):
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    logging.basicConfig(
        level=numeric_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.debug(f"Logging set up {logging.getLevelName(logging.getLogger().level)}")


@app.command()
def main(
    only: Annotated[
        Optional[list[str]],
        typer.Option(
            "-S",
            "--scheme",
            help="Filter schemes by 'shortname'.",
        ),
    ] = None,
    config_dir: Annotated[
        Path,
        typer.Option(
            "-C",
            "--config-dir",
            help="Path to the config directory containing the `schemes.json` and `host_config.json` files",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("config"),
    secrets_file: Annotated[
        Path,
        typer.Option(
            "-s",
            "--secrets-file",
            help="Path to the secrets file containing (at least) the user credentials and consumer key+secret",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = Path("secrets.json"),
    secrets_cache_file: Annotated[
        Path,
        typer.Option(
            "-c",
            "--secrets-cache-file",
            help="Path to the secrets cache file (default: secrets_cache.json)",
            file_okay=True,
            dir_okay=False,
        ),
    ] = Path("secrets_cache.json"),
    output_dir: Annotated[
        Path,
        typer.Option(
            "-o",
            "--output-dir",
            help="Path to the output directory",
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("."),
    output_schemes_file: Annotated[
        Path,
        typer.Option(
            "-f",
            "--output-schemes-file",
            help="Path to the output schemes.json file",
            file_okay=True,
            dir_okay=False,
        ),
    ] = "selected_schemes.json",
    log_level: Annotated[
        str,
        typer.Option(
            "-l",
            "--log-level",
            help="Set the logging level",
            case_sensitive=False,
        ),
    ] = "INFO",
) -> None:
    print(f"{config_dir}, {secrets_file}, {log_level}")
    setup_logging(log_level)

    schemes_file = config_dir / "schemes.json"

    with open(schemes_file, "r") as f:
        logging.debug(f"Loading schemes from {schemes_file} into {output_dir}...")
        schemes: list[dict[str, Any]] = json.load(f)["schemes"]

    if only:
        print(f"Only downloading schemes with shortnames: {', '.join(only)}")
        schemes = [
            scheme
            for scheme in schemes
            if any(wanted_scheme == scheme["shortname"] for wanted_scheme in only)
        ]

    keycache = KeyCache(secrets_file=secrets_file, host_config_file=config_dir / "host_config.json", cache_file=secrets_cache_file)
    logging.debug(f"Keycache: {keycache}")
    logging.info(f"Downloading {len(schemes)} schemes")
    download_schemes(output_dir, schemes, keycache, output_schemes_file)


def download_scheme(
    metadata: dict[str, Any], output_dir: Path, keycache: KeyCache
) -> tuple[str, str]:
    downloader = downloaders.initialise(metadata, keycache)
    logging.debug("Downloader initialised.")
    download_path, timestamp = downloader.download(output_dir)
    logging.debug(f"Downloaded {metadata['shortname']} to {download_path}")
    return str(download_path), timestamp


def download_schemes(
    output_dir: Path,
    schemes: list[dict[str, Any]],
    keycache: KeyCache,
    output_schemes_file: Path = None,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    for scheme in schemes:
        logging.info(f"Downloading {scheme['shortname']}")
        try:
            download_path, timestamp = download_scheme(scheme, output_dir, keycache)
            scheme["db_path"] = download_path
            scheme["last_updated"] = timestamp
        except Exception as e:
            logging.error(f"Error downloading {scheme['shortname']}: {str(e)}")
            raise e
    with open(output_schemes_file, "w") as f_out:
        json.dump({"schemes": schemes}, f_out)
        logging.debug(json.dumps({"schemes": schemes}))


def read_access_keys(key_file: Path) -> dict[str, tuple[str, str]]:
    if key_file is None or not key_file.exists():
        return {}
    with open(key_file, "r") as f:
        return json.load(f)


def read_consumer_keys(consumer_key_file: Path):
    if consumer_key_file is None or not consumer_key_file.exists():
        return {}
    with open(consumer_key_file, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    app()
