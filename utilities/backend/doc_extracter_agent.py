from langchain.chat_models.azure_openai import AzureChatOpenAI
# import openai
import os
from dotenv import load_dotenv, find_dotenv
import openai
from openai import OpenAI
from pydantic import BaseModel, ConfigDict,validator
load_dotenv(find_dotenv())

openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")

class extractor_struct(BaseModel):
    content: str
    summary: str
    completion_tokens: int
    prompt_tokens: int


def extract(json):
    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "You are a helpful assistant designed to output JSON. You need to extract the content from the output of document intelligence along with its summary and token counts."},
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": json}
                ]
            }
        ],
        response_format=extractor_struct
    )
    return response.choices[0].message.parsed
