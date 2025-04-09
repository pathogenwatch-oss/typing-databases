FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS build

COPY src uv.lock pyproject.toml LICENSE.md README.md /download_schemes/

WORKDIR /download_schemes

RUN uv build --wheel && mkdir /build && mv LICENSE.md README.md dist/*.whl /build/

FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS code

ARG VERSION
ENV VERSION="${VERSION}"

COPY --from=build /build /download_schemes

COPY config/host_config.json config/schemes.json /download_schemes/config/

COPY build.py /download_schemes/build.py

WORKDIR /download_schemes

RUN uv pip install --system download_schemes-"${VERSION}"-py3-none-any.whl

FROM code AS prod

# e.g. "-S 485 -S 573"
# This should be provided with the option flag even if only doing one.
ARG SCHEME
ENV SCHEME="${SCHEME}"
ARG BUILD_DATE
LABEL build_data=$BUILD_DATE

RUN --mount=type=secret,id=secrets \
    --mount=type=cache,target=/cache \
    download_schemes \
    -o db  \
    --secrets-file /run/secrets/secrets  \
    --secrets-cache-file /cache/secrets_cache.json \
    -l debug \
    $([ -n "${SCHEME}" ] && echo ${SCHEME})

ENTRYPOINT ["cat", "/db/schemes.json"]