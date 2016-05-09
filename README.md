
## Example usage:

```
$ export LOCUST_STATSD_HOST=172.17.0.7 \
    LOCUST_DURATION=360 \
    LOCUST_USERS=10 \
    LOCUST_METRICS_EXPORT="measurements" \
    LOCUST_MEASUREMENT_NAME="measurement" \
    LOCUST_MEASUREMENT_DESCRIPTION="linear increase" \
    LOCUST_INFLUXDB_SERVER="influxdb.local" \
    LOCUST_INFLUXDB_PORT="8086" \
    LOCUST_INFLUXDB_USER="influxdb" \
    LOCUST_INFLUXDB_PASSWORD="rewtrewt" \
    LOCUST_INFLUXDB_DB="metrics"
$ locust -H http://sharelatex.local
```
