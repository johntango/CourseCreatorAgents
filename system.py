import os
import asyncio
import faust
import logging
import json
import datetime
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
    content: str

# Define one topic per agent stage
input_topic            = app.topic("input",            value_type=Message)
background_topic       = app.topic("background",       value_type=Message)
decomposition_topic    = app.topic("decomposition",    value_type=Message)
planning_topic         = app.topic("planning",         value_type=Message)
content_topic          = app.topic("content",          value_type=Message)
images_topic           = app.topic("images",           value_type=Message)
exercises_topic        = app.topic("exercises",        value_type=Message)
mini_project_topic     = app.topic("mini_project",     value_type=Message)
quiz_topic             = app.topic("quiz",             value_type=Message)
grading_topic          = app.topic("grading",          value_type=Message)
feedback_topic         = app.topic("feedback",         value_type=Message)
adaptation_topic       = app.topic("adaptation",       value_type=Message)
delivery_topic         = app.topic("delivery",         value_type=Message)
final_topic            = app.topic("final",            value_type=Message)
analytics_topic        = app.topic("analytics",        value_type=Message)

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
input_parser_agent = Agent(
    name="Input Parser Agent",
    instructions=(
        "Master Instructions: Ingest the raw JSON input {'title':…, 'background':…}, "
        "validate schema, normalize fields, and output a canonical JSON with 'title' "
        "and parsed 'background'. Repeat the Master Instructions in your response."
    ),
    model_settings=model_settings,
)

background_analysis_agent = Agent(
    name="Background Analysis Agent",
    instructions=(
        "Master Instructions: Analyze the student's 'background' field to determine "
        "difficulty level, identify prerequisite knowledge gaps, and choose appropriate "
        "terminology. Repeat the Master Instructions in your response."
    ),
    model_settings=model_settings,
)

topic_decomposition_agent = Agent(
    name="Topic Decomposition Agent",
    instructions=(
        "Master Instructions: Decompose the high-level 'title' into sub-topics, learning "
        "objectives, and prerequisite concepts. Repeat the Master Instructions in your response."
    ),
    model_settings=model_settings,
)

curriculum_planning_agent = Agent(
    name="Curriculum Planning Agent",
    instructions=(
        "Master Instructions: Sequence sub-topics into a coherent lesson plan, deciding "
        "granularity, pacing, and dependencies. Repeat the Master Instructions in your response."
    ),
    model_settings=model_settings,
)

content_generation_agent = Agent(
    name="Content Generation Agent",
    instructions=(
        "Master Instructions: Generate instructional text for each lesson segment, "
        "adapting register to student background, including examples. Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

images_agent = Agent(
    name="Images Agent",
    instructions=(
        "Master Instructions: Produce or source diagrams, charts, and figures to "
        "illustrate each lesson segment. Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

exercise_generation_agent = Agent(
    name="Exercise Generation Agent",
    instructions=(
        "Master Instructions: Create practice problems, worked examples, and coding "
        "exercises aligned to each lesson objective. Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

mini_project_agent = Agent(
    name="Mini-Project Agent",
    instructions=(
        "Master Instructions: Design capstone mini-projects integrating multiple lesson elements. "
        "Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

quiz_agent = Agent(
    name="Quiz Agent",
    instructions=(
        "Master Instructions: Construct formative and summative quizzes—MCQs, short-answer, coding tasks. "
        "Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

grading_agent = Agent(
    name="Grading Agent",
    instructions=(
        "Master Instructions: Define rubrics, auto-grade objective items, and flag open-ended responses. "
        "Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

feedback_agent = Agent(
    name="Feedback Agent",
    instructions=(
        "Master Instructions: Generate personalized feedback: error explanations, remediation links, hints. "
        "Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

adaptation_agent = Agent(
    name="Adaptation Agent",
    instructions=(
        "Master Instructions: Monitor student performance data, update the learner model, "
        "and adjust future content difficulty or pacing. Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

delivery_agent = Agent(
    name="Delivery Agent",
    instructions=(
        "Master Instructions: Package all text, images, exercises, and quizzes into the "
        "target format (web page, PDF, LMS). Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

analytics_agent = Agent(
    name="Analytics Agent",
    instructions=(
        "Master Instructions: Collect usage and performance metrics, prepare instructor dashboards, "
        "and trigger alerts for learner progress. Repeat the Master Instructions."
    ),
    model_settings=model_settings,
)

# --- Pipeline Stages ---
@app.agent(input_topic)
async def parse_input(stream):
    async for msg in stream:
        log_event("consume", "input", msg.trace_id, msg.content)
        with trace("Input Parsing Phase"):
            result = await Runner.run(input_parser_agent, msg.content)
            log_event("produce", "background", msg.trace_id, result.final_output)
        await background_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(background_topic)
async def analyze_background(stream):
    async for msg in stream:
        log_event("consume", "background", msg.trace_id, msg.content)
        with trace("Background Analysis Phase"):
            result = await Runner.run(background_analysis_agent, msg.content)
            log_event("produce", "decomposition", msg.trace_id, result.final_output)
        await decomposition_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(decomposition_topic)
async def decompose_topic(stream):
    async for msg in stream:
        log_event("consume", "decomposition", msg.trace_id, msg.content)
        with trace("Decomposition Phase"):
            result = await Runner.run(topic_decomposition_agent, msg.content)
            log_event("produce", "planning", msg.trace_id, result.final_output)
        await planning_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(planning_topic)
async def plan_curriculum(stream):
    async for msg in stream:
        log_event("consume", "planning", msg.trace_id, msg.content)
        with trace("Planning Phase"):
            result = await Runner.run(curriculum_planning_agent, msg.content)
            log_event("produce", "content", msg.trace_id, result.final_output)
        await content_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(content_topic)
async def generate_content(stream):
    async for msg in stream:
        log_event("consume", "content", msg.trace_id, msg.content)
        with trace("Content Generation Phase"):
            result = await Runner.run(content_generation_agent, msg.content)
            log_event("produce", "images", msg.trace_id, result.final_output)
        await images_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(images_topic)
async def generate_images(stream):
    async for msg in stream:
        log_event("consume", "images", msg.trace_id, msg.content)
        with trace("Images Generation Phase"):
            result = await Runner.run(images_agent, msg.content)
            log_event("produce", "exercises", msg.trace_id, result.final_output)
        await exercises_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(exercises_topic)
async def generate_exercises(stream):
    async for msg in stream:
        log_event("consume", "exercises", msg.trace_id, msg.content)
        with trace("Exercises Generation Phase"):
            result = await Runner.run(exercise_generation_agent, msg.content)
            log_event("produce", "mini_project", msg.trace_id, result.final_output)
        await mini_project_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(mini_project_topic)
async def generate_mini_project(stream):
    async for msg in stream:
        log_event("consume", "mini_project", msg.trace_id, msg.content)
        with trace("Mini-Project Phase"):
            result = await Runner.run(mini_project_agent, msg.content)
            log_event("produce", "quiz", msg.trace_id, result.final_output)
        await quiz_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(quiz_topic)
async def generate_quiz(stream):
    async for msg in stream:
        log_event("consume", "quiz", msg.trace_id, msg.content)
        with trace("Quiz Generation Phase"):
            result = await Runner.run(quiz_agent, msg.content)
            log_event("produce", "grading", msg.trace_id, result.final_output)
        await grading_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(grading_topic)
async def grade_content(stream):
    async for msg in stream:
        log_event("consume", "grading", msg.trace_id, msg.content)
        with trace("Grading Phase"):
            result = await Runner.run(grading_agent, msg.content)
            log_event("produce", "feedback", msg.trace_id, result.final_output)
        await feedback_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(feedback_topic)
async def provide_feedback(stream):
    async for msg in stream:
        log_event("consume", "feedback", msg.trace_id, msg.content)
        with trace("Feedback Phase"):
            result = await Runner.run(feedback_agent, msg.content)
            log_event("produce", "adaptation", msg.trace_id, result.final_output)
        await adaptation_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(adaptation_topic)
async def adapt_learning(stream):
    async for msg in stream:
        log_event("consume", "adaptation", msg.trace_id, msg.content)
        with trace("Adaptation Phase"):
            result = await Runner.run(adaptation_agent, msg.content)
            log_event("produce", "delivery", msg.trace_id, result.final_output)
        await delivery_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(delivery_topic)
async def deliver_content(stream):
    async for msg in stream:
        log_event("consume", "delivery", msg.trace_id, msg.content)
        with trace("Delivery Phase"):
            result = await Runner.run(delivery_agent, msg.content)
            log_event("produce", "final", msg.trace_id, result.final_output)
        await final_topic.send(
            value=Message(trace_id=msg.trace_id, content=result.final_output)
        )

@app.agent(final_topic)
async def output_final(stream):
    async for msg in stream:
        print(f"\n✅ Final Packaged Course (Trace {msg.trace_id}):\n{msg.content}\n")
        # Trigger analytics after final delivery
        await analytics_topic.send(value=Message(trace_id=msg.trace_id, content=msg.content))

@app.agent(analytics_topic)
async def run_analytics(stream):
    async for msg in stream:
        log_event("consume", "analytics", msg.trace_id, msg.content)
        with trace("Analytics Phase"):
            await Runner.run(analytics_agent, msg.content)
        # No further topic


# --- Bootstrap: Read JSON and kick off pipeline once ---
_has_run = False

@app.timer(interval=1.0, on_leader=True)
async def initiate_pipeline_once():
    global _has_run
    if _has_run:
        return
    _has_run = True

    # Expect a JSON file courses.json with array of {"title":…, "background":…}
    try:
        with open("courses.json", "r") as f:
            courses = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load courses.json: {e}")
        return

    for course in courses:
        trace_id = str(uuid4())
        payload = json.dumps({
            "title":      course["title"],
            "background": course["background"]
        })
        log_event("initiate", "input", trace_id, payload)
        await input_topic.send(
            value=Message(trace_id=trace_id, content=payload)
        )

if __name__ == "__main__":
    app.main()
