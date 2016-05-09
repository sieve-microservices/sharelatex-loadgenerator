from influxdb import InfluxDBClient
c = InfluxDBClient("influxdb.local", 8086, "influxdb", "rewtrewt", "metrics")
c.query("drop database metrics")
c.query("create database metrics")
#for batch in c.query("show measurements"):
#    for m in batch:
#        q = 'drop measurement "%s"' % (m["name"].replace('\\', '\\\\'))
#        print(q)
#        c.query(q)
