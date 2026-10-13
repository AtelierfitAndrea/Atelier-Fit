from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ImageContent:
    base64: str = ""

@dataclass
class UserMessage:
    text: str = ""
    file_contents: Optional[List] = None

class LlmChat:
    def __init__(self, api_key=None, session_id=None, system_message="You are a helpful assistant."):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.model_provider = "openai"
        self.model_name = "gpt-4o-mini"
        self.temperature = 0.7

    def with_model(self, provider, model):
        self.model_provider = provider
        self.model_name = model
        return self

    def with_params(self, **kwargs):
        if "temperature" in kwargs:
