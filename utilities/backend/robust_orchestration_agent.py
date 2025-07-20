"""
# Robust Orchestration Framework for Agentic AI
This file contains classes to:
- Decide if external tools (search/scraping) are needed.
- Identify if more user information is required.
- Route orchestration through tailored plans.
- Output formatted Markdown reports.
"""

from openai import OpenAI
from typing import List, Dict, Any
import json

# Add your own import paths if needed
from webscraping import google_search, scrape_website
from pydantic import BaseModel, ConfigDict,validator
from typing import Optional, List, Dict, Any
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv, find_dotenv
import os
import openai
load_dotenv(find_dotenv())

openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI()

# ----------- Helper Agents -----------

def query_needs_search(query: str, chat_history: str) -> bool:
    """Uses LLM to determine if search/scraping is necessary."""
    decision = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You're a smart assistant. Answer 'yes' or 'no'. Does this user query require an online search or scraping to answer?"},
            {"role": "user", "content": f"Query: {query}\nChat: {chat_history}"}
        ],
        temperature=0
    ).choices[0].message.content.strip().lower()
    return "yes" in decision

def needs_more_info(query: str, chat_history: str, image_text: str) -> str:
    """Checks if additional input is required."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Do we need more information to proceed? Respond with the specific question to ask, or 'no' if nothing else is needed."},
            {"role": "user", "content": f"Query: {query}\nChat: {chat_history}\nImage Text: {image_text}"}
        ],
        temperature=0
    ).choices[0].message.content.strip()
    return response

# ----------- Orchestration Templates -----------

def generate_orchestration_plan_scenario(query: str, image_text: str, chat: str, party_data: str) -> Dict:
    """Generate tailored orchestration for a legal scenario."""
    prompt = f"""
You're a legal AI agent. Create a step-by-step plan to address this issue. Return JSON with fields: Step_id, Instructions, input_required, output_required, tools (optional).
Query: {query}
Chat: {chat}
Image Text: {image_text}
Party Data: {party_data}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Generate a detailed orchestration plan for legal processing."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content

# ----------- Main Executor -----------

class RobustLitigatorAgent:
    def __init__(self, query: str, chat_history: List[str], image_text: str, party_data: str):
        self.query = query
        self.chat_history = "\n".join(chat_history) if isinstance(chat_history, list) else chat_history
        self.image_text = image_text
        self.party_data = party_data
        self.search_results = []
        self.scraped_info = []

    def run(self):
        markdown_output = []

        # Step 1: Check if more info is needed
        question = needs_more_info(self.query, self.chat_history, self.image_text)
        if question.lower() != "no":
            markdown_output.append(f"⚠️ **More Info Required:** {question}")
            return "\n".join(markdown_output)

        # Step 2: Determine if search/scraping is needed
        use_tools = query_needs_search(self.query, self.chat_history)

        if use_tools:
            markdown_output.append("🔍 **Search Triggered**")
            # Perform search (replace keys with your real keys)
            google_data = google_search(self.query, api_key="YOUR_API_KEY", cse_id="YOUR_CSE_ID")
            top_urls = [item["link"] for item in google_data.get("items", [])]
            self.search_results = top_urls[:3]
            markdown_output.append(f"**Top URLs:**\n" + "\n".join([f"- {url}" for url in self.search_results]))

            # Scrape first site
            try:
                scraped = scrape_website(self.search_results[0])
                self.scraped_info = scraped
                markdown_output.append("🧾 **Scraped Info Summary:**")
                markdown_output.append(f"- **Title**: {scraped['title']}")
                markdown_output.append(f"- **Meta Description**: {scraped['meta_description']}")
                markdown_output.append(f"- **Headings**: {[t for _, t in scraped['headings']]}")
            except Exception as e:
                markdown_output.append(f"❌ Scraping failed: {e}")

        # Step 3: Orchestrate
        orchestration = generate_orchestration_plan_scenario(
            query=self.query,
            image_text=self.image_text,
            chat=self.chat_history,
            party_data=self.party_data
        )

        markdown_output.append("\n📋 **Orchestration Plan:**")
        for step in orchestration.get("Orchestrator", []):
            markdown_output.append(f"""
- **Step {step['Step_id']}**: {step['Instructions']}
  - **Input Required**: {', '.join(step['input_required'])}
  - **Output Required**: {', '.join(step['output_required'])}
  - **Tools**: {', '.join(step['tools']) if step.get('tools') else 'None'}
""")

        return "\n".join(markdown_output)

if __name__ == "__main__":
    query = "what are writ petitions?"
    chat_history = []
    image_txt = ""
    party_data = ""
    obj = generate_orchestration_plan_scenario(query=query, image_text=image_txt, chat=chat_history, party_data=party_data)
    print(obj)