import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import docker
import typer

datestamp_format = "%Y-%m-%d"


def build_image(
    scheme: dict[str, Any], tag_base: str, base: str = "typing-databases"
) -> str:
    tag = f"{base}:{tag_base}-{scheme['shortname']}"
    client = docker.from_env()
    _, logs = client.images.build(
        path=".",
        tag=tag,
        rm=True,
        buildargs={
            "COMMAND": f"one {scheme['shortname']}",
            "BUILD_DATE": datetime.now().strftime(datestamp_format),
        },
    )
    for line in logs:
        print(line, file=sys.stderr)
    return tag


def build(
    scheme_file: Annotated[
        Path,
        typer.Option(
            "-s", "--schemes-file", exists=True, file_okay=True, dir_okay=False
        ),
    ] = Path("schemes.json"),
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
) -> None:
    with open(scheme_file, "r") as sf:
        for scheme in json.load(sf)["schemes"]:
            if (
                (selection is not None and scheme["shortname"] in selection)
                or (scheme_type is not None and scheme["type"] in scheme_type)
                or (selection is None and scheme_type is None)
            ):
                print(f"Building scheme {scheme['shortname']}", file=sys.stderr)
                image_name = build_image(scheme, image_tag, image_base_name)
                print(
                    f"{scheme['shortname']},{image_tag},{image_name}",
                    file=sys.stdout,
                    end="\n",
                )


if __name__ == "__main__":
    typer.run(build)
