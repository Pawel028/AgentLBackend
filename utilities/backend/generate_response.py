from langchain.chat_models.azure_openai import AzureChatOpenAI
# import openai
import os
from dotenv import load_dotenv, find_dotenv
import openai
from openai import OpenAI
load_dotenv(find_dotenv())

openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_version = "2022-12-01"
openai.api_key = os.getenv("OPENAI_API_KEY")

class ResponseClient():
    def __init__(self,json):
        self.json = json

    def generate_response(self):
        client = OpenAI()
        response = client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": "You are a helpful assistant designed to output JSON. you need to infer about the product regarding the health benefits. You also need to infere about the side effects"},
            {"role": "user", "content": self.json}
        ]
        )
        return response.choices[0].message.content