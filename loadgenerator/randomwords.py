from . import ROOT_PATH
import os
import random

with open(os.path.join(ROOT_PATH, "words"), "r") as f:
    WORDS = map(lambda s: s.strip(), f.readlines())

def sample(minimum, maximum):
    return random.sample(WORDS, random.randint(minimum, maximum))
