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

# Set your OpenAI key
set_default_openai_key(os.environ["OPENAI_API_KEY"])

# Define model settings
model_settings = ModelSettings(
    temperature=0.7,
    max_tokens=5000,
)
MAX_ROUNDS = 1  # Maximum number of rounds for the agent interactions

# Faust setup
app = faust.App("agent_pipeline", broker="kafka://localhost:9092")
print("Starting Faust app...")  # Debugging line to verify app start

# Define Agents
plot_agent = Agent(
    name="Curriculum Planner Agent",
    instructions="These are the Master Instructions: {Develop a structured, modular outline for the course titled '{title}', tailored for {level} learners. The outline should include clear learning objectives, module titles, and a brief description for each. Repeat these Master Instructions in your response.}",
    model_settings=model_settings,
)

writer_agent = Agent(
    name="Content Developer Agent",
    instructions="Using the course outline provided and following the Master Instructions, expand each module into detailed lesson content suitable for {level} learners. Include key concepts, examples, and exercises. Repeat the Master Instructions in your response.",
    model_settings=model_settings,
)

critic_agent = Agent(
    name="Curriculum Reviewer Agent",
    instructions="Review the developed course content for pedagogical clarity, depth, pacing, and alignment with the target expertise level ({level}). Suggest improvements, but do not rewrite the entire content. Repeat the Master Instructions in your response.",
    model_settings=model_settings,
)




@dataclass
class Message(faust.Record):
    trace_id: str
    content: str
    round: int = 0


plot_topic = app.topic("plot", value_type=Message)
story_topic = app.topic("story", value_type=Message)
critique_topic = app.topic("critique", value_type=Message)
final_topic = app.topic("final", value_type=Message)

# Set up JSON log file
log_file = "broker_interactions.json"
log_handler = logging.FileHandler(log_file)
log_formatter = jsonlogger.JsonFormatter()
log_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG)

# Silence noisy logs
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("aiokafka").setLevel(logging.DEBUG)
logging.getLogger("faust").setLevel(logging.DEBUG)


def log_event(event_type, topic, trace_id, payload):
    logger.info({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event_type,
        "topic": topic,
        "trace_id": trace_id,
        "payload": payload,
        "event_id": str(uuid4())
    })


@app.agent(plot_topic)
async def writer_agent_stream(stream):
    async for msg in stream:
        if msg.round >= MAX_ROUNDS:
            await final_topic.send(value=msg)
            continue
        log_event("consume", "plot", msg.trace_id, msg.content)
        with trace("Writer Phase"):
            result = await Runner.run(writer_agent, msg.content)
            log_event("produce", "story", msg.trace_id, result.final_output)
        await story_topic.send(value=Message(trace_id=msg.trace_id, content=result.final_output))


@app.agent(story_topic)
async def critic_agent_stream(stream):
    async for msg in stream:
        log_event("consume", "story", msg.trace_id, msg.content)
        with trace("Critic Phase"):
            result = await Runner.run(critic_agent, msg.content)
            log_event("produce", "critique", msg.trace_id, result.final_output)
        await critique_topic.send(value=Message(trace_id=msg.trace_id, content=result.final_output))


@app.agent(critique_topic)
async def writer_revise_stream(stream):
    async for msg in stream:
        log_event("consume", "critique", msg.trace_id, msg.content)
        with trace("Writer Revision Phase"):
            result = await Runner.run(writer_agent, msg.content)
            log_event("produce", "final", msg.trace_id, result.final_output)
        await final_topic.send(value=Message(trace_id=msg.trace_id, content=result.final_output))


@app.agent(final_topic)
async def editor_output_stream(stream):
    async for msg in stream:
        print(
            f"\n✅ Final Course Output for Trace ID {msg.trace_id}:\n{msg.content} \n")

# Define the course list to process
course_list = [
    {"name": "LLM Prompting", "level": "beginner"},
    {"name": "AI Ethics", "level": "intermediate"},
    {"name": "AI in Education", "level": "advanced"}
]

# Initiate pipeline for each course
# This runs the plot agent once at startup


# @app.task
@app.timer(interval=1.0, on_leader=True)
async def initiate_pipeline_once():
    print("🕒 Timer fired: initiate_pipeline_once")             # <— verify timer
    trace_id = str(uuid4())
    try:
        # <— verify you got here
        print(f"🔍 Running plot_agent for trace {trace_id}")
        result = await Runner.run(plot_agent, "Say Hello World")
        print("✅ plot_agent returned successfully")
    except Exception as e:
        print("❌ Exception in plot_agent:", e, flush=True)
        raise

    print("✉️ Sending to plot_topic")
    await plot_topic.send(value=Message(trace_id=trace_id,
                                        content=result.final_output,
                                        round=1))


if __name__ == "__main__":
    app.main()
