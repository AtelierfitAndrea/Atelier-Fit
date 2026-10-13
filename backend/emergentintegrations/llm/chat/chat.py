class UserMessage:
    def __init__(self, text: str):
        self.text = text

class LlmChat:
    def __init__(self, *args, **kwargs):
        pass
    def with_model(self, *args, **kwargs):
        return self
    async def send_message(self, message):
        return "Ciao! Sono Atelier Fit AI"
