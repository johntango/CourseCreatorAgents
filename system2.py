import os
import asyncio
import faust
import logging
import json
import datetime
import html as _html
from uuid import uuid4
from dataclasses import dataclass
from pythonjsonlogger import jsonlogger

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
    'input': app.topic('input', value_type=Message),
    'background': app.topic('background', value_type=Message),
    'decomposition': app.topic('decomposition', value_type=Message),
    'planning': app.topic('planning', value_type=Message),
    'content': app.topic('content', value_type=Message),
    'images': app.topic('images', value_type=Message),
    'exercises': app.topic('exercises', value_type=Message),
    'mini_project': app.topic('mini_project', value_type=Message),
    'quiz': app.topic('quiz', value_type=Message),
    'grading': app.topic('grading', value_type=Message),
    'feedback': app.topic('feedback', value_type=Message),
    'adaptation': app.topic('adaptation', value_type=Message),
    'delivery': app.topic('delivery', value_type=Message),
    'final': app.topic('final', value_type=Message),
    'analytics': app.topic('analytics', value_type=Message),
}

# --- JSON Logging Setup ---
log_file = "pipeline_interactions.json"
log_handler = logging.FileHandler(log_file)
log_handler.setFormatter(jsonlogger.JsonFormatter())
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

# --- Define Agents ---
agents = {}
agent_specs = [
    ("input_parser_agent",     "Ingest JSON, validate schema, normalize fields."),
    ("background_analysis_agent", "Analyze background, detect prerequisites, set difficulty."),
    ("topic_decomposition_agent", "Decompose title into sub-topics, objectives."),
    ("curriculum_planning_agent", "Sequence sub-topics into a lesson plan."),
    ("content_generation_agent", "Generate instructional text for each segment."),
    ("images_agent",            "Produce/source diagrams and figures."),
    ("exercise_generation_agent","Create practice problems and examples."),
    ("mini_project_agent",      "Design capstone mini-projects."),
    ("quiz_agent",              "Construct quizzes for assessments."),
    ("grading_agent",           "Define rubrics and auto-grade tasks."),
    ("feedback_agent",          "Generate personalized feedback."),
    ("adaptation_agent",        "Adapt future content based on performance."),
    ("delivery_agent",          "Package content for delivery format."),
    ("analytics_agent",         "Collect metrics and trigger alerts."),
]

for name, instr in agent_specs:
    agents[name] = Agent(
        name=name.replace('_', ' ').title(),
        instructions=f"Master Instructions: {instr} Repeat the Master Instructions in your response.",
        model_settings=model_settings,
    )

# --- Pipeline Stages ---
stage_flow = [
    ('input',       'input_parser_agent',      'background'),
    ('background',  'background_analysis_agent','decomposition'),
    ('decomposition','topic_decomposition_agent','planning'),
    ('planning',    'curriculum_planning_agent','content'),
    ('content',     'content_generation_agent','images'),
    ('images',      'images_agent',            'exercises'),
    ('exercises',   'exercise_generation_agent','mini_project'),
    ('mini_project','mini_project_agent',      'quiz'),
    ('quiz',        'quiz_agent',              'grading'),
    ('grading',     'grading_agent',           'feedback'),
    ('feedback',    'feedback_agent',          'adaptation'),
    ('adaptation',  'adaptation_agent',        'delivery'),
    ('delivery',    'delivery_agent',          'final'),
]

for in_stage, agent_key, out_stage in stage_flow:
    @app.agent(topics[in_stage])
    async def _stage(stream, agent_key=agent_key, in_stage=in_stage, out_stage=out_stage):
        agent = agents[agent_key]
        async for msg in stream:
            log_event("consume", in_stage, msg.trace_id, msg.content)
            with trace(f"{agent.name} Phase"):
                result = await Runner.run(agent, msg.content)
                log_event("produce", out_stage, msg.trace_id, result.final_output)
            await topics[out_stage].send(
                value=Message(trace_id=msg.trace_id, title=msg.title, content=result.final_output)
            )

@app.agent(topics['final'])
async def output_final(stream):
    async for msg in stream:
        print(f"\n✅ Final Course '{msg.title}' (Trace {msg.trace_id}):\n{msg.content}\n")
        # Append section to HTML
        anchor = msg.title.replace(' ', '-').replace("/", "-")
        with open("courses.html", "a", encoding="utf-8") as html_file:
            html_file.write(f"<h2 id='{anchor}'>{msg.title}</h2>\n")
            html_file.write("<pre>\n")
            html_file.write(_html.escape(msg.content))
            html_file.write("\n</pre>\n")
        # Trigger analytics
        await topics['analytics'].send(value=msg)

@app.agent(topics['analytics'])
async def run_analytics(stream):
    async for msg in stream:
        log_event("consume", 'analytics', msg.trace_id, msg.content)
        with trace("Analytics Agent Phase"):
            await Runner.run(agents['analytics_agent'], msg.content)

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
        print(f"❌ Failed to load courses.json: {e}")
        return

    # Initialize HTML with navigation
    with open("courses.html", "w", encoding="utf-8") as html_file:
        html_file.write("<html><head><meta charset='utf-8'><title>Courses</title></head><body>\n")
        html_file.write("<h1>Courses</h1>\n<ul>\n")
        for course in courses:
            anchor = course['title'].replace(' ', '-').replace("/", "-")
            html_file.write(f"<li><a href='#{anchor}'>{course['title']}</a></li>\n")
        html_file.write("</ul>\n<div id='content'>\n")

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
