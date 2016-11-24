import json
import os
import re
import sys
import time
from threading import Thread
import signal
from datetime import datetime
import random

from gevent.queue import Queue, Full, Empty
from influxdb import InfluxDBClient
import gevent
from locust.core import TaskSet
from locust import HttpLocust, TaskSet, task, events, runners
from locust.exception import StopLocust
import requests
import statsd
import pandas as pd
import numpy as np

from loadgenerator import project, csrf
import metrics
import logparser

host = os.environ.get("LOCUST_STATSD_HOST", "localhost")
port = os.environ.get("LOCUST_STATSD_PORT", "8125")
STATSD = statsd.StatsClient(host, port, prefix='loadgenerator')
METRICS_EXPORT_PATH     = os.environ.get("LOCUST_METRICS_EXPORT", "measurements")
MEASUREMENT_NAME        = os.environ.get("LOCUST_MEASUREMENT_NAME", "measurement")
MEASUREMENT_DESCRIPTION = os.environ.get("LOCUST_MEASUREMENT_DESCRIPTION", "linear increase")
DURATION                = int(os.environ.get("LOCUST_DURATION", "20"))
print(DURATION)
USERS                   = int(os.environ.get("LOCUST_USERS", '10'))
HATCH_RATE              = float(os.environ.get("LOCUST_HATCH_RATE", "1"))
LOAD_TYPE               = os.environ.get("LOCUST_LOAD_TYPE", "constant") # linear, constant, random, nasa, worldcup
SPAWN_WAIT_MEAN         = int(os.environ.get("LOCUST_SPAWN_WAIT_MEAN", "10"))
SPAWN_WAIT_STD          = int(os.environ.get("LOCUST_SPAWN_WAIT_STD", "4"))
USER_MEAN               = int(os.environ.get("LOCUST_USER_MEAN", "40"))
USER_STD                = int(os.environ.get("LOCUST_USER_STD", "5"))
WAIT_MEAN               = int(os.environ.get("LOCUST_WAIT_MEAN", "10"))
WAIT_STD                = int(os.environ.get("LOCUST_WAIT_STD", "4"))
TIMESTAMP_START         = os.environ.get("LOCUST_TIMESTAMP_START", '1998-06-02 08:50:00')
TIMESTAMP_STOP          = os.environ.get("LOCUST_TIMESTAMP_STOP", '1998-06-02 09:50:00')
WEB_LOGS_PATH           = os.environ.get("LOCUST_LOG_PATH", "logs") # path to nasa/worldcup logs

def wait(self):
    gevent.sleep(random.normalvariate(WAIT_MEAN, WAIT_STD))
TaskSet.wait = wait

def login(l):
    resp = l.client.get("/login")
    l.csrf_token = csrf.find_in_page(resp.content)
    data = {
        "_csrf": l.csrf_token,
        "email": l.email,
        "password": "password"
    }
    r = l.client.post("/login", data)
    assert r.json().get("redir", None) == "/project"

def create_delete_project(l):
    d = {"_csrf": l.csrf_token, "projectName": "123", "template": None}
    r = l.client.post("/project/new", json=d)
    l.client.delete("/project/%s" % r.json()["project_id"],
                    params = {"_csrf": l.csrf_token},
                    name = "/project/[id]")

def settings(l):
    l.client.get("/user/settings")
    d = dict(_csrf=l.csrf_token, email=l.parent.email, first_name="foo", last_name="bar")
    assert l.client.post("/user/settings", json=d).text == "OK"

def stop(l):
    l.interrupt()

def register(l):
    l.client.get("/register")

def index(l):
    l.client.get("/")

class ProjectOverview(TaskSet):
    tasks = { project.Page: 30, create_delete_project: 2, stop: 1, settings: 1 }
    def on_start(self):
        r = self.client.get("/project")
        projects = re.search("projects: (\\[.*\\])", r.content, re.MULTILINE).group(1)
        self.projects = json.loads(projects)
        assert len(self.projects) > 0, "No project founds create some!"
        self.csrf_token = csrf.find_in_page(r.content)

user = 1
logins_per_acc = 2
class UserBehavior(TaskSet):
    tasks = {ProjectOverview: 10, register: 1, index: 1}
    def on_start(self):
        global user
        global logins_per_acc
        user += 1.0 / logins_per_acc
        self.email = "user%d@higgsboson.tk" % (int(user) % 300)
        print(self.email)
        login(self)

class WebsiteUser(HttpLocust):
    if LOAD_TYPE == "nasa" or LOAD_TYPE == "worldcup":
        def __init__(self, client_id, timestamps, queue):
            self.request_timestamps = timestamps
            self.request_number = 1
            self.client_id = client_id
            self.client_queue = queue
            super(WebsiteUser, self).__init__()
    task_set = UserBehavior

class RequestStats():
    def __init__(self):
        events.request_success += self.requests_success
        events.request_failure += self.requests_failure
        events.locust_error    += self.locust_error

    def requests_success(self, request_type="", name="", response_time=0, **kw):
        STATSD.timing(request_type + "-" + name, response_time)
        if not request_type.startswith("WebSocket"):
            print("%s - %s: %s" % (request_type, name, response_time))
	    STATSD.timing("requests_success", response_time)

    def requests_failure(self, request_type="", name="", response_time=0, exception=None, **kw):
        STATSD.timing(request_type + "-" + name + "-error", response_time)
        if not request_type.startswith("WebSocket"):
            print("%s - %s: %s" % (request_type, name, response_time))
	    STATSD.timing("requests_failure", response_time)

    def locust_error(self, locust_instance=None, exception=None, tb=None):
        STATSD.incr(locust_instance.__class__.__name__ + "-" + exception.__class__.__name__)
        STATSD.incr("requests_error")

def stop_measure(started_at):
    ended_at = datetime.utcnow()
    metadata = {}
    for k, v in os.environ.items():
        if k.startswith("LOCUST_"):
            name = k[len("LOCUST_"):]
            metadata[name.lower()] = v
    # compatibility
    metadata['name']        = metadata['measurement_name']
    metadata['description'] = metadata['measurement_description']
    metrics.export(metadata, started_at, ended_at)
    os.kill(os.getpid(), signal.SIGINT)

def constant_measure(*args, **kw):
    # wait for the load generator to take effect
    time.sleep(10)
    started_at = datetime.utcnow()
    time.sleep(DURATION)
    stop_measure(started_at)

def start_hatch(users, hatch_rate):
    payload = dict(locust_count=users, hatch_rate=hatch_rate)
    r = requests.post("http://localhost:8089/swarm", data=payload)
    print(r.text)

def print_color(text):
    print("\x1B[31;40m%s\x1B[0m" % text)

def process_requests(self):
    i = self.locust.request_number
    timestamps = self.locust.request_timestamps
    if i < timestamps.size:
	delta = (timestamps.iloc[i] - timestamps.iloc[i - 1]) / np.timedelta64(1, 's')
	print("client %s waits or %s" % (self.locust.client_id, delta))
	gevent.sleep(delta)
	self.locust.request_number += 1
    else:
        try:
	    idx, timestamps = self.locust.client_queue.get(timeout=1)
            self.client_id = idx
	    self.request_timestamps = timestamps
	    self.request_number = 1
        except Empty:
	    raise StopLocust("stop this instance")

def report_users():
    while True:
        try:
            val = runners.locust_runner.user_count
            STATSD.set("website_users", val)
        except SystemError as e:
            print("could not update `website_users` statsd counter: %s" % e)
        gevent.sleep(2)

GREENLETS = []
def replay_log_measure(df):
    TaskSet.wait = process_requests
    runner = runners.locust_runner
    locust = runner.locust_classes[0]
    start_hatch(0, 1)

    by_session = df.groupby(["started_at", "client_id", "session_id"])
    started_at = by_session.first().timestamp.iloc[0]
    real_started_at = datetime.utcnow()

    real_started_at = datetime.utcnow()
    queue = Queue(maxsize=1)
    runner.locusts.spawn(report_users)

    for idx, client in by_session:
        timestamps = client.timestamp
        now = timestamps.iloc[0]
        gevent.sleep((now - started_at) / np.timedelta64(1, 's'))
        print("sleep (%s - %s) %s" % (now, started_at, (now - started_at) / np.timedelta64(1, 's')))
        started_at = now
        def start_locust(_):
            try:
                l = WebsiteUser(idx[1], timestamps, queue)
                l.run()
            except gevent.GreenletExit:
                pass
        try:
	    queue.put((idx[1], timestamps), block=False)
        except Full:
            runner.locusts.spawn(start_locust, locust)
    stop_measure(real_started_at)

def random_measure():
    runner = runners.locust_runner
    locust = runner.locust_classes[0]
    def start_locust(_):
        try:
            locust().run()
        except gevent.GreenletExit:
            pass

    print_color("start hatching with %d/%d" % (USER_MEAN, len(runner.locusts)))
    start_hatch(0, 1)
    while USER_MEAN > len(runner.locusts):
        runner.locusts.spawn(start_locust, locust)
        time.sleep(2)

    started_at = datetime.utcnow()

    while True:
        seconds = (datetime.utcnow() - started_at).seconds
        if seconds > DURATION:
            break
        print("%d seconds left!" % (DURATION - seconds))
        new_user = -1
        while new_user < 0:
            new_user = int(random.normalvariate(USER_MEAN, USER_STD))

        print_color("new user %d clients" % new_user)
        if new_user > len(runner.locusts):
            while new_user > len(runner.locusts):
                runner.locusts.spawn(start_locust, locust)
                print("spawn user: now: %d" % len(runner.locusts))
                time.sleep(1)
        elif new_user < len(runner.locusts):
            locusts = list([l for l in runner.locusts])
            diff = len(locusts) - new_user
            if diff > 0:
                for l in random.sample(locusts, diff):
                    if new_user >= len(runner.locusts): break
                    try:
                        runner.locusts.killone(l)
                    except Exception as e:
                        print("failed to kill locust: %s" % e)
                    print("stop user: now: %d" % len(runner.locusts))
        STATSD.gauge("user", len(runner.locusts))
        wait = random.normalvariate(SPAWN_WAIT_MEAN, SPAWN_WAIT_STD)
        print_color("cooldown for %f" % wait)
        time.sleep(wait)
    stop_measure(started_at)

def read_log(type):
    if type == "nasa":
        read_log = logparser.read_nasa
    else: # "worldcup"
        read_log = logparser.read_worldcup
    df = read_log(WEB_LOGS_PATH)
    df = df[(df.timestamp > pd.Timestamp(TIMESTAMP_START)) & (df.timestamp < pd.Timestamp(TIMESTAMP_STOP))]
    filter = df["type"].isin(["HTML", "DYNAMIC", "DIRECTORY"])
    if type == "worldcup":
        #filter = filter & df.region.isin(["Paris", "SantaClara"])
        filter = filter & df.region.isin(["Paris"])
    return df[filter]

def session_number(v):
    diff = v.timestamp.diff(1)
    diff.fillna(0, inplace=True)
    sessions = (diff > pd.Timedelta(minutes=10)).cumsum()
    data = dict(client_id=v.client_id, timestamp=v.timestamp,
                session_id=sessions.values)
    return pd.DataFrame(data)

def started_at(v):
    data = dict(client_id=v.client_id, timestamp=v.timestamp, session_id=v.session_id,
                started_at=[v.timestamp.iloc[0]] * len(v.timestamp))
    return pd.DataFrame(data)

def group_log_by_sessions(df):
    df = df.sort_values("timestamp")
    per_client = df.groupby(df.client_id, sort=False)
    with_session = per_client.apply(session_number)
    by = [with_session.client_id, with_session.session_id]
    return with_session.groupby(by).apply(started_at)

def measure():
    RequestStats()
    time.sleep(5)
    if LOAD_TYPE == "constant":
        start_hatch(USERS, HATCH_RATE)
        events.hatch_complete += constant_measure
    elif LOAD_TYPE == "linear":
        start_hatch(USERS, HATCH_RATE)
        started_at = datetime.utcnow()
        def linear_measure(*args, **kw):
            stop_measure(started_at)
        events.hatch_complete += linear_measure
    elif LOAD_TYPE == "random":
        random_measure()
    elif LOAD_TYPE == "nasa" or LOAD_TYPE == "worldcup":
        df = read_log(LOAD_TYPE)
        replay_log_measure(group_log_by_sessions(df))
    else:
        sys.stderr.write("unsupported load type: %s" % LOAD_TYPE)
        sys.exit(1)

Thread(target=measure).start()
