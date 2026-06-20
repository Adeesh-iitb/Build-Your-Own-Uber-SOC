"""
city_routes.py

Predefined start and destination coordinates for testing
routing algorithms on real-world road networks.

To use a different location, simply modify ACTIVE_CITY.
"""

CITY_COORDINATES = {

    "hyderabad": {
        "start": (17.3850, 78.4867),
        "end": (17.4239, 78.4738),
        "description": "Hyderabad Centre → Secunderabad"
    },

    "mumbai": {
        "start": (19.0760, 72.8777),
        "end": (19.1136, 72.8697),
        "description": "Churchgate → Bandra"
    },

    "delhi": {
        "start": (28.6139, 77.2090),
        "end": (28.6562, 77.2410),
        "description": "Connaught Place → Civil Lines"
    },

    "bangalore": {
        "start": (12.9716, 77.5946),
        "end": (12.9352, 77.6245),
        "description": "MG Road → Koramangala"
    },

    "london": {
        "start": (51.5074, -0.1278),
        "end": (51.5155, -0.0922),
        "description": "Charing Cross → Aldgate"
    }
}


# Select the city for the routing experiment
ACTIVE_CITY = "hyderabad"

selected_route = CITY_COORDINATES[ACTIVE_CITY]

START_LATITUDE, START_LONGITUDE = selected_route["start"]

END_LATITUDE, END_LONGITUDE = selected_route["end"]

ROUTE_NAME = selected_route["description"]
