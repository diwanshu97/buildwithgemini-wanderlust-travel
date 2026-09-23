import ast
import base64
import datetime
import logging
import math
import operator
import os
import re
from typing import Any
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google import genai
from google.genai import types as genai_types
import httpx

logger = logging.getLogger(__name__)

# IMPORTANT: Hardcode project ID and bucket name as strings, not from auth default or env var
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-04-69c9c83b08f1"
GCS_BUCKET_NAME = "wanderlust-travel-media-69c9c83b"

_firestore_client: firestore.Client | None = None
_storage_client: storage.Client | None = None
_genai_client: genai.Client | None = None


def _get_db() -> firestore.Client:
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=FIRESTORE_PROJECT_ID)
    return _firestore_client


def _get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    return _storage_client


def _get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT_ID,
            location="global"
        )
    return _genai_client


# ==========================================
# Firestore Travel Tools (Read & Write)
# ==========================================

def search_destinations(
    city: str | None = None,
    category: str | None = None,
    max_results: int = 5
) -> dict[str, Any]:
    """Search and browse travel destinations, sights, landmarks, and dining spots.

    Args:
        city: Optional city name to filter by (e.g. 'Paris', 'Tokyo', 'Rome', 'Kyoto').
        category: Optional category filter (e.g. 'landmark', 'cultural', 'museum', 'nature', 'food & dining').
        max_results: Maximum number of results to return (default: 5).

    Returns:
        dict: List of matching destination records and count.
    """
    try:
        db = _get_db()
        docs = db.collection("destinations").stream()
        results = []

        city_query = city.strip().lower() if city else None
        cat_query = category.strip().lower() if category else None

        for doc in docs:
            data = doc.to_dict()
            doc_city = str(data.get("city", "")).lower()
            doc_category = str(data.get("category", "")).lower()

            if city_query and city_query not in doc_city:
                continue
            if cat_query and cat_query not in doc_category:
                continue

            results.append(data)
            if len(results) >= max_results:
                break

        return {
            "status": "success",
            "count": len(results),
            "destinations": results
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to search destinations from Firestore: {e}"
        }


def get_destination_details(destination_id: str) -> dict[str, Any]:
    """Retrieve complete details for a specific destination by its ID.

    Args:
        destination_id: The unique ID of the destination (e.g. 'eiffel-tower', 'colosseum', 'senso-ji').

    Returns:
        dict: Detailed destination record or error if not found.
    """
    try:
        db = _get_db()
        doc_ref = db.collection("destinations").document(destination_id.strip().lower())
        doc = doc_ref.get()
        if doc.exists:
            return {
                "status": "success",
                "destination": doc.to_dict()
            }
        return {
            "status": "error",
            "message": f"Destination with ID '{destination_id}' not found."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to retrieve destination from Firestore: {e}"
        }


def add_destination(
    name: str,
    city: str,
    country: str,
    category: str,
    description: str,
    rating: float = 4.5,
    price_tier: str = "$$",
    tags: list[str] | None = None,
    recommended_duration_hours: float = 2.0
) -> dict[str, Any]:
    """Add a new travel destination, sight, or restaurant to the Firestore catalog.

    Args:
        name: Name of the destination or attraction (e.g. 'Montmartre Artists Square').
        city: City where it is located (e.g. 'Paris').
        country: Country where it is located (e.g. 'France').
        category: Category (e.g. 'landmark', 'cultural', 'museum', 'food & dining', 'nature').
        description: Brief description of the place and experience.
        rating: Average rating from 1.0 to 5.0 (default 4.5).
        price_tier: Cost level ('free', '$', '$$', '$$$').
        tags: List of keywords/tags (e.g. ['scenic', 'art', 'bohemian']).
        recommended_duration_hours: Recommended visit time in hours (default 2.0).

    Returns:
        dict: Confirmation of the created destination.
    """
    try:
        db = _get_db()
        doc_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        data = {
            "id": doc_id,
            "name": name,
            "city": city,
            "country": country,
            "category": category.lower(),
            "description": description,
            "rating": round(float(rating), 1),
            "price_tier": price_tier,
            "tags": tags or [],
            "recommended_duration_hours": float(recommended_duration_hours)
        }
        db.collection("destinations").document(doc_id).set(data)
        return {
            "status": "success",
            "message": f"Destination '{name}' successfully added to catalog.",
            "destination": data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to add destination to Firestore: {e}"
        }


def save_itinerary_stop(
    trip_name: str,
    day_number: int,
    place_name: str,
    city: str,
    notes: str = ""
) -> dict[str, Any]:
    """Save an attraction or activity stop to a traveler's planned trip itinerary in Firestore.

    Args:
        trip_name: Name of the trip (e.g. 'Paris Autumn Getaway', 'Tokyo Spring 2026').
        day_number: Which day of the trip (e.g. 1, 2, 3).
        place_name: Name of the sight or dining venue.
        city: City where this stop takes place.
        notes: Optional custom notes, planned time of day, or tips.

    Returns:
        dict: Confirmation of the saved itinerary stop.
    """
    try:
        db = _get_db()
        clean_trip_id = re.sub(r'[^a-z0-9]+', '-', trip_name.lower()).strip('-')
        stop_id = f"day{day_number}-{re.sub(r'[^a-z0-9]+', '-', place_name.lower()).strip('-')}"

        stop_data = {
            "trip_name": trip_name,
            "day_number": int(day_number),
            "place_name": place_name,
            "city": city,
            "notes": notes,
        }

        doc_ref = (
            db.collection("itineraries")
            .document(clean_trip_id)
            .collection("stops")
            .document(stop_id)
        )
        doc_ref.set(stop_data)

        # Also update parent trip metadata
        db.collection("itineraries").document(clean_trip_id).set(
            {"trip_name": trip_name, "city": city}, merge=True
        )

        return {
            "status": "success",
            "message": f"Saved '{place_name}' to Day {day_number} of '{trip_name}'.",
            "stop": stop_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to save itinerary stop to Firestore: {e}"
        }


def get_trip_itinerary(trip_name: str) -> dict[str, Any]:
    """Retrieve all planned stops and days for a given trip itinerary.

    Args:
        trip_name: Name of the trip (e.g. 'Paris Autumn Getaway').

    Returns:
        dict: List of planned stops organized by day.
    """
    try:
        db = _get_db()
        clean_trip_id = re.sub(r'[^a-z0-9]+', '-', trip_name.lower()).strip('-')
        stops_ref = (
            db.collection("itineraries")
            .document(clean_trip_id)
            .collection("stops")
            .order_by("day_number")
        )
        stops = [doc.to_dict() for doc in stops_ref.stream()]
        return {
            "status": "success",
            "trip_name": trip_name,
            "total_stops": len(stops),
            "stops": stops
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get trip itinerary from Firestore: {e}"
        }


# ==========================================
# Live Weather & Packing Tools
# ==========================================

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def get_destination_weather(city: str) -> dict[str, Any]:
    """Fetch live weather conditions and a 3-day forecast for any travel destination.

    Args:
        city: Name of the city (e.g. 'Paris', 'Tokyo', 'Rome', 'New York', 'Kyoto').

    Returns:
        dict: Real-time current temperature, feels like, conditions, humidity,
              wind speed, and a 3-day forecast with daily highs, lows, and rain probability.
    """
    clean_city = city.strip()
    try:
        # 1. Geocode city name to lat/lon
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        with httpx.Client(timeout=10.0) as client:
            geo_resp = client.get(
                geo_url,
                params={"name": clean_city, "count": 1, "language": "en", "format": "json"}
            )
            geo_data = geo_resp.json()

            results = geo_data.get("results")
            if not results:
                return {
                    "status": "error",
                    "message": f"Could not find coordinates for city '{clean_city}'."
                }

            loc = results[0]
            lat = loc["latitude"]
            lon = loc["longitude"]
            resolved_city = loc.get("name", clean_city)
            country = loc.get("country", "")

            # 2. Fetch live weather & 3-day forecast
            weather_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 3,
            }
            w_resp = client.get(weather_url, params=params)
            w_data = w_resp.json()

            current = w_data.get("current", {})
            daily = w_data.get("daily", {})

            curr_code = current.get("weather_code", 0)
            curr_condition = WMO_WEATHER_CODES.get(curr_code, "Partly cloudy")

            forecast_list = []
            dates = daily.get("time", [])
            codes = daily.get("weather_code", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            rain_probs = daily.get("precipitation_probability_max", [])

            for i in range(len(dates)):
                d_code = codes[i] if i < len(codes) else 0
                forecast_list.append({
                    "date": dates[i],
                    "condition": WMO_WEATHER_CODES.get(d_code, "Partly cloudy"),
                    "high_c": max_temps[i] if i < len(max_temps) else None,
                    "low_c": min_temps[i] if i < len(min_temps) else None,
                    "rain_probability_pct": rain_probs[i] if i < len(rain_probs) else 0,
                })

            return {
                "status": "success",
                "city": resolved_city,
                "country": country,
                "latitude": lat,
                "longitude": lon,
                "current": {
                    "temperature_c": current.get("temperature_2m"),
                    "feels_like_c": current.get("apparent_temperature"),
                    "condition": curr_condition,
                    "humidity_pct": current.get("relative_humidity_2m"),
                    "wind_speed_kmh": current.get("wind_speed_10m"),
                },
                "forecast_3_day": forecast_list,
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch weather for '{clean_city}': {e}"
        }


# ==========================================
# Postcard & Landmark Image Generation Tools
# ==========================================

async def generate_destination_image(
    destination_name: str,
    prompt: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Generate a scenic travel image or postcard visual for a destination using Gemini image generation.

    The generated image is saved as an artifact in the session context (visible in the Artifacts panel)
    and uploaded directly to the public Cloud Storage bucket in memory.

    Args:
        destination_name: Name of the destination, landmark, or city (e.g. 'Eiffel Tower', 'Senso-ji Temple', 'Colosseum').
        prompt: Optional specific artistic prompt or visual description. If omitted, a scenic postcard prompt is constructed.
        tool_context: ADK execution context injected by the framework.

    Returns:
        dict: Status, public Cloud Storage URL, and artifact filename.
    """
    clean_name = destination_name.strip()
    if prompt and prompt.strip():
        visual_prompt = f"{prompt.strip()}. High quality travel photograph of {clean_name}, scenic lighting, postcard perspective, high resolution."
    else:
        visual_prompt = (
            f"A breathtaking photorealistic travel photograph of {clean_name}, vibrant scenic lighting, "
            f"beautiful travel postcard perspective, 4k ultra high detail."
        )

    try:
        genai_client = _get_genai_client()
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=visual_prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        )

        image_bytes: bytes | None = None
        mime_type = "image/jpeg"

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not image_bytes:
            return {
                "status": "error",
                "message": f"Model did not return any image data for '{clean_name}'."
            }

        slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "destination"
        timestamp = int(datetime.datetime.now().timestamp())
        ext = "jpg" if "jpeg" in mime_type or "jpg" in mime_type else "png"
        artifact_filename = f"{slug}_{timestamp}.{ext}"
        object_name = f"postcards/{slug}_{timestamp}.{ext}"

        # 1. Save artifact with tool_context for playground
        if tool_context is not None:
            try:
                artifact_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                await tool_context.save_artifact(
                    filename=artifact_filename,
                    artifact=artifact_part,
                    custom_metadata={"destination": clean_name, "prompt": visual_prompt}
                )
            except Exception as e:
                logger.warning(f"Could not save artifact to tool_context: {e}")

        # 2. Upload image bytes to public Cloud Storage bucket in memory (no local file)
        storage_client = _get_storage_client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(object_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"

        return {
            "status": "success",
            "destination_name": clean_name,
            "image_url": public_url,
            "artifact_filename": artifact_filename,
            "message": f"Image successfully generated for '{clean_name}' and published to {public_url}"
        }
    except Exception as e:
        logger.exception("Failed to generate destination image")
        return {
            "status": "error",
            "message": f"Failed to generate image for '{clean_name}': {e}"
        }


# ==========================================
# Video Generation Tools (Gemini Omni Flash)
# ==========================================

async def generate_destination_video(
    destination_name: str,
    prompt: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Generate a short cinematic travel video preview for a destination or landmark using Google's Omni model (gemini-omni-flash-preview) in the global region.

    The generated video is saved as an artifact in the session context (visible in the Playground's Artifacts panel)
    and uploaded directly to the public Cloud Storage bucket in memory.

    Args:
        destination_name: Name of the destination, sight, or attraction (e.g. 'Eiffel Tower', 'Shibuya Crossing', 'Colosseum').
        prompt: Optional specific artistic description or scene direction. If omitted, a scenic cinematic prompt is constructed.
        tool_context: ADK execution context injected by the framework.

    Returns:
        dict: Status, public Cloud Storage video URL, artifact filename, and message.
    """
    clean_name = destination_name.strip()
    if prompt and prompt.strip():
        video_prompt = f"{prompt.strip()}. High quality cinematic travel video clip of {clean_name}, smooth camera motion, scenic 4k resolution."
    else:
        video_prompt = (
            f"A stunning cinematic 5-second travel video clip of {clean_name}, smooth aerial drone perspective, "
            f"scenic lighting, vibrant atmosphere, photorealistic detail."
        )

    try:
        genai_client = _get_genai_client()
        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=[{"type": "text", "text": video_prompt}],
            response_format=[{"type": "video", "duration": "5s", "resolution": "720p"}],
        )

        video_bytes: bytes | None = None
        mime_type = "video/mp4"

        output_video = getattr(interaction, "output_video", None)
        if output_video:
            data = getattr(output_video, "data", None) or (output_video.get("data") if isinstance(output_video, dict) else None)
            if data:
                if isinstance(data, str):
                    video_bytes = base64.b64decode(data)
                elif isinstance(data, bytes):
                    video_bytes = data

            detected_mime = getattr(output_video, "mime_type", None) or (output_video.get("mime_type") if isinstance(output_video, dict) else None)
            if detected_mime:
                mime_type = detected_mime

        if not video_bytes and hasattr(interaction, "steps"):
            for step in reversed(getattr(interaction, "steps", []) or []):
                content_list = getattr(step, "content", None) or (step.get("content") if isinstance(step, dict) else None) or []
                for item in content_list:
                    item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                    if item_type == "video":
                        item_data = getattr(item, "data", None) or (item.get("data") if isinstance(item, dict) else None)
                        if item_data:
                            video_bytes = base64.b64decode(item_data) if isinstance(item_data, str) else item_data
                            item_mime = getattr(item, "mime_type", None) or (item.get("mime_type") if isinstance(item, dict) else None)
                            if item_mime:
                                mime_type = item_mime
                            break
                if video_bytes:
                    break

        if not video_bytes:
            return {
                "status": "error",
                "message": f"Model did not return any video data for '{clean_name}'."
            }

        slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "destination"
        timestamp = int(datetime.datetime.now().timestamp())
        ext = "mp4"
        artifact_filename = f"{slug}_{timestamp}.{ext}"
        object_name = f"videos/{slug}_{timestamp}.{ext}"

        # 1. Save artifact with tool_context for playground
        if tool_context is not None:
            try:
                artifact_part = genai_types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
                await tool_context.save_artifact(
                    filename=artifact_filename,
                    artifact=artifact_part,
                    custom_metadata={"destination": clean_name, "prompt": video_prompt}
                )
            except Exception as e:
                logger.warning(f"Could not save video artifact to tool_context: {e}")

        # 2. Upload video bytes to public Cloud Storage bucket in memory (no local file)
        storage_client = _get_storage_client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(object_name)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"

        return {
            "status": "success",
            "destination_name": clean_name,
            "video_url": public_url,
            "artifact_filename": artifact_filename,
            "message": f"Video successfully generated for '{clean_name}' using gemini-omni-flash-preview and published to {public_url}"
        }
    except Exception as e:
        logger.exception("Failed to generate destination video")
        return {
            "status": "error",
            "message": f"Failed to generate video for '{clean_name}': {e}"
        }


# ==========================================
# Currency Exchange & Travel Budget Tools
# ==========================================

def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict[str, Any]:
    """Convert travel funds, expenses, and prices between foreign currencies using live European Central Bank exchange rates.

    Args:
        amount: Numerical amount of money to convert (e.g. 150.0).
        from_currency: 3-letter source currency code (e.g. 'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD').
        to_currency: 3-letter target currency code (e.g. 'JPY', 'EUR', 'USD', 'GBP', 'CHF').

    Returns:
        dict: Converted amount, current exchange rate, date, and formatted string.
    """
    clean_from = from_currency.strip().upper()
    clean_to = to_currency.strip().upper()

    if clean_from == clean_to:
        return {
            "status": "success",
            "amount": amount,
            "from_currency": clean_from,
            "to_currency": clean_to,
            "converted_amount": round(amount, 2),
            "rate": 1.0,
            "formatted": f"{amount} {clean_from} = {amount:.2f} {clean_to}",
        }

    api_url = os.environ.get("FRANKFURTER_API_URL", "https://api.frankfurter.dev/v1/latest")
    api_key = os.environ.get("EXCHANGE_RATE_API_KEY")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                api_url,
                params={"amount": amount, "from": clean_from, "to": clean_to},
                headers=headers,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Currency exchange rate lookup failed for '{clean_from}' to '{clean_to}'. Ensure valid 3-letter currency codes."
                }
            data = resp.json()
            rates = data.get("rates", {})
            converted_val = rates.get(clean_to)
            if converted_val is None:
                return {
                    "status": "error",
                    "message": f"No rate found for target currency '{clean_to}'."
                }
            rate = converted_val / amount if amount != 0 else 0
            return {
                "status": "success",
                "amount": amount,
                "from_currency": clean_from,
                "to_currency": clean_to,
                "converted_amount": round(converted_val, 2),
                "rate": round(rate, 4),
                "date": data.get("date"),
                "formatted": f"{amount} {clean_from} = {converted_val:.2f} {clean_to} (rate: 1 {clean_from} = {rate:.4f} {clean_to})",
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to perform currency conversion: {e}",
        }


# ==========================================
# Unit & Math Utility Tools
# ==========================================

def convert_units(value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
    """Convert a numerical value from one unit of measurement to another.

    Supported categories and units:
    - Temperature: celsius (c), fahrenheit (f), kelvin (k)
    - Length/Distance: meter (m), kilometer (km), centimeter (cm), millimeter (mm),
                       mile (mi), yard (yd), foot (ft), inch (in)
    - Weight/Mass: kilogram (kg), gram (g), milligram (mg), pound (lb), ounce (oz)
    - Speed: m/s, km/h, mph, knot

    Args:
        value: The numerical quantity to convert.
        from_unit: The source unit name or abbreviation (e.g. 'celsius', 'km', 'kg', 'miles').
        to_unit: The target unit name or abbreviation (e.g. 'fahrenheit', 'miles', 'lb').

    Returns:
        dict: Containing the converted result and formatted string.
    """
    f = from_unit.strip().lower()
    t = to_unit.strip().lower()

    temp_aliases = {
        "c": "celsius", "celsius": "celsius",
        "f": "fahrenheit", "fahrenheit": "fahrenheit",
        "k": "kelvin", "kelvin": "kelvin"
    }

    length_to_m = {
        "m": 1.0, "meter": 1.0, "meters": 1.0,
        "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
        "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
        "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
        "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
        "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
        "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
        "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
    }

    mass_to_g = {
        "g": 1.0, "gram": 1.0, "grams": 1.0,
        "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
        "mg": 0.001, "milligram": 0.001, "milligrams": 0.001,
        "lb": 453.59237, "pound": 453.59237, "pounds": 453.59237, "lbs": 453.59237,
        "oz": 28.349523125, "ounce": 28.349523125, "ounces": 28.349523125,
    }

    speed_to_ms = {
        "m/s": 1.0,
        "km/h": 1.0 / 3.6, "kph": 1.0 / 3.6,
        "mph": 0.44704,
        "knot": 0.514444, "knots": 0.514444,
    }

    if f in temp_aliases and t in temp_aliases:
        src_temp = temp_aliases[f]
        dst_temp = temp_aliases[t]

        if src_temp == "celsius":
            celsius = value
        elif src_temp == "fahrenheit":
            celsius = (value - 32.0) * 5.0 / 9.0
        elif src_temp == "kelvin":
            celsius = value - 273.15

        if dst_temp == "celsius":
            result = celsius
        elif dst_temp == "fahrenheit":
            result = (celsius * 9.0 / 5.0) + 32.0
        elif dst_temp == "kelvin":
            result = celsius + 273.15

        return {
            "status": "success",
            "original_value": value,
            "from_unit": src_temp,
            "converted_value": round(result, 4),
            "to_unit": dst_temp,
            "formatted": f"{value} {src_temp} = {round(result, 4)} {dst_temp}"
        }

    if f in length_to_m and t in length_to_m:
        meters = value * length_to_m[f]
        result = meters / length_to_m[t]
        return {
            "status": "success",
            "original_value": value,
            "from_unit": f,
            "converted_value": round(result, 4),
            "to_unit": t,
            "formatted": f"{value} {f} = {round(result, 4)} {t}"
        }

    if f in mass_to_g and t in mass_to_g:
        grams = value * mass_to_g[f]
        result = grams / mass_to_g[t]
        return {
            "status": "success",
            "original_value": value,
            "from_unit": f,
            "converted_value": round(result, 4),
            "to_unit": t,
            "formatted": f"{value} {f} = {round(result, 4)} {t}"
        }

    if f in speed_to_ms and t in speed_to_ms:
        ms = value * speed_to_ms[f]
        result = ms / speed_to_ms[t]
        return {
            "status": "success",
            "original_value": value,
            "from_unit": f,
            "converted_value": round(result, 4),
            "to_unit": t,
            "formatted": f"{value} {f} = {round(result, 4)} {t}"
        }

    return {
        "status": "error",
        "message": f"Unsupported unit conversion between '{from_unit}' and '{to_unit}'."
    }


_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
}

_SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        raise ValueError(f"Unknown variable or constant: {node.id}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        op_type = type(node.op)
        if op_type in _SAFE_OPS:
            return _SAFE_OPS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        op_type = type(node.op)
        if op_type in _SAFE_OPS:
            return _SAFE_OPS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS:
            args = [_eval_node(arg) for arg in node.args]
            return _SAFE_FUNCS[node.func.id](*args)
        raise ValueError("Unsupported function call")
    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def calculate_math(expression: str) -> dict[str, Any]:
    """Safely calculate a mathematical expression.

    Supports arithmetic (+, -, *, /, //, %, **), constants (pi, e),
    and functions (sqrt, sin, cos, tan, log, exp, abs, round, ceil, floor).

    Args:
        expression: A string containing the math expression to evaluate (e.g. 'sqrt(256) * 3', '2 ** 8').

    Returns:
        dict: The evaluated numerical result or an error message.
    """
    cleaned_expr = expression.strip()
    try:
        parsed = ast.parse(cleaned_expr, mode="eval")
        result = _eval_node(parsed.body)
        return {
            "status": "success",
            "expression": cleaned_expr,
            "result": result,
            "formatted": f"{cleaned_expr} = {result}"
        }
    except Exception as e:
        return {
            "status": "error",
            "expression": cleaned_expr,
            "message": f"Failed to evaluate expression: {e}"
        }
