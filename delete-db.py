from influxdb import InfluxDBClient
c = InfluxDBClient("influxdb.local", 8086, "influxdb", "rewtrewt", "metrics")
c.query("drop database metrics")
c.query("create database metrics")
