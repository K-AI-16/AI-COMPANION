from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class LLMService:

    @staticmethod
    def generate_reply(messages: list):

        response = client.responses.create(
            model="gpt-4o",
            input=messages
        )

        return response.output_text