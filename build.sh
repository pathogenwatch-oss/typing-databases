#!/usr/bin/env bash

printf -v DATE '%(%Y-%m-%d)T\n' -1

echo ${DATE}

MLST_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-mlst
MLST2_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-mlst2
CGMLST_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-cgmlst
NGSTAR_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-ngstar


docker --pull build --rm -t ${MLST_IMAGE} --build-arg TYPE=mlst .
docker build --rm -t ${MLST2_IMAGE} --build-arg TYPE=alternative_mlst .
docker build --rm -t ${CGMLST_IMAGE} --build-arg TYPE=cgmlst .
docker build --rm -t ${NGSTAR_IMAGE} --build-arg SCHEME=ngstar .

docker push ${MLST_IMAGE}
docker push ${MLST2_IMAGE}
docker push ${CGMLST_IMAGE}
docker push ${NGSTAR_IMAGE}