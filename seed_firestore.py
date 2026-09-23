"""Seed script for populating the Firestore destinations collection.

Hardcoded project ID ensures compatibility with Agent Platform / Agent Runtime.
"""

from google.cloud import firestore

# IMPORTANT: Hardcode project ID as a string, not from auth default or env var
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-04-69c9c83b08f1"

SEEDED_DESTINATIONS = [
    {
        "id": "eiffel-tower",
        "name": "Eiffel Tower",
        "city": "Paris",
        "country": "France",
        "category": "landmark",
        "description": "Iconic iron lattice tower on the Champ de Mars with panoramic views over Paris.",
        "rating": 4.7,
        "price_tier": "$$",
        "tags": ["iconic", "views", "architecture", "romantic"],
        "recommended_duration_hours": 2.5,
    },
    {
        "id": "louvre-museum",
        "name": "Louvre Museum",
        "city": "Paris",
        "country": "France",
        "category": "museum",
        "description": "World's largest art museum housing historic treasures like the Mona Lisa and Venus de Milo.",
        "rating": 4.8,
        "price_tier": "$$",
        "tags": ["art", "history", "mona-lisa", "culture"],
        "recommended_duration_hours": 3.5,
    },
    {
        "id": "senso-ji",
        "name": "Senso-ji Temple",
        "city": "Tokyo",
        "country": "Japan",
        "category": "cultural",
        "description": "Tokyo's oldest and most significant ancient Buddhist temple located in historic Asakusa.",
        "rating": 4.7,
        "price_tier": "free",
        "tags": ["temple", "historic", "asakusa", "culture"],
        "recommended_duration_hours": 2.0,
    },
    {
        "id": "shibuya-crossing",
        "name": "Shibuya Crossing",
        "city": "Tokyo",
        "country": "Japan",
        "category": "landmark",
        "description": "World's busiest pedestrian scramble crossing surrounded by giant video screens and neon lights.",
        "rating": 4.6,
        "price_tier": "free",
        "tags": ["urban", "neon", "iconic", "walk"],
        "recommended_duration_hours": 1.0,
    },
    {
        "id": "colosseum",
        "name": "The Colosseum",
        "city": "Rome",
        "country": "Italy",
        "category": "landmark",
        "description": "The largest ancient amphitheater ever built, situated in the historic heart of Rome.",
        "rating": 4.8,
        "price_tier": "$$",
        "tags": ["ancient", "history", "gladiators", "monument"],
        "recommended_duration_hours": 2.5,
    },
    {
        "id": "trastevere-food-tour",
        "name": "Trastevere Evening Food & Wine Tour",
        "city": "Rome",
        "country": "Italy",
        "category": "food & dining",
        "description": "Authentic Roman culinary walk tasting carbonara, supplì, local cheeses, and artisanal gelato.",
        "rating": 4.9,
        "price_tier": "$$$",
        "tags": ["culinary", "pasta", "wine", "local", "dinner"],
        "recommended_duration_hours": 3.0,
    },
    {
        "id": "fushimi-inari",
        "name": "Fushimi Inari Shrine",
        "city": "Kyoto",
        "country": "Japan",
        "category": "cultural",
        "description": "Iconic Shinto shrine famous for its thousands of vibrant vermilion torii gates winding up Mount Inari.",
        "rating": 4.9,
        "price_tier": "free",
        "tags": ["torii-gates", "shrine", "hiking", "views", "spiritual"],
        "recommended_duration_hours": 2.5,
    },
]


def seed_database():
    print(f"Connecting to Firestore for project: {FIRESTORE_PROJECT_ID}...")
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    collection_ref = db.collection("destinations")

    count = 0
    for item in SEEDED_DESTINATIONS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  ✓ Seeded destination: {item['name']} ({item['city']}, {item['country']})")
        count += 1

    print(f"\nSuccessfully seeded {count} destinations to Firestore collection 'destinations'!")


if __name__ == "__main__":
    seed_database()
