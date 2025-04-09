# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-on-whales",
#     "toml",
#     "typer",
# ]
# ///

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import toml
import typer
from python_on_whales import DockerClient

# Configure docker client to use the socket
docker = DockerClient(host="unix:///var/run/docker.sock")

datestamp_format = "%Y-%m-%d"

app = typer.Typer(pretty_exceptions_show_locals=False,pretty_exceptions_short=False)

def get_version_from_pyproject() -> str:
    try:
        with open("pyproject.toml", "r") as pyproject_file:
            pyproject_data = toml.load(pyproject_file)
            return pyproject_data["project"]["version"]
    except (FileNotFoundError, KeyError):
        print("Warning: Unable to read version from pyproject.toml. Using default version.", file=sys.stderr)
        return "0.0.0"


def build_image(
    image_name: str,
    tag_base: str,
    scheme: dict[str, Any],
    cache_dir: Path,
    secrets_file: Path,
    version: str,
) -> str:
    tag = f"{image_name}:{tag_base}-{scheme['shortname']}"

    build_args = {
        "SCHEME": f'-S {scheme["shortname"]}',
        "BUILD_DATE": datetime.now().strftime(datestamp_format),
        "VERSION": version
    }

    result = docker.build(
        ".",
        tags=[tag],
        build_args=build_args,
        cache_from=[{"type": "local", "src": str(cache_dir)}],
        cache_to=f"type=local,dest={cache_dir}",
        secrets=[f'id=secrets,src={secrets_file.absolute()}'],
        progress="plain",
    )

    print(result, file=sys.stderr)
    return tag


@app.command()
def build(
    scheme_file: Annotated[
        Path,
        typer.Option(
            "-s", "--schemes-file", exists=True, file_okay=True, dir_okay=False
        ),
    ] = Path("config/schemes.json"),
    selection: Annotated[
        list[str],
        typer.Option(
            "-n",
            "--short-name",
            help="Specify one or more typing schemes using their short names as in the "
            "schemes.json file. If none are specified, all schemes will be built.",
        ),
    ] = None,
    scheme_type: Annotated[
        list[str],
        typer.Option(
            "-t",
            "--type",
            help="Specify one or more typing schemes using their type as in the "
            "schemes.json file (e.g. 'mlst'). If none are specified, all schemes will "
            "be built.",
        ),
    ] = None,
    image_base_name: Annotated[
        str,
        typer.Option(
            "-p",
            "--image-path",
            help="Specify the base name of the docker image",
        ),
    ] = "registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases",
    image_tag: Annotated[
        str,
        typer.Option(
            "-l",
            "--image-label",
            help="Specify the tag of the docker image. The current date will be used as"
            f" a default: '{datetime.today().strftime(datestamp_format)}'",
        ),
    ] = datetime.today().strftime("%Y-%m-%d"),
    secrets_file: Annotated[
        Path,
        typer.Option(
            "-S", "--secrets-file", exists=True, file_okay=True, dir_okay=False
        ),
    ] = Path("secrets.json"),
    cache_dir: Annotated[
        Path, typer.Option("-C", "--cache-dir", file_okay=False, dir_okay=True)
    ] = Path("cache_dir"),
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    version = get_version_from_pyproject()
    
    with open(scheme_file, "r") as sf:
        for scheme in json.load(sf)["schemes"]:
            if (
                (selection is not None and scheme["shortname"] in selection)
                or (scheme_type is not None and scheme["type"] in scheme_type)
                or (selection is None and scheme_type is None)
            ):
                print(f"Building scheme {scheme['shortname']}", file=sys.stderr)
                image_name = build_image(
                    image_base_name,
                    image_tag,
                    scheme,
                    cache_dir,
                    secrets_file,
                    version
                )
                print(
                    f"{scheme['shortname']},{image_tag},{image_name}",
                    file=sys.stdout,
                    end="\n",
                )


if __name__ == "__main__":
    app()
