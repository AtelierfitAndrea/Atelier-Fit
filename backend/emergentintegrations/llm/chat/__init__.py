try:
    from .chat import LlmChat, UserMessage, ImageContent
except ImportError:
    from .chat import LlmChat, UserMessage
    class ImageContent:
        def __init__(self, image_base64: str = None, image_url: str = None):
            self.image_base64 = image_base64
            self.image_url = image_url
            self.type = "image"
