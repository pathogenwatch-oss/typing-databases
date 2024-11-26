import json
import sys
from pathlib import Path
from typing import Annotated

import typer

required_fields = [
    "shortname",
    "host",
    "scheme_id",
    "type",
    "cite",
    "name",
    "targets",
]

pubmlst_required = ["host_path"]


def scheme_cleaner(
    schemes_file: Annotated[
        Path,
        typer.Option(
            "-s", "--schemes-file", exists=True, file_okay=True, dir_okay=False
        ),
    ] = "schemes.json",
):
    new_schemes = {"schemes": []}
    with open(schemes_file, "r") as f:
        schemes = json.load(f)["schemes"]
        for scheme in schemes:
            if "host" not in scheme.keys():
                scheme["host"] = "pubmlst"
            if "type" not in scheme.keys():
                raise Exception(f"Missing type for {scheme['shortname']}")
            if "scheme_id" not in scheme.keys() and (
                scheme["type"] == "mlst" or scheme["type"] == "alternative_mlst"
            ):
                scheme_file = Path(scheme["path"]) / ".bin" / "download"
                with open(scheme_file, "r") as s_f:
                    for line in s_f:
                        if line.startswith("SCHEME="):
                            scheme_name = line.split("=")[1].strip().replace('"', "")
                        if "--scheme-id" in line:
                            scheme["scheme_id"] = (
                                line.strip().split("--scheme-id ")[1].split()[0]
                            )
                    if scheme_name is None:
                        raise Exception(
                            f"Unable to find the scheme_name for {scheme['shortname']}"
                        )
                    if "scheme_id" not in scheme or scheme["scheme_id"] is None:
                        raise Exception(
                            f"Unable to find the MLST scheme_id for {scheme['shortname']}"
                        )
                    scheme[
                        "host_path"
                    ] = f"{scheme['host']}_{scheme_name}_{scheme['scheme_id']}"
            final_record = {}
            for field in required_fields:
                if field not in scheme.keys():
                    raise Exception(f"Missing {field} for {scheme['shortname']}")
                final_record[field] = scheme[field]
            if scheme["host"] == "pubmlst":
                for field in pubmlst_required:
                    if field not in scheme.keys():
                        raise Exception(f"Missing {field} for {scheme['shortname']}")
                    final_record[field] = scheme[field]
            new_schemes["schemes"].append(final_record)
    print(json.dumps(new_schemes, indent=4), file=sys.stdout)


if __name__ == "__main__":
    typer.run(scheme_cleaner)
