"""
Email Discovery Agent for Healthcare Sales Leads

This agent uses AI services to discover email addresses for healthcare organizations
by searching the web and extracting contact information.

Cost-effective approach using:
1. Serper API for search ($5/1000 searches)
2. OpenAI GPT-4o-mini for extraction (cheap ~$0.15/1M tokens)
3. Retry logic and caching to minimize costs
"""

import os
import json
import time
import pandas as pd
from typing import Dict, List, Optional
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize clients
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not SERPER_API_KEY or not OPENAI_API_KEY:
    print("⚠️ Warning: Please set SERPER_API_KEY and OPENAI_API_KEY in your .env file")
    print("Get Serper API key at: https://serper.dev/")
    print("Get OpenAI API key at: https://platform.openai.com/api-keys")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


class EmailDiscoveryAgent:
    """
    Agent that discovers email addresses for healthcare organizations
    """

    def __init__(self, cache_file: str = "email_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.searches_count = 0
        self.api_calls_count = 0

    def _load_cache(self) -> Dict:
        """Load cached email results"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """Save cache to disk"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def _create_cache_key(self, facility_name: str, city: str, state: str) -> str:
        """Create unique cache key for organization"""
        return f"{facility_name.lower().strip()}|{city.lower()}|{state.lower()}"

    def _search_web(self, query: str) -> List[Dict]:
        """
        Search web using Serper API
        Cost: ~$5/1000 searches
        """
        if not SERPER_API_KEY:
            return []

        url = "https://google.serper.dev/search"
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }

        payload = json.dumps({
            "q": query,
            "num": 5  # Get top 5 results
        })

        try:
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            response.raise_for_status()
            self.searches_count += 1

            data = response.json()
            results = []

            # Extract organic results
            if 'organic' in data:
                for result in data['organic']:
                    results.append({
                        'title': result.get('title', ''),
                        'link': result.get('link', ''),
                        'snippet': result.get('snippet', '')
                    })

            return results

        except Exception as e:
            print(f"Search error: {e}")
            return []

    def _extract_emails_with_ai(self, facility_name: str, search_results: List[Dict]) -> Dict:
        """
        Use GPT-4o-mini to extract emails from search results
        Cost: ~$0.15/1M input tokens, $0.60/1M output tokens
        """
        if not client or not search_results:
            return {"emails": [], "confidence": "low", "source": "none"}

        # Prepare context from search results
        context = f"Organization: {facility_name}\n\n"
        context += "Search Results:\n"
        for i, result in enumerate(search_results[:5], 1):
            context += f"\n{i}. {result['title']}\n"
            context += f"   URL: {result['link']}\n"
            context += f"   {result['snippet']}\n"

        prompt = f"""Analyze these search results for {facility_name} and extract email addresses.

{context}

Please provide:
1. Any email addresses found (general contact, info, admin, etc.)
2. Email patterns for the organization (e.g., firstname.lastname@domain.com)
3. The official website domain
4. Your confidence level (high/medium/low) in the results

Return as JSON:
{{
    "emails": ["list of email addresses found"],
    "email_pattern": "pattern if determinable, e.g. firstname.lastname@domain.com",
    "domain": "official domain",
    "confidence": "high/medium/low",
    "website": "official website URL",
    "notes": "any relevant notes"
}}

If no emails found, return empty emails list with low confidence."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Cheapest model
                messages=[
                    {"role": "system", "content": "You are an expert at finding contact information for healthcare organizations. Extract email addresses and patterns from search results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            self.api_calls_count += 1
            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"AI extraction error: {e}")
            return {"emails": [], "confidence": "low", "source": "error"}

    def discover_email(self, facility_name: str, city: str, state: str,
                      address: str = "", phone: str = "") -> Dict:
        """
        Discover email for a healthcare organization

        Args:
            facility_name: Name of the healthcare facility
            city: City location
            state: State location
            address: Full address (optional)
            phone: Phone number (optional)

        Returns:
            Dict with email discovery results
        """
        # Check cache first
        cache_key = self._create_cache_key(facility_name, city, state)
        if cache_key in self.cache:
            print(f"✓ Cache hit: {facility_name}")
            return self.cache[cache_key]

        print(f"🔍 Searching: {facility_name}, {city}, {state}")

        # Search for organization website and contact info
        query = f'"{facility_name}" {city} {state} contact email'
        search_results = self._search_web(query)

        if not search_results:
            result = {
                "facility_name": facility_name,
                "city": city,
                "state": state,
                "emails": [],
                "confidence": "low",
                "website": "",
                "notes": "No search results found"
            }
            self.cache[cache_key] = result
            self._save_cache()
            return result

        # Extract emails using AI
        time.sleep(0.5)  # Rate limiting
        extraction = self._extract_emails_with_ai(facility_name, search_results)

        result = {
            "facility_name": facility_name,
            "city": city,
            "state": state,
            "emails": extraction.get("emails", []),
            "email_pattern": extraction.get("email_pattern", ""),
            "domain": extraction.get("domain", ""),
            "confidence": extraction.get("confidence", "low"),
            "website": extraction.get("website", ""),
            "notes": extraction.get("notes", ""),
            "searched_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Cache the result
        self.cache[cache_key] = result
        self._save_cache()

        return result

    def discover_emails_batch(self, organizations_df: pd.DataFrame,
                             max_orgs: int = 100) -> pd.DataFrame:
        """
        Discover emails for a batch of organizations

        Args:
            organizations_df: DataFrame with columns: Facility_Name, City, State
            max_orgs: Maximum number of organizations to process

        Returns:
            DataFrame with email discovery results
        """
        results = []

        # Limit to max_orgs
        orgs_to_process = organizations_df.head(max_orgs)

        print(f"\n🤖 Starting email discovery for {len(orgs_to_process)} organizations...")
        print(f"Estimated cost: ~${(len(orgs_to_process) * 0.005):.2f} for searches + ~$0.01 for AI\n")

        for idx, row in orgs_to_process.iterrows():
            facility_name = row.get('Facility_Name', row.get('Facility Name', ''))
            city = row.get('City', row.get('city_clean', ''))
            state = row.get('State', row.get('state_clean', ''))
            address = row.get('Address', row.get('full_address', ''))
            phone = row.get('Phone', row.get('phone_clean', ''))

            if not facility_name or facility_name == "Unknown Organization":
                continue

            result = self.discover_email(facility_name, city, state, address, phone)
            results.append(result)

            # Progress update
            if (len(results) % 10) == 0:
                print(f"Progress: {len(results)}/{len(orgs_to_process)} organizations processed")

        print(f"\n✅ Complete! Processed {len(results)} organizations")
        print(f"📊 Searches made: {self.searches_count}")
        print(f"🤖 AI calls made: {self.api_calls_count}")

        results_df = pd.DataFrame(results)
        return results_df

    def export_results(self, results_df: pd.DataFrame, output_file: str = "email_discoveries.csv"):
        """Export results to CSV"""
        results_df.to_csv(output_file, index=False)
        print(f"\n💾 Results saved to {output_file}")

        # Print summary
        total = len(results_df)
        with_emails = len(results_df[results_df['emails'].apply(lambda x: len(x) > 0)])
        high_conf = len(results_df[results_df['confidence'] == 'high'])

        print(f"\n📈 Summary:")
        print(f"   Total organizations: {total}")
        print(f"   With emails found: {with_emails} ({with_emails/total*100:.1f}%)")
        print(f"   High confidence: {high_conf} ({high_conf/total*100:.1f}%)")


def main():
    """
    Example usage of the Email Discovery Agent
    """
    print("🤖 Healthcare Email Discovery Agent")
    print("=" * 50)

    # Check if API keys are set
    if not SERPER_API_KEY or not OPENAI_API_KEY:
        print("\n❌ Error: API keys not configured!")
        print("\nPlease create a .env file with:")
        print("SERPER_API_KEY=your_key_here")
        print("OPENAI_API_KEY=your_key_here")
        return

    # Initialize agent
    agent = EmailDiscoveryAgent()

    # Load the exported leads from the dashboard
    print("\n📂 Loading leads from dashboard export...")

    # Try to find the most recent high-value leads export
    import glob
    export_files = glob.glob("high_value_leads_*.csv")

    if not export_files:
        print("❌ No high-value leads export found!")
        print("Please export high-value leads from the dashboard first.")
        return

    # Use most recent file
    export_file = sorted(export_files)[-1]
    print(f"✓ Found: {export_file}")

    # Load the data
    df = pd.read_csv(export_file)
    print(f"✓ Loaded {len(df)} organizations")

    # Get unique facilities (since we have multiple providers per facility)
    unique_facilities = df.groupby(['Facility_Name', 'City', 'State']).first().reset_index()
    print(f"✓ Found {len(unique_facilities)} unique facilities")

    # Ask how many to process
    print(f"\n💡 Recommended: Start with 10-20 organizations to test")
    print(f"Estimated cost for 100 orgs: ~$0.50-1.00")

    try:
        max_orgs = int(input("\nHow many organizations to process? (default: 10): ") or "10")
    except ValueError:
        max_orgs = 10

    # Run email discovery
    results = agent.discover_emails_batch(unique_facilities, max_orgs=max_orgs)

    # Export results
    agent.export_results(results)

    # Show some examples
    print("\n📧 Sample Results:")
    print("-" * 50)
    for idx, row in results.head(5).iterrows():
        print(f"\n{row['facility_name']}")
        print(f"  Location: {row['city']}, {row['state']}")
        if row['emails']:
            print(f"  Emails: {', '.join(row['emails'])}")
        if row['website']:
            print(f"  Website: {row['website']}")
        print(f"  Confidence: {row['confidence']}")


if __name__ == "__main__":
    main()
