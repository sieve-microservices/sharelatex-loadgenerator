#!/usr/bin/env bash

export LOCUST_DURATION=3600
export LOCUST_WAIT_MEAN=10
export LOCUST_WAIT_STD=4
export LOCUST_HATCH_RATE=4
export LOCUST_SPAWN_WAIT_MEAN=40
export LOCUST_SPAWN_WAIT_STD=10
export LOCUST_USER_MEAN=40
export LOCUST_USER_STD=20
export LOCUST_MEASUREMENT_DESCRIPTION="normal distributed number of users with normal distributed wait"
export ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export LOCUST_USERS=10
export LOCUST_METRICS_EXPORT="measurements"
export LOCUST_MEASUREMENT_NAME="measurement"
export LOCUST_MEASUREMENT_DESCRIPTION="linear increase"
export LOCUST_INFLUXDB_SERVER="influxdb.local"
export LOCUST_INFLUXDB_PORT="8086"
export LOCUST_INFLUXDB_USER="influxdb"
export LOCUST_INFLUXDB_PASSWORD="rewtrewt"
export LOCUST_INFLUXDB_DB="metrics"
export LOCUST_STATSD_HOST="telegraf.local"

#for i in $(seq 1 1); do
#    export LOCUST_USERS=70
#    export LOCUST_LOAD_TYPE=constant
#    export LOCUST_MEASUREMENT_NAME="70-constant-users-60min-$i"
#    locust -H http://sharelatex.local
#done

#for j in $(seq 1 4); do
#  #python scale-rancher.py --scale "$j" sharelatex clsi,chat,contacts,docstore,tags,doc-updater,real-time,track-changes,web
#  python scale-rancher.py --scale "$j" sharelatex clsi,chat,contacts,docstore,tags,doc-updater,track-changes,web
#  for i in $(seq 1 5); do
#    export LOCUST_DURATION=1200
#    export LOCUST_USER_MEAN=25
#    export LOCUST_USER_STD=10
#    export LOCUST_LOAD_TYPE=random
#    export LOCUST_MEASUREMENT_NAME="random-users-mean25-std10-20min-scale${j}-${i}"
#    locust -H http://sharelatex.local
#  done
#done

export LOCUST_USERS=40
export LOCUST_LOAD_TYPE=worldcup
export LOCUST_LOG_PATH="${ROOT_DIR}/logs/wc_day38_1.gz"
export LOCUST_TIMESTAMP_START="1998-06-02 08:50:00"
export LOCUST_TIMESTAMP_STOP="1998-06-02 09:50:00"
#export LOCUST_TIMESTAMP_START="1998-06-02 09:30:00"
#export LOCUST_TIMESTAMP_STOP="1998-06-02 09:35:00"
export LOCUST_MEASUREMENT_NAME="worldcup98-http-scale"
./cpu_scale.sh http_request_scale.tick
locust -H http://sharelatex.local
export LOCUST_MEASUREMENT_NAME="worldcup98-cpu-scale"
./cpu_scale.sh cpu_scale.tick
locust -H http://sharelatex.local

#for i in $(seq 1 5); do
#    export LOCUST_USERS=70
#    export LOCUST_HATCH_RATE="0.019444444444444445" # 70.0/(60 * 60)
#    export LOCUST_LOAD_TYPE=linear
#    export LOCUST_MEASUREMENT_NAME="70-linear-users-60min-$i"
#    locust -H http://sharelatex.local
#done

#export LOCUST_DURATION=90
#export LOCUST_USERS=40
#export LOCUST_LOAD_TYPE=random
#export LOCUST_MEASUREMENT_NAME="test-load"
#locust -H http://sharelatex.local
