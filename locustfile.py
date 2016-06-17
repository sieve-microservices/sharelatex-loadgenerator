import json
import os
import re
import sys
import time
from threading import Thread
import metrics
import signal
from datetime import datetime
import gevent
import random
from locust import runners

import requests
import statsd
from locust import HttpLocust, TaskSet, task, events
from loadgenerator import project, csrf
from influxdb import InfluxDBClient

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
    def on_start(self):
        r = self.client.get("/project")
        projects = re.search("projects: (\\[.*\\])", r.content, re.MULTILINE).group(1)
        self.projects = json.loads(projects)
        assert len(self.projects) > 0, "No project founds create some!"
        self.csrf_token = csrf.find_in_page(r.content)
    tasks = { project.Page: 30, create_delete_project: 2, stop: 1, settings: 1 }

user = 1
logins_per_acc = 2
class UserBehavior(TaskSet):
    tasks = {ProjectOverview: 10, register: 1, index: 1}
    def on_start(self):
        global user
        global logins_per_acc
        user += 1.0 / logins_per_acc
        self.email = "user%d@higgsboson.tk" % int(user)
        print(self.email)
        login(self)

class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 5000
    max_wait = 9000

host = os.environ.get("LOCUST_STATSD_HOST", "localhost")
port = os.environ.get("LOCUST_STATSD_PORT", "8125")
STATSD = statsd.StatsClient(host, port, prefix='loadgenerator')

class RequestStats():
    def __init__(self):
        events.request_success += self.requests_stats
        events.request_failure += self.requests_stats
    def requests_stats(self, request_type="", name="", response_time=0, **kw):
        STATSD.timing(request_type + "-" + name, response_time)

METRICS_EXPORT_PATH     = os.environ.get("LOCUST_METRICS_EXPORT", "measurements")
MEASUREMENT_NAME        = os.environ.get("LOCUST_MEASUREMENT_NAME", "measurement")
MEASUREMENT_DESCRIPTION = os.environ.get("LOCUST_MEASUREMENT_DESCRIPTION", "linear increase")
DURATION                = int(os.environ.get("LOCUST_DURATION", "20"))
USERS                   = int(os.environ.get("LOCUST_USERS", '10'))
HATCH_RATE              = float(os.environ.get("LOCUST_HATCH_RATE", "1"))
LOAD_TYPE               = os.environ.get("LOCUST_LOAD_TYPE", "constant") # linear, constant, random
RANDOM_MINWAIT          = os.environ.get("LOCUST_RANDOM_MINWAIT", 2)
RANDOM_MAXWAIT          = os.environ.get("LOCUST_RANDOM_MAXWAIT", 4)
START_STOP_RATIO        = os.environ.get("START_STOP_RATIO", 1)


def stop_measure(started_at):
    ended_at = datetime.utcnow()
    metrics.export(MEASUREMENT_NAME, MEASUREMENT_DESCRIPTION, METRICS_EXPORT_PATH, started_at, ended_at)
    os.kill(os.getpid(), signal.SIGINT)

def constant_measure(*args, **kw):
    # wait for the load generator to take effect
    time.sleep(10)
    started_at = datetime.utcnow()
    time.sleep(DURATION)
    stop_measure(started_at)

def random_measure():
    runner = runners.locust_runner
    locust = runner.locust_classes[0]
    def start_locust(_):
        try:
            locust().run()
        except gevent.GreenletExit:
            pass
    start = START_STOP_RATIO / (1.0 + START_STOP_RATIO)
    stop = 1 - start

    payload = dict(locust_count=locust_count, hatch_rate=1)
    r = requests.post("http://localhost:8089/swarm", data=payload)
    time.sleep(1)

    started_at = datetime.utcnow()

    while True:
        if (datetime.utcnow() - started_at).seconds > DURATION:
            break
        if random.random() < start:
            runner.locusts.spawn(start_locust, locust)
        else:
            runner.kill_locusts(1)
        wait = random.randrange(RANDOM_MINWAIT * 1000, RANDOM_MAXWAIT * 1000) / 1000.0
        gevent.sleep(wait)
    stop_measure(started_at)

def measure():
    time.sleep(5)
    RequestStats()
    if LOAD_TYPE == "constant":
        payload = dict(locust_count=USERS, hatch_rate=HATCH_RATE)
        r = requests.post("http://localhost:8089/swarm", data=payload)
        print(r.text)
        #runners.locust_runner.start_hatching(USERS, HATCH_RATE)
        events.hatch_complete += constant_measure
    elif LOAD_TYPE == "linear":
        payload = dict(locust_count=USERS, hatch_rate=HATCH_RATE)
        r = requests.post("http://localhost:8089/swarm", data=payload)
        print(r.text)
        #runners.locust_runner.start_hatching(USERS, HATCH_RATE)
        started_at = datetime.utcnow()
        def linear_measure(*args, **kw):
            stop_measure(started_at)
        events.hatch_complete += linear_measure
    else: # "random"
        random_measure()

Thread(target=measure).start()
