import json
import os
import re
import sys
import time
from threading import Thread
import signal
from datetime import datetime
import random

from influxdb import InfluxDBClient
import gevent
from locust.core import TaskSet
from locust import HttpLocust, TaskSet, task, events, runners
import requests
import statsd

from loadgenerator import project, csrf
import metrics

host = os.environ.get("LOCUST_STATSD_HOST", "localhost")
port = os.environ.get("LOCUST_STATSD_PORT", "8125")
STATSD = statsd.StatsClient(host, port, prefix='loadgenerator')
METRICS_EXPORT_PATH     = os.environ.get("LOCUST_METRICS_EXPORT", "measurements")
MEASUREMENT_NAME        = os.environ.get("LOCUST_MEASUREMENT_NAME", "measurement")
MEASUREMENT_DESCRIPTION = os.environ.get("LOCUST_MEASUREMENT_DESCRIPTION", "linear increase")
DURATION                = int(os.environ.get("LOCUST_DURATION", "20"))
USERS                   = int(os.environ.get("LOCUST_USERS", '10'))
HATCH_RATE              = float(os.environ.get("LOCUST_HATCH_RATE", "1"))
LOAD_TYPE               = os.environ.get("LOCUST_LOAD_TYPE", "constant") # linear, constant, random
SPAWN_WAIT_MEAN         = int(os.environ.get("LOCUST_SPAWN_WAIT_MEAN", "10"))
SPAWN_WAIT_STD          = int(os.environ.get("LOCUST_SPAWN_WAIT_STD", "4"))
USER_MEAN               = int(os.environ.get("LOCUST_USER_MEAN", "40"))
USER_STD                = int(os.environ.get("LOCUST_USER_STD", "5"))
WAIT_MEAN               = int(os.environ.get("LOCUST_WAIT_MEAN", "10"))
WAIT_STD                = int(os.environ.get("LOCUST_WAIT_STD", "4"))

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
        user += 1.0 / logins_per_acc % 300
        self.email = "user%d@higgsboson.tk" % int(user)
        print(self.email)
        login(self)

class WebsiteUser(HttpLocust):
    task_set = UserBehavior

class RequestStats():
    def __init__(self):
        events.request_success += self.requests_success
        events.request_failure += self.requests_failure
        events.locust_error    += self.locust_error

    def requests_success(self, request_type="", name="", response_time=0, **kw):
        STATSD.timing(request_type + "-" + name, response_time)

    def requests_failure(self, request_type="", name="", response_time=0, exception=None, **kw):
        STATSD.incr(request_type + "-" + name + "-error")

    def locust_error(self, locust_instance=None, exception=None, tb=None):
        STATSD.incr(locust_instance.__class__.__name__ + "-" + exception.__class__.__name__)

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
    CSI="\x1B["
    reset=CSI+"m"
    print((CSI+"31;40m%s"+CSI+"0m") % text)

def random_measure():
    runner = runners.locust_runner
    locust = runner.locust_classes[0]
    def start_locust(_):
        try:
            locust().run()
        except gevent.GreenletExit:
            pass

    print_color("start hatching with %d/%d" % (USER_MEAN, len(runner.locusts)))
    start_hatch(1, 1)
    while USER_MEAN > len(runner.locusts):
        runner.locusts.spawn(start_locust, locust)
        time.sleep(2)

    started_at = datetime.utcnow()

    while True:
        if (datetime.utcnow() - started_at).seconds > DURATION:
            break
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
                    runner.locusts.killone(l)
                    print("stop user: now: %d" % len(runner.locusts))
        STATSD.gauge("user", len(runner.locusts))
        wait = random.normalvariate(SPAWN_WAIT_MEAN, SPAWN_WAIT_STD)
        print_color("cooldown for %f" % wait)
        time.sleep(wait)
    stop_measure(started_at)

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
    else: # "random"
        random_measure()

Thread(target=measure).start()
