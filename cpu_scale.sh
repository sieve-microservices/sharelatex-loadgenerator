#!/usr/bin/env bash
#s6-svc -t /run/s6/services/kapacitor-scale
#s6-svc -t /run/s6/services/kapacitor
set -eux
kapacitor \
    -url http://sharelatex-kapacitor-1.local:9092 \
    define \
    autoscaling \
    -type stream \
    -tick "$1" \
    -dbrp metrics.autogen
kapacitor -url http://sharelatex-kapacitor-1.local:9092 reload autoscaling
