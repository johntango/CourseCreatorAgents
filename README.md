# CourseCreatorAgents

# Pub-Sub Capability Added

### You should run Python 3.11 but NOT 3.12 or higher

### In CodeSpaces this is specified in .devcontainer/devcontainer.json

#

## Make sure you load faust-streaming and not an older version

pip uninstall faust -y
pip uninstall faust-streaming -y # in case a half-installed one exists

pip install faust-streaming

## check the version

pip show faust-streaming

# we run redpanda in a docker container.

### in terminal window - run docker to spin up redpanda version v24.3.18

docker run -d --name=redpanda -p 9092:9092 -p 9644:9644 redpandadata/redpanda:v24.3.18 redpanda start --overprovisioned --smp 1 --memory 1G --reserve-memory 0M --node-id 0 --check=false --kafka-addr PLAINTEXT://0.0.0.0:9092 --advertise-kafka-addr PLAINTEXT://localhost:9092

### This should return and you should check the container is running.

## now pip install -r requirements.txt

### in the code faust-streaming is referenced as `faust` so we import it as such

import os
import asyncio
import faust
import logging
import json
from pythonjsonlogger import jsonlogger
from agents import Agent, Runner, set_default_openai_key, trace
from agents.model_settings import ModelSettings
from uuid import uuid4
import datetime
from dataclasses import dataclass

# Faust setup in python code

app = faust.App("agent_pipeline", broker="kafka://localhost:9092")
...

### Now in Terminal Window launch program agent.py

python debugAgents.py worker -l info

## You should see something like this

Starting Faust app...
┌ƒaµS† v0.11.3┬────────────────────────────────────────────────────────┐
│ id │ agent_pipeline │
│ transport │ [URL('kafka://localhost:9092')] │
│ store │ memory: │
│ web │ http://localhost:6066/ │
│ log │ -stderr- (info) │
│ pid │ 21744 │
│ hostname │ codespaces-ac1c94 │
│ platform │ CPython 3.11.4 (Linux x86_64) │
│ + │ Cython (GCC 10.2.1 20210110) │
│ drivers │ │
│ transport │ aiokafka=0.12.0 │
│ web │ aiohttp=3.12.14 │
│ datadir │ /workspaces/CourseCreatorAgents/agent_pipeline-data │
│ appdir │ /workspaces/CourseCreatorAgents/agent_pipeline-data/v1 │
└─────────────┴────────────────────────────────────────────────────────┘
