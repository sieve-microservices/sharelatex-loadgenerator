from influxdb import InfluxDBClient
from itertools import imap
from datetime import datetime, timedelta
import time
import heapq
import csv
import json
import os.path

server = os.environ.get("LOCUST_INFLUXDB_SERVER", "localhost")
port = int(os.environ.get("LOCUST_INFLUXDB_PORT", "8086"))
user = os.environ.get("LOCUST_INFLUXDB_USER", None)
password = os.environ.get("LOCUST_INFLUXDB_PASSWORD", None)
database = os.environ.get("LOCUST_INFLUXDB_DB", "metrics")

DB = InfluxDBClient(server, port, user, password, database)

def pad(d):
    return str(d) + "00"

SKIP_PREFIX = ["container_id", "host", "time"]

def scroll(query, begin, until, prefix=None):
    diff = timedelta(minutes=4)
    while begin < until:
        to = min(begin + diff, until)
        res = DB.query(query % (pad(begin), pad(to)))
        for batch in res:
            for row in batch:
                # truncate longer ids to match with shorter host names
                if "container_id" in row:
                    row["container_id"] = row["container_id"][0:11]

                time_col = row["time"][0:min(26, len(row["time"]) - 1)]
                t = time.strptime(time_col, "%Y-%m-%dT%H:%M:%S.%f")

                if prefix is not None:
                    for key in row.iterkeys():
                        if key not in SKIP_PREFIX:
                            row["-".join((prefix, key))] = row.pop(key)
                yield (time.mktime(t), row)
        begin = to

class Application:
    def __init__(self, n, t, f):
        self.name = n
        self.filename = n + ".tsv"
        self.tags = list(t)
        self.tags.sort()
        self.fields = list(f)
        self.fields.sort()
    def __json__(s):
        return {"name": s.name,
                "filename": s.filename, "tags": s.tags, "fields": s.fields}


class Metadata():
    start = None
    end = None
    services = []
    description = ""
    def __json__(s):
        return {"start": s.start, "end": s.end, "services": s.services, "description": s.description, "name": s.name}

def dump_column_names(app):
    def query(what):
        names = set()
        result = DB.query(what % app)
        for name, cols in result.items():
            for col in cols:
                col = col.values()[0]
                if name[0] == app and col not in SKIP_PREFIX:
                    col = "-".join((app, col))
                names.add(col)
        return names
    tags = query('SHOW TAG KEYS FROM "%s", /docker_container.*/')
    fields = query('SHOW FIELD KEYS FROM "%s", /docker_container.*/')

    if "container_id" in fields:
        fields.remove("container_id")
        tags.add("container_id")

    return Application(app, tags, fields)

SYSTEM_METRICS = ["cpu", "blkio", "mem", "net"]

def dump_app(app_name, path, begin, now):
    app = dump_column_names(app_name)
    queries = []
    for system in SYSTEM_METRICS:
        q = "select * from \"docker_container_{}\" where container_image =~ /.*{}:latest$/ and time > '%s' and time < '%s'".format(system, app.name)
        queries.append(scroll(q, begin, now))
    q = "select * from \"{}\" where time > '%s' and time < '%s'".format(app.name)
    queries.append(scroll(q, begin, now, prefix=app.name))
    path = os.path.join(path, app.filename)
    with open(path, "w+") as f:
        columns = app.fields + app.tags + ["time"]
        writer = csv.DictWriter(f, fieldnames=columns, dialect=csv.excel_tab, extrasaction='ignore')
        writer.writeheader()
        for _, row in heapq.merge(*queries):
            writer.writerow(row)
    return app

APPS = ["chat",
        "clsi",
        "contacts",
        "doc-updater",
        "docstore",
        "filestore",
        "haproxy",
        "mongodb",
        "postgresql",
        "real-time",
        "redis",
        "spelling",
        "tags",
        "track-changes",
        "web",
        "loadgenerator"]

class Encoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__json__'):
            return obj.__json__()
        return json.JSONEncoder.default(self, obj)

def export(name, description, path, start, end):
    queries = []
    metadata = Metadata()
    metadata.name = name
    metadata.start = start.isoformat() + "Z"
    metadata.end = end.isoformat() + "Z"
    metadata.description = description

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S-")
    path = os.path.join(path, ts + name)
    if not os.path.isdir(path):
        os.makedirs(path)

    for app in APPS:
        metadata.services.append(dump_app(app, path, start, end))
    with open(os.path.join(path, "metadata.json"), "w+") as f:
        json.dump(metadata, f, cls=Encoder, sort_keys=True, indent=4)
        f.flush()

if __name__ == '__main__':
    end = datetime.utcnow()
    start = end - timedelta(minutes=1)
    import pdb; pdb.set_trace()
    export("test", "test export", "test", start, end)
