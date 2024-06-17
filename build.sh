#!/usr/bin/env bash

TYPE=${1:-"all"}

if [ ${TYPE} = "all" ]; then
  PULL=""
else
  PULL="--pull"
fi

printf -v DATE '%(%Y-%m-%d)T' -1

echo ${DATE}

if [ ${TYPE} == "all" ] || [ ${TYPE} == "mlst" ]; then
  MLST_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-mlst
  docker ${PULL} build --rm -t ${MLST_IMAGE} --build-arg TYPE=mlst .
  docker push ${MLST_IMAGE}
fi

if [ ${TYPE} == "all" ] || [ ${TYPE} == "mlst2" ]; then
  MLST2_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-mlst2
  docker ${PULL} build --rm -t ${MLST2_IMAGE} --build-arg TYPE=alternative_mlst .
  docker push ${MLST2_IMAGE}
fi

if [ ${TYPE} == "all" ] || [ ${TYPE} == "cgmlst" ]; then
  CGMLST_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-cgmlst
  echo "Building ${CGMLST_IMAGE}"
  docker ${PULL} build --rm -t ${CGMLST_IMAGE} --build-arg TYPE=cgmlst .
  docker push ${CGMLST_IMAGE}
fi

if [ ${TYPE} == "all" ] || [ ${TYPE} == "ngstar" ]; then
  NGSTAR_IMAGE=registry.gitlab.com/cgps/pathogenwatch/analyses/typing-databases:${DATE}-ngstar
  docker ${PULL} build --rm -t ${NGSTAR_IMAGE} --build-arg SCHEME=ngstar .
  docker push ${NGSTAR_IMAGE}
fi
