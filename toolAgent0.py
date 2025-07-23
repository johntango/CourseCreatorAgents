import os
import asyncio
from agents import Agent, Runner, set_default_openai_key, gen_trace_id, trace
from agents.model_settings import ModelSettings
# this uses agents as tools there is no handoff just tool calling
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
    instructions="Using the topics provided, develop content for that topic given the background level of the student. Write at least one paragraph for each topic, ensuring the content is engaging and informative. Send the content back to the Editor Agent.",
    model_settings=model_settings,
)

broadcast_agent = Agent(
    name="Broadcast Agent",
    instructions="You are the Broadcaster Agent. Your task is to take the final course content and for each topic prepare a 5 minute broadcast.",
    model_settings=model_settings,
)

editor_agent = Agent(
    name="Editor Agent",
    instructions=(
        "You are the Editor coordinating course development'. "
        "Begin by asking the Topics Agent Tool to create a list of modules and topics. Then pass the topics to the Writer Agent Tool to develop each topic of the course. " 
        "Develop a broadcast script for each topic and then output and print the final course. "
        "Respond at each stage using structured outputs like {stage: ..., content: ...}."
    ),
    model_settings=model_settings,
    tools=[
        topics_agent.as_tool(
            tool_name="PlotAgent",
            tool_description="Develop modules and topics that the writer can use to write the story.",
        ),
        writer_agent.as_tool(
            tool_name="WriterAgent",
            tool_description="Write a paragraph for each topic provided by the Plot Agent.",
        ),
        broadcast_agent.as_tool(
            tool_name="BroadcastAgent",
            tool_description="Write a 3 minute broadcast for each topic.",
        ),
    ],
    #handoffs=[topics_agent, writer_agent]
)
def trace_hook(trace):
    for step in trace.steps:
        print(f"\n🔧 Agent: {step.agent.name}")
        print(f"➡️ Input: {step.input.content}")
        print(f"✅ Output: {step.output.content}")
# --- Runner Execution ---

async def run_course_creation():
    input_prompt = "Please coordinate the course creation process for 'LLM Prompting for Ministers in the Media Sector'. The course should be designed for media professionals with very basic understanding of AI and LLMs. The course should cover practical applications, ethical considerations, and hands-on exercises appropriate for this audience. Start by using your Topics Agent to create a list of modules and topics, then use the Writer Agent to develop content for each topic. Finally, output the complete course content."
    print(f">> Running Editor Agent with input: {input_prompt}")

    try:
        # run trace
        with trace("Course creation workflow"):
            editor_result = await Runner.run(editor_agent, input_prompt)
            # print trace
            print(f"\n\nFinal response:\n{editor_result.final_output}")
            print("\n✅ Final Course Output:\n")
            print(editor_result.final_output)
    except TimeoutError:
        print("❌ Timed out during the agent orchestration")

# Entry point
if __name__ == "__main__":
    asyncio.run(run_course_creation())