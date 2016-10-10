import requests
import os
import sys
import argparse
import time

# debug python-requests
#import logging
#logging.basicConfig(level=logging.DEBUG)

class Rancher():
    def __init__(self, baseurl, user, password):
        if baseurl.endswith("/"):
            self.baseurl = baseurl
        else:
            self.baseurl = baseurl + "/"
        self.user = user
        self.password = password

    def auth(self):
        return (self.user, self.password)

    def get(self, path):
        return requests.get(self.baseurl + path, auth=self.auth())

    def put(self, path, data):
        return requests.put(self.baseurl + path, auth=self.auth(), data=data)

    def services(self, stack_id):
        return self.get("v1/environments/%s/services" % stack_id).json()

    def environments(self):
        return self.get("v1/environments/").json()

    def scale(self, id, count):
        return self.put("v1/services/%s" % id, data=dict(scale=count))

RANCHER_URL = os.environ.get("RANCHER_URL", "localhost:8080")
RANCHER_ACCESS_KEY = os.environ.get("RANCHER_ACCESS_KEY")
RANCHER_SECRET_KEY = os.environ.get("RANCHER_SECRET_KEY")


def parse_args():
    parser = argparse.ArgumentParser(prog='PROG', usage='%(prog)s [options]')
    parser.add_argument('--scale', default=1, help="scale all rancher services to this number (default: 1)")
    parser.add_argument('stack', help='name of the rancher stack to use')
    parser.add_argument('services', help='service names seperated by comma')
    return parser.parse_args()


def find_stack(rancher, stack_name):
    envs = rancher.environments()
    for environment in envs["data"]:
        if environment["name"] == stack_name:
            return environment["id"]


def die(msg):
    sys.stderr.write(msg)
    sys.stderr.write("\n")
    sys.exit(1)


def wait_finished(rancher, stack_id):
    scaling = True
    while scaling:
        scaling = False
        for srv in rancher.services(stack_id)["data"]:
            if "currentScale" in srv and srv["currentScale"] != srv["scale"]:
                scaling = True
                break
        time.sleep(1)

def main():
    if RANCHER_ACCESS_KEY is None or RANCHER_SECRET_KEY is None:
        die("RANCHER_ACCESS_KEY or RANCHER_SECRET_KEY have to expored")
    args = parse_args()
    rancher = Rancher(RANCHER_URL, RANCHER_ACCESS_KEY, RANCHER_SECRET_KEY)
    stack_id = find_stack(rancher, args.stack)
    if stack_id is None:
        die("could not find rancher stack with name %s" % args.stack)
    services = rancher.services(stack_id)
    scale_services = set(args.services.split(","))
    for service in services["data"]:
        if service["name"] in scale_services:
            r = rancher.scale(service["id"], args.scale)
    wait_finished(rancher, stack_id)

if __name__ == "__main__":
    # example:
    # python scale-rancher.py --scale 2 sharelatex clsi,chat,contacts,docstore,tags,doc-updater,real-time,track-changes,web
    main()
