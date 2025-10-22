import os
import json
import time
import argparse
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Load environment variables
load_dotenv(".env.example")

# Get API key
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# Cache file location
CACHE_FILE = "output/serper_results/serper_cache.json"


def load_cache():
    """Load cached results from file"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                print(f"✓ Loaded cache with {len(cache)} existing results")
                return cache
        except Exception as e:
            print(f"Warning: Could not load cache: {e}")
            return {}
    return {}


def save_cache(cache):
    """Save cache to file"""
    try:
        # Ensure output directory exists
        os.makedirs("output", exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save cache: {e}")


def query_serper(query):
    """Query Serper.dev API for a given search query"""
    url = "https://google.serper.dev/search"

    payload = json.dumps({"q": query})

    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying Serper API: {e}")
        return None


def process_facility(facility, cache, rate_limit_delay=1.0):
    """Process a single facility search with caching"""
    # Parse facility string: "Facility Name, City, State"
    # Split by ", " to get facility name, city, and state
    parts = facility.rsplit(
        ", ", 2
    )  # Split from right, max 2 splits to handle commas in facility name

    if len(parts) == 3:
        facility_name, city, state = parts
        # Format query with facility name in quotes for exact match
        query = f"{facility_name} {city} {state} email format"
    else:
        # Fallback if parsing fails
        query = f"{facility} email format"

    # Check cache first
    if facility in cache:
        print(f"[CACHED] {facility}")
        return {
            "facility": facility,
            "query": query,
            "cached": True,
            "from_cache": cache[facility],
        }

    # Not in cache, query API
    print(f"[API] Searching: {query}")

    # Add rate limiting delay
    time.sleep(rate_limit_delay)

    result = query_serper(query)

    if result:
        result_data = {
            "facility": facility,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results": result,
        }
        print(f"  ✓ Success - Found {len(result.get('organic', []))} organic results")
        return {
            "facility": facility,
            "query": query,
            "cached": False,
            "data": result_data,
        }
    else:
        result_data = {
            "facility": facility,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results": None,
            "error": "API request failed",
        }
        print(f"  ✗ Failed")
        return {
            "facility": facility,
            "query": query,
            "cached": False,
            "data": result_data,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Search for email formats using Serper.dev API"
    )
    parser.add_argument(
        "-n",
        "--num-facilities",
        type=int,
        default=10,
        help="Number of unique facilities to search (default: 10)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3)",
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear the cache before running"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Rate limit delay in seconds between API calls (default: 1.0)",
    )

    args = parser.parse_args()

    # Clear cache if requested
    if args.clear_cache and os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        print("✓ Cache cleared")

    # Load cache
    cache = load_cache()

    # Read the CSV file
    print(f"\nReading cleaned_md_doctors.csv...")
    df = pd.read_csv("cleaned_md_doctors.csv", low_memory=False)

    # Get unique full_name_city_state values
    unique_facilities = (
        df["full_name_city_state"].drop_duplicates().head(args.num_facilities).tolist()
    )

    print(f"Found {len(unique_facilities)} unique facilities to search")
    print(f"Using {args.workers} parallel workers")
    print(f"Rate limit: {args.rate_limit}s between requests")
    print("-" * 80)

    results = []
    api_calls = 0
    cache_hits = 0

    # Process facilities in parallel
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_facility = {
            executor.submit(
                process_facility, facility, cache, args.rate_limit
            ): facility
            for facility in unique_facilities
        }

        # Collect results as they complete
        for future in as_completed(future_to_facility):
            facility = future_to_facility[future]
            try:
                result = future.result()

                if result["cached"]:
                    # Add cached result to output
                    results.append(result["from_cache"])
                    cache_hits += 1
                else:
                    # Add new result to output and cache
                    results.append(result["data"])
                    cache[facility] = result["data"]
                    api_calls += 1

            except Exception as e:
                print(f"✗ Error processing {facility}: {e}")

    # Save updated cache
    if api_calls > 0:
        save_cache(cache)
        print(f"\n✓ Cache updated with {api_calls} new results")

    # Save results to JSON file
    output_file = (
        f"output/serper_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"✓ Results saved to: {output_file}")
    print(f"Total facilities: {len(results)}")
    print(f"API calls made: {api_calls}")
    print(f"Cache hits: {cache_hits}")
    print("=" * 80)


if __name__ == "__main__":
    main()
