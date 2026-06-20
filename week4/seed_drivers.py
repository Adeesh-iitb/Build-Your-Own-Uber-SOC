import json
import random
from pathlib import Path

CITY_LATITUDE = 17.3850
CITY_LONGITUDE = 78.4867

DRIVER_COUNT = 10_000
OFFSET_RANGE = 0.15


def create_driver_locations(total_drivers=DRIVER_COUNT):
    """
    Generate random driver positions around a city center.
    """

    records = {}

    for index in range(total_drivers):

        identifier = f"driver_{index:05d}"

        latitude = CITY_LATITUDE + random.uniform(
            -OFFSET_RANGE,
            OFFSET_RANGE,
        )

        longitude = CITY_LONGITUDE + random.uniform(
            -OFFSET_RANGE,
            OFFSET_RANGE,
        )

        records[identifier] = {
            "lat": latitude,
            "lng": longitude,
        }

    return records


def export_json(data, destination="drivers_fallback.json"):
    """
    Save generated drivers to disk.
    """

    output_path = Path(destination)

    with output_path.open("w") as fp:
        json.dump(data, fp, indent=2)

    print(
        f"{len(data):,} driver records written to "
        f"{output_path}"
    )


def upload_to_redis(driver_data):
    """
    Load coordinates into Redis GEO index.
    """

    import redis

    connection = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    geo_key = "drivers:geo"

    connection.delete(geo_key)

    batch = connection.pipeline()

    for driver_id, position in driver_data.items():

        batch.geoadd(
            geo_key,
            (
                position["lng"],
                position["lat"],
                driver_id,
            ),
        )

    batch.execute()

    print(
        f"{len(driver_data):,} drivers inserted "
        f"into Redis GEO index"
    )


def main():

    print(
        f"Creating {DRIVER_COUNT:,} driver locations "
        f"around ({CITY_LATITUDE}, {CITY_LONGITUDE})"
    )

    drivers = create_driver_locations()

    try:
        upload_to_redis(drivers)

    except Exception as error:

        print(
            "Redis unavailable. "
            "Saving locally instead."
        )

        print(f"Reason: {error}")

        export_json(drivers)


if __name__ == "__main__":
    main()
