# Wanderlust Travel Concierge & Studio

> A personalized, multimodal AI travel planner and concierge built with Google's Agent Development Kit (ADK), deployed on Vertex AI Agent Runtime, and powered by Gemini 2.5 Flash, Gemini Image Generation, and Gemini Omni Flash (`gemini-omni-flash-preview`).

---

## ✨ Features & Capabilities

- **Curated Destination & Itinerary Management**: Grounded in Google Cloud Firestore with real-time search, attraction details, and day-by-day itinerary saving (`search_destinations`, `get_destination_details`, `save_itinerary_stop`, `get_trip_itinerary`).
- **Cinematic Omni Video Generation**: Generates 5-second cinematic motion video previews for any destination or landmark using Google's Omni model (`gemini-omni-flash-preview`) in Vertex AI `global` region, saving directly to Cloud Storage and ADK Playground artifacts (`generate_destination_video`).
- **Scenic Postcard Generation**: Generates photorealistic scenic postcards and visual travel previews using Gemini Image Gen, published directly to a public Cloud Storage bucket (`generate_destination_image`).
- **Live Weather & Packing Advice**: Real-time temperature, conditions, and 3-day weather forecasts via the Open-Meteo API (`get_destination_weather`).
- **Currency & Budget Math**: Live exchange rates from the European Central Bank (ECB) via the Frankfurter API (`convert_currency`) and arithmetic/unit conversions (`convert_units`, `calculate_math`).
- **Code Execution Sandbox**: Secure Python execution for complex expense splitting and trip budget calculations.
- **Cross-Session Long-Term Memory**: Remembers traveler preferences, pace, dietary restrictions, and favorite destinations across sessions via Vertex AI Memory Bank (`PreloadMemoryTool` & memory generation callback).
- **Travel Studio Web UI**: A responsive web portal featuring a left-hand action studio with 1-click destination chips and dedicated media generation controls, paired with an embedded HTML5 video player and postcard gallery.

---

## 🏗️ Architecture

```
                                    ┌────────────────────────────────────────────────────────┐
                                    │               Wanderlust Travel Studio                 │
                                    │        (FastAPI Proxy + Responsive Portal UI)          │
                                    └───────────────────────────┬────────────────────────────┘
                                                                │ A2A Protocol
                                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 ADK Agent (Agent Runtime)                                  │
│                                                                                            │
│   ┌────────────────────┐   ┌────────────────────────┐   ┌──────────────────────────────┐   │
│   │     Firestore      │   │   Open-Meteo Weather   │   │  Gemini Omni Flash (Global)  │   │
│   │ (Catalog & Trips)  │   │     & ECB Currency     │   │      (5s Video Previews)     │   │
│   └────────────────────┘   └────────────────────────┘   └──────────────────────────────┘   │
│                                                                                            │
│   ┌────────────────────┐   ┌────────────────────────┐   ┌──────────────────────────────┐   │
│   │ Vertex Memory Bank │   │    Gemini Image Gen    │   │     Python Code Sandbox      │   │
│   │(Long-Term Context) │   │   (Scenic Postcards)   │   │   (Budget & Math Solvers)    │   │
│   └────────────────────┘   └────────────────────────┘   └──────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install)
- `agents-cli`: Install with `uv tool install google-agents-cli`

### 1. Installation

Clone this repository and install dependencies:

```bash
git clone <your-repo-url>
cd <repo-folder>
agents-cli install
```

### 2. Local Development

Run the ADK agent locally:

```bash
uv run adk web . --port 8080 --reload_agents
```

### 3. Run the Frontend Studio

In a separate terminal, navigate to the `frontend/` directory and run:

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Then visit `http://localhost:8080` to explore the travel concierge portal.

---

## 🛠️ Project Structure

```
.
├── app/
│   ├── agent.py               # Main ADK root_agent definition, prompts, callbacks & tools
│   ├── tools.py               # Custom tools (Firestore, Weather, FX, Postcards, Omni Video)
│   ├── app_utils/             # Memory Bank callbacks and helper utilities
│   └── fast_api_app.py        # FastAPI A2A backend
├── frontend/
│   ├── main.py                # FastAPI proxy server connecting to Agent Engine over A2A
│   ├── static/index.html      # Travel Studio web UI with embedded video player & media gallery
│   └── requirements.txt       # Frontend proxy dependencies
├── agents-cli-manifest.yaml   # Agent deployment manifest
├── Dockerfile                 # Container specification for Agent Runtime
├── project_brief.md           # Project specification & tool coverage brief
├── pyproject.toml             # Python dependencies and packaging configuration
└── tests/                     # Unit and integration test suites
```

---

## 📜 License

Apache-2.0
