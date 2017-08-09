#!/bin/sh

# Figure out which cluster we are on
CLUSTER=`hostname | sed 's/\([a-zA-Z][a-zA-Z]*\)[0-9]*/\1/g'`

if [ "${CLUSTER}" == "surface" ]; then
  CMD='spack setup lbann@local +gpu %gcc@7.1.0 ^elemental@master+cublas ^mvapich2@2.2'
else
  CMD='spack setup lbann@local %gcc@7.1.0 ^elemental@master ^mvapich2@2.2'
fi

echo $CMD
echo $CMD > build_lbann.sh
chmod +x build_lbann.sh
$CMD