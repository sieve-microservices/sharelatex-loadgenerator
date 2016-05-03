import json
import os
import re
import sys
import time
from threading import Thread

import requests
from locust import HttpLocust, TaskSet, task

from loadgenerator import project, csrf

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

def start_swarm():
    time.sleep(1)
    payload = {
            'locust_count': os.environ.get("LOCUST_USERS", '10'),
            'hatch_rate': os.environ.get("LOCUST_HATCH_RATE", '1')
            }
    r = requests.post("http://localhost:8089/swarm", data=payload)
    print(r.text)

Thread(target=start_swarm).start()
