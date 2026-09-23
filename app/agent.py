# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


MODEL = "gemini-2.5-flash"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


import json
from pathlib import Path
from google.adk.agents.callback_context import CallbackContext
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from app.tools import (
    add_destination,
    calculate_math,
    convert_currency,
    convert_units,
    generate_destination_image,
    generate_destination_video,
    get_destination_details,
    get_destination_weather,
    get_trip_itinerary,
    save_itinerary_stop,
    search_destinations,
)

# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None

def _init_code_executor() -> AgentEngineSandboxCodeExecutor:
    metadata_file = Path(__file__).resolve().parent.parent / "deployment_metadata.json"
    sandbox_name = "projects/100827421660/locations/us-east1/reasoningEngines/428468686228029440/sandboxEnvironments/4244449134750203904"
    engine_name = "projects/100827421660/locations/us-east1/reasoningEngines/428468686228029440"
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                sandbox_name = data.get("sandbox_resource_name", sandbox_name)
                engine_name = data.get("remote_agent_runtime_id", engine_name)
        except Exception:
            pass
    return AgentEngineSandboxCodeExecutor(
        sandbox_resource_name=sandbox_name,
        agent_engine_resource_name=engine_name,
    )

code_executor = _init_code_executor()

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    after_agent_callback=generate_memories_callback,
    instruction=(
        "You are Wanderlust Travel Concierge, a personalized travel planning agent. "
        "You remember the traveler's stated preferences, dietary restrictions, favorite destinations, "
        "and facts from previous conversations to personalize all recommendations and itineraries. "
        "Use `search_destinations` and `get_destination_details` to query the Firestore catalog of curated places. "
        "Use `add_destination` when the user wants to contribute a new place or recommendation to the catalog. "
        "Use `save_itinerary_stop` and `get_trip_itinerary` to build and retrieve customized trip plans in Firestore. "
        "Whenever the user asks to plan, create, or recommend an itinerary for a destination, or asks about sights in a city, "
        "ALWAYS also generate a scenic postcard image for the primary highlight/landmark using `generate_destination_image` so the itinerary is accompanied by vibrant visual media. "
        "Use `generate_destination_video` whenever the traveler asks for a video, motion clip, cinematic preview, or footage of a destination or landmark. "
        "Use `get_destination_weather` to check live weather conditions and 3-day forecasts for trip planning and packing advice. "
        "Use `convert_currency` to convert travel funds, prices, and shopping budgets between international currencies using live exchange rates. "
        "Use `convert_units` and `calculate_math` for standard conversions and arithmetic. "
        "When advanced calculations, expense splitting, data simulation, or custom scripts are needed, execute Python code in the sandbox. "
        "When returning generated media (images or videos), always include their public HTTPS URLs in your response so the client can display them."
    ),
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        add_destination,
        save_itinerary_stop,
        get_trip_itinerary,
        get_destination_weather,
        generate_destination_image,
        generate_destination_video,
        convert_currency,
        convert_units,
        calculate_math,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
