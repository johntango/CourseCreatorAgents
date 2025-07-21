import os
import asyncio
from agents import Agent, Runner, set_default_openai_key, gen_trace_id, trace
from agents.mcp import MCPServerSse, MCPServerSseParams
from agents.model_settings import ModelSettings

# Set your OpenAI key
set_default_openai_key(os.environ["OPENAI_API_KEY"])

# Define common model settings
model_settings = ModelSettings(
    temperature=0.7,
    max_tokens=5000,
)

topics_agent = Agent(
    name="Topics Agent",
    instructions="Develop the modules and topics for the course, taking into account the background of the student and the course objectives. Output the list of topics and a description for each topic.",
    model_settings=model_settings,
)

writer_agent = Agent(
    name="Writer Agent",
    instructions="Using the topics provided, develop content for that topic given the background of the student.",
    model_settings=model_settings,
)

editor_agent = Agent(
    name="Editor Agent",
    instructions=(
        "You are the Editor coordinating course development'. "
        "Begin by asking the Plot Agent Tool to create a plot. Then pass the plot to the Writer Agent Tool to write the story. "
        "Next, give the story to the Critic Agent Tool for feedback. "
        "Then ask the Writer Agent to revise the story based on the Critic's feedback. "
        "Finally, send results back and print out the final book. "
        "Respond at each stage using structured outputs like {stage: ..., content: ...}."
    ),
    model_settings=model_settings,
    tools=[
        topics_agent.as_tool(
            tool_name="PlotAgent",
            tool_description="Develop an outline plot that the writer can use to write the story.",
        ),
        writer_agent.as_tool(
            tool_name="WriterAgent",
            tool_description="Write the story based on the plot provided by the Plot Agent.",
        ),
    ],
    handoffs=[topics_agent, writer_agent]
)
def trace_hook(trace):
    for step in trace.steps:
        print(f"\n🔧 Agent: {step.agent.name}")
        print(f"➡️ Input: {step.input.content}")
        print(f"✅ Output: {step.output.content}")
# --- Runner Execution ---

async def run_course_creation():
    input_prompt = "Please coordinate the coursecreation process for 'LLM Prompting for Beginners'. The course should be designed for absolute beginners with no prior knowledge of LLMs. The course should cover the following topics: Introduction to LLMs, Basic Prompting Techniques, Advanced Prompting Techniques, and Practical Applications of LLMs. Each topic should have a detailed description and learning objectives."
    print(f">> Running Editor Agent with input: {input_prompt}")

    try:
        # run trace
        with trace("Book creation workflow"):
            editor_result = await Runner.run(editor_agent, input_prompt)
            # print trace
            print(f"\n\nFinal response:\n{editor_result.final_output}")
            print("\n✅ Final Book Output:\n")
            print(editor_result.final_output)
    except TimeoutError:
        print("❌ Timed out during the agent orchestration")

# Entry point
if __name__ == "__main__":
    asyncio.run(run_course_creation())