"""Sample data. Prices are per night in USD; meal prices are per guest per night."""

HOTELS = [
    {"id": "h1", "name": "Harbor Light Inn", "city": "Mumbai", "stars": 4, "rating": 4.4,
     "description": "A quiet harbour-side hotel ten minutes from the Gateway of India, with rooftop dining and sea breezes.",
     "amenities": ["Free Wi-Fi", "Rooftop restaurant", "Airport pickup", "Gym"],
     "rooms": [{"id": "h1-r1", "type": "Standard", "price": 95}, {"id": "h1-r2", "type": "Sea View", "price": 140},
               {"id": "h1-r3", "type": "Suite", "price": 260}]},
    {"id": "h2", "name": "Godavari Residency", "city": "Nashik", "stars": 3, "rating": 4.1,
     "description": "Comfortable stay near the ghats and temples, popular with families and vineyard visitors.",
     "amenities": ["Free Wi-Fi", "Parking", "Vegetarian restaurant", "Vineyard tours"],
     "rooms": [{"id": "h2-r1", "type": "Standard", "price": 45}, {"id": "h2-r2", "type": "Deluxe", "price": 70}]},
    {"id": "h3", "name": "Pink City Haveli", "city": "Jaipur", "stars": 5, "rating": 4.8,
     "description": "A restored haveli with courtyards, a spa and evening folk music, close to the City Palace.",
     "amenities": ["Spa", "Pool", "Courtyard dining", "Free Wi-Fi"],
     "rooms": [{"id": "h3-r1", "type": "Heritage Room", "price": 180}, {"id": "h3-r2", "type": "Royal Suite", "price": 420}]},
    {"id": "h4", "name": "Backwater Retreat", "city": "Kochi", "stars": 4, "rating": 4.6,
     "description": "Lakeside rooms and villas with houseboat trips and fresh seafood from the kitchen.",
     "amenities": ["Houseboat trips", "Pool", "Seafood restaurant", "Free Wi-Fi"],
     "rooms": [{"id": "h4-r1", "type": "Garden Room", "price": 85}, {"id": "h4-r2", "type": "Lake Villa", "price": 210}]},
    {"id": "h5", "name": "Pune Tech Stay", "city": "Pune", "stars": 3, "rating": 4.0,
     "description": "Business-friendly rooms near Hinjewadi with fast Wi-Fi, desks and a 24-hour cafe.",
     "amenities": ["Fast Wi-Fi", "Work desk", "24-hour cafe", "Parking"],
     "rooms": [{"id": "h5-r1", "type": "Single", "price": 55}, {"id": "h5-r2", "type": "Business Double", "price": 80}]},
    {"id": "h6", "name": "Himalaya Pines Lodge", "city": "Manali", "stars": 4, "rating": 4.7,
     "description": "Wooden cabins among pine trees with mountain views, bonfires and trekking guides.",
     "amenities": ["Bonfire", "Trekking guide", "Heater", "Mountain view"],
     "rooms": [{"id": "h6-r1", "type": "Cabin", "price": 110}, {"id": "h6-r2", "type": "Family Cabin", "price": 190}]},
]

MEALS = [
    {"id": "none", "name": "Room only", "price": 0, "desc": "No meals included"},
    {"id": "breakfast", "name": "Breakfast", "price": 8, "desc": "Buffet breakfast every morning"},
    {"id": "half", "name": "Half board", "price": 18, "desc": "Breakfast and dinner"},
    {"id": "full", "name": "Full board", "price": 28, "desc": "Breakfast, lunch and dinner"},
]

GUEST_NAMES = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sara", "Vihaan", "Ananya"]
