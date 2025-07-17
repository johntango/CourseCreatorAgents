# PubSub Architecture

# 📘 README: Creative Story Generation Pipeline with Faust and LLM Agents

## Overview

This project implements a distributed, event-driven storytelling pipeline using **Faust** and **LLM-based agents**. The pipeline automates the generation, critique, and revision of a creative story for children titled *"Tim the Flying Dog"*, employing a modular agent architecture. Each agent fulfills a distinct role in the story development lifecycle. The design utilizes Kafka-backed message topics to orchestrate communication between asynchronous processing stages.

---
# Pub-Sub Capability Added
## app = faust.App("agent_pipeline", broker="kafka://localhost:9092")
## run docker to spin up redpanda 
docker run -d --name=redpanda   -p 9092:9092 -p 9644:9644   redpandadata/redpanda:latest   redpanda start   --overprovisioned   --smp 1   --memory 1G   --reserve-memory 0M   --node-id 0   --check=false   --kafka-addr PLAINTEXT://0.0.0.0:9092   --advertise-kafka-addr PLAINTEXT://localhost:9092
## to launch program python agent.py worker -l info



## System Architecture

### Agent Flow

1. **Plot Agent**: Constructs a child-appropriate plot.
2. **Writer Agent**: Expands the plot into a complete narrative.
3. **Critic Agent**: Evaluates and suggests improvements to the story.
4. **Writer Agent (Revision Phase)**: Incorporates critic feedback.
5. **Final Output**: Presents the finalized story.

---

## Technologies Used

* **Python 3.8+**
* **Faust** – Stream processing
* **Apache Kafka** – Message broker
* **OpenAI GPT-based Agents** – Creative content generation
* **JSON Logging** – Structured event traceability
* **Asyncio** – Concurrent processing

---

## Prerequisites

Ensure the following environment is configured:

* Python ≥ 3.8
* Kafka broker running at `localhost:9092`
* OpenAI API key exported as an environment variable:

  ```bash
  export OPENAI_API_KEY='your-key-here'
  ```

---

## Key Components

### 1. **Model Settings**

```python
ModelSettings(temperature=0.7, max_tokens=5000)
```

These parameters configure the deterministic behavior and response length of the language model.

---

### 2. **Agents**

All agents use shared `ModelSettings` and serve specific roles:

* `plot_agent`: Outputs the foundational story structure.
* `writer_agent`: Converts plot into prose.
* `critic_agent`: Provides constructive feedback to enhance literary quality.

Each agent repeats its master instructions in every response, maintaining instruction traceability.

---

### 3. **Kafka Topics**

The inter-agent communication is handled via the following topics:

| Topic      | Purpose                      |
| ---------- | ---------------------------- |
| `plot`     | Transmits the generated plot |
| `story`    | Contains narrative drafts    |
| `critique` | Holds critic feedback        |
| `final`    | Final, polished story output |

---

### 4. **Logging**

Structured logs are saved in `broker_interactions.json` using `python-json-logger` for later inspection. Each log event includes:

* Timestamp
* Event type (`consume` or `produce`)
* Topic name
* Trace ID (UUID)
* Message payload
* Unique event ID

---

### 5. **Pipeline Lifecycle**

#### a. **Initialization Task**

Triggered at startup:

```python
@app.task
async def initiate_pipeline_once()
```

This sends an initial message to the `plot` topic.

#### b. **Processing Agents**

Each topic has a corresponding agent handler function:

* `writer_agent_stream`
* `critic_agent_stream`
* `writer_revise_stream`
* `editor_output_stream`

These use the `Runner.run()` utility to invoke LLM agents and generate responses.

---

## Example Execution

```bash
python script_name.py
```

Console Output:

```
✅ Final Story Output for Trace ID <uuid>:
<final story content>
```

---

## Advanced Features

### Timed Pipeline (Commented Out)

A timer-based approach (`@app.timer`) can trigger story creation at regular intervals.

---

## File Structure

```
.
├── main.py                      # Core pipeline logic
├── agents/
│   ├── __init__.py
│   ├── Agent.py
│   ├── Runner.py
│   └── model_settings.py
├── broker_interactions.json    # Structured JSON logs
└── README.md                   # Project documentation
```

---

## Extensibility

* Replace prompt templates in `Agent` definitions for alternative narratives.
* Enhance `Critic Agent` to support rubric-based evaluation.
* Parallelize multiple stories with unique `trace_id` namespaces.

---

## License

Distributed under a permissive license. Attribution required for reproduction.

---

## Author

*John Williams*
*Professor of Physics and IT*

---

