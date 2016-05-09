import json
import os
import re
import sys
import time
from threading import Thread
import metrics
import signal
from datetime import datetime

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
    min_wait=5000
    max_wait=9000

host = os.environ.get("LOCUST_STATSD_HOST", "localhost")
port = os.environ.get("LOCUST_STATSD_PORT", "8125")
STATSD = statsd.StatsClient(host, port, prefix='loadgenerator')

class RequestStats():
    def __init__(self):
        events.request_success += self.requests_stats
        events.request_failure += self.requests_stats
    def requests_stats(self, request_type="", name="", response_time=0, **kw):
        STATSD.timing(request_type + "-" + name, response_time)

def start_measure(*args, **kw):
    time.sleep(10) # wait for the load generator to take effect
    path = os.environ.get("LOCUST_METRICS_EXPORT", "measurements")
    name = os.environ.get("LOCUST_MEASUREMENT_NAME", "measurement")
    desc = os.environ.get("LOCUST_MEASUREMENT_DESCRIPTION", "linear increase")
    start = datetime.utcnow()
    time.sleep(int(os.environ.get("LOCUST_DURATION", "20")))
    end = datetime.utcnow()
    metrics.export(name, desc, path, start, end)
    os.kill(os.getpid(), signal.SIGINT)

events.hatch_complete += start_measure

def measure():
    time.sleep(1)
    users = os.environ.get("LOCUST_USERS", '10')

    change_swarm(users, os.environ.get("LOCUST_HATCH_RATE", "1"))
    RequestStats()

def change_swarm(count, rate):
    payload = dict(locust_count=count, hatch_rate=rate)
    r = requests.post("http://localhost:8089/swarm", data=payload)
    print(r.text)

Thread(target=measure).start()
