import os
import sys
import asyncio
import faust
import logging
import json
import datetime
import html as _html
from uuid import uuid4
from dataclasses import dataclass
#from pythonjsonlogger.jsonlogger import JsonFormatter

from agents import Agent, Runner, set_default_openai_key, trace
from agents.model_settings import ModelSettings

# --- OpenAI & Model Settings ---
set_default_openai_key(os.environ["OPENAI_API_KEY"])
model_settings = ModelSettings(
    temperature=0.7,
    max_tokens=5000,
)

# --- Faust App & Kafka Topics ---
app = faust.App("learning_material_pipeline", broker="kafka://localhost:9092")

@dataclass
class Message(faust.Record):
    trace_id: str
    title: str
    content: str

# Define Kafka topics for each stage
topics = {
    'input':         app.topic('input',        value_type=Message),
    'background':    app.topic('background',   value_type=Message),
    'decomposition': app.topic('decomposition',value_type=Message),
    'planning':      app.topic('planning',     value_type=Message),
    'content':       app.topic('content',      value_type=Message),
    'final':         app.topic('final',        value_type=Message),
}

class SimpleJsonFormatter(logging.Formatter):
    def format(self, record):
        # Convert the LogRecord to a dict, then dump to a JSON string
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level":     record.levelname,
            "message":   record.getMessage(),
            **record.__dict__,
        }
        return json.dumps(payload)
# --- JSON Logging Setup ---
log_file = "pipeline_interactions.json"
log_handler = logging.FileHandler(log_file)
log_handler.setFormatter(SimpleJsonFormatter())
logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("aiokafka").setLevel(logging.DEBUG)
logging.getLogger("faust").setLevel(logging.DEBUG)

def log_event(event_type: str, topic: str, trace_id: str, payload: str):
    logger.info({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event":     event_type,
        "topic":     topic,
        "trace_id":  trace_id,
        "payload":   payload,
        "event_id":  str(uuid4()),
    })

# --- Define prompt templates ---
prompt_templates = {
    'input_parser_agent': {
        'system': "You are a JSON schema validator specialized in course pipelines.",
        'user':   "Please validate and normalize the following JSON payload. Ensure it contains exactly the keys 'title' and 'background'. Respond with a compact JSON string.\n\nData:\n{input}",
    },
    'background_analysis_agent': {
        'system': "You are an educational background analyst.",
        'user':   "Given the course title and background JSON, identify prerequisites, key learning objectives, and recommend a difficulty level ('Beginner', 'Intermediate', 'Advanced'). Respond in JSON with keys: 'prerequisites', 'objectives', 'difficulty'.\n\nData:\n{input}",
    },
    'topic_decomposition_agent': {
        'system': "You are an expert in breaking down topics into curriculum modules.",
        'user':   "Break down the course topic and background analysis into a list of modules. For each module, provide 'subtopic' and a concise 'learning outcome'. Respond as a JSON array named 'modules'.\n\nData:\n{input}",
    },
    'curriculum_planning_agent': {
        'system': "You are a curriculum planner optimizing lesson flow.",
        'user':   "Sequence the provided modules into a lesson plan. For each module, assign 'order', include 'subtopic', 'outcome', and estimate 'duration_minutes'. Wrap in a JSON object 'lesson_plan'.\n\nData:\n{input}",
    },
    'content_generation_agent': {
        'system': "You are a content creator for educational modules.",
        'user':   "Generate detailed instructional content for each lesson module. Include an explanatory section, an example, and a practice question. Respond in JSON mapping module 'order' to 'content'.\n\nData:\n{input}",
    },
}

# --- Instantiate Agents with system prompts ---
agents = {}
for key, prompts in prompt_templates.items():
    agents[key] = Agent(
        name=key.replace('_', ' ').title(),
        instructions=prompts['system'],
        model_settings=model_settings,
    )

# Helper: combine prompts and run agent
async def run_agent(agent_key: str, input_data: str):
    prompts = prompt_templates[agent_key]
    combined = (
        f"<|system|> {prompts['system']}\n<|endofsystem|>\n"
        f"{prompts['user'].format(input=input_data)}"
    )
    return await Runner.run(agents[agent_key], combined)

# --- Pipeline Stages ---
@app.agent(topics['input'])
async def input_stage(stream):
    async for msg in stream:
        log_event("consume", 'input', msg.trace_id, msg.content)
        with trace("Input Parser Phase"):
            res = await run_agent('input_parser_agent', msg.content)
            log_event("produce", 'background', msg.trace_id, res.final_output)
        anchor = msg.title.replace(' ', '-').replace("/", "-")
        with open("courses.html", "a", encoding="utf-8") as html_file:
            html_file.write(f"<section id='{anchor}-input'>\n<h3>Input Stage</h3>\n<pre>\n{_html.escape(res.final_output)}\n</pre>\n</section>\n")
        await topics['background'].send(
            value=Message(trace_id=msg.trace_id, title=msg.title, content=res.final_output)
        )

@app.agent(topics['background'])
async def background_stage(stream):
    async for msg in stream:
        log_event("consume", 'background', msg.trace_id, msg.content)
        with trace("Background Analysis Phase"):
            res = await run_agent('background_analysis_agent', msg.content)
            log_event("produce", 'decomposition', msg.trace_id, res.final_output)
        anchor = msg.title.replace(' ', '-').replace("/", "-")
        with open("courses.html", "a", encoding="utf-8") as html_file:
            html_file.write(f"<section id='{anchor}-background'>\n<h3>Background Analysis Stage</h3>\n<pre>\n{_html.escape(res.final_output)}\n</pre>\n</section>\n")
        await topics['decomposition'].send(
            value=Message(trace_id=msg.trace_id, title=msg.title, content=res.final_output)
        )

@app.agent(topics['decomposition'])
async def decomposition_stage(stream):
    async for msg in stream:
        log_event("consume", 'decomposition', msg.trace_id, msg.content)
        with trace("Topic Decomposition Phase"):
            res = await run_agent('topic_decomposition_agent', msg.content)
            log_event("produce", 'planning', msg.trace_id, res.final_output)
        anchor = msg.title.replace(' ', '-').replace("/", "-")
        with open("courses.html", "a", encoding="utf-8") as html_file:
            html_file.write(f"<section id='{anchor}-decomposition'>\n<h3>Topic Decomposition Stage</h3>\n<pre>\n{_html.escape(res.final_output)}\n</pre>\n</section>\n")
        await topics['planning'].send(
            value=Message(trace_id=msg.trace_id, title=msg.title, content=res.final_output)
        )

@app.agent(topics['planning'])
async def planning_stage(stream):
    async for msg in stream:
        log_event("consume", 'planning', msg.trace_id, msg.content)
        with trace("Curriculum Planning Phase"):
            res = await run_agent('curriculum_planning_agent', msg.content)
            log_event("produce", 'content', msg.trace_id, res.final_output)
        anchor = msg.title.replace(' ', '-').replace("/", "-")
        with open("courses.html", "a", encoding="utf-8") as html_file:
            html_file.write(f"<section id='{anchor}-planning'>\n<h3>Curriculum Planning Stage</h3>\n<pre>\n{_html.escape(res.final_output)}\n</pre>\n</section>\n")
        await topics['content'].send(
            value=Message(trace_id=msg.trace_id, title=msg.title, content=res.final_output)
        )

@app.agent(topics['content'])
async def content_stage(stream):
    async for msg in stream:
        log_event("consume", 'content', msg.trace_id, msg.content)
        with trace("Content Generation Phase"):
            res = await run_agent('content_generation_agent', msg.content)
            log_event("produce", 'final', msg.trace_id, res.final_output)
        anchor = msg.title.replace(' ', '-')
        with open("courses.html", "a", encoding="utf-8") as html_file:
            html_file.write(f"<section id='{anchor}-content'>\n<h3>Content Generation Stage</h3>\n<pre>\n{_html.escape(res.final_output)}\n</pre>\n</section>\n")
        await topics['final'].send(
            value=Message(trace_id=msg.trace_id, title=msg.title, content=res.final_output)
        )

@app.agent(topics['final'])
async def output_final(stream):
    async for msg in stream:
        log_event("consume", 'final', msg.trace_id, msg.content)
        print(f"\n✅ Final Course '{msg.title}' (Trace {msg.trace_id}):\n{msg.content}\n")
        anchor = msg.title.replace(' ', '-').replace("/", "-")
        with open("courses.html", "a", encoding="utf-8") as html_file:
            html_file.write(f"<section id='{anchor}-final'>\n<h2>Final Course</h2>\n<pre>\n{_html.escape(msg.content)}\n</pre>\n</section>\n")
            html_file.write("</div>\n</body></html>\n")
        await app.stop()
        sys.exit(0)

# --- Bootstrap: Read courses.json, write initial HTML, and start pipeline ---
_has_run = False
@app.timer(interval=1.0, on_leader=True)
async def initiate_pipeline_once():
    global _has_run
    if _has_run:
        return
    _has_run = True

    try:
        with open("courses.json", "r", encoding="utf-8") as f:
            courses = json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load courses.json: {e}")
        return

    # Initialize HTML with navigation and content container
    with open("courses.html", "w", encoding="utf-8") as html_file:
        html_file.write("<html><head><meta charset='utf-8'><title>Courses</title></head><body>\n")
        html_file.write("<h1>Courses</h1>\n<ul>\n")
        for course in courses:
            anchor = course['title'].replace(' ', '-').replace("/", "-")
            html_file.write(f"<li><a href='#{anchor}-final'>{course['title']}</a></li>\n")
        html_file.write("</ul>\n<div id='content'>\n")

    # Send each course into the pipeline
    for course in courses:
        trace_id = str(uuid4())
        payload = json.dumps({
            "title":      course["title"],
            "background": course["background"]
        })
        log_event("initiate", 'input', trace_id, payload)
        await topics['input'].send(
            value=Message(trace_id=trace_id, title=course['title'], content=payload)
        )

if __name__ == "__main__":
    app.main()
