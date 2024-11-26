import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from downloaders import downloaders

app = typer.Typer()


def download_scheme(metadata: dict[str, Any], output_dir: Path) -> tuple[str, str]:
    downloader = downloaders.initialise(metadata)
    download_path, timestamp = downloader.download(output_dir)
    return str(download_path), timestamp


def download_schemes(output_dir, schemes, output_schemes_file=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    for scheme in schemes:
        print(f"Downloading {scheme['shortname']}", file=sys.stderr)
        download_path, timestamp = download_scheme(scheme, output_dir)
        scheme["db_path"] = download_path
        scheme["last_updated"] = timestamp
    with open(output_schemes_file, "w") as f_out:
        json.dump({"schemes": schemes}, f_out)
        json.dump({"schemes": schemes}, sys.stderr)


@app.command()
def one(
    scheme_name: Annotated[
        str,
        typer.Argument(
            help="Short name of schemes (e.g. 'saureus_1') as in the schemes.json file"
        ),
    ],
    schemes_file: Annotated[
        Path,
        typer.Option(
            "-s",
            "--schemes-file",
            help="Path to the source schemes.json file",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = Path("schemes.json"),
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
) -> None:
    selected_schemes = []
    with open(schemes_file, "r") as f:
        for scheme in json.load(f)["schemes"]:
            if scheme["shortname"] == scheme_name:
                selected_schemes.append(scheme)
                break
    download_schemes(output_dir, selected_schemes, output_schemes_file)


@app.command()
def full(
    schemes_file: Annotated[
        Path,
        typer.Option(
            "-s",
            "--schemes-file",
            help="Path to the schemes.json file",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = Path("schemes.json"),
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
) -> None:
    with open(schemes_file, "r") as f:
        schemes = json.load(f)["schemes"]
    download_schemes(output_dir, schemes, output_schemes_file)


if __name__ == "__main__":
    app()
