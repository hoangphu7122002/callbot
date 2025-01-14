import openai
from config.config import config
from .dify_bot_client import DifyBotClient

class ChatbotClient:
    """
    Manages conversation with OpenAI's GPT model.
    Maintains conversation history and handles the chat flow.
    """
    
    def __init__(self, config):
        """Initialize OpenAI client and conversation history"""
        self.config = config
        # Khởi tạo end_keywords cho mọi loại bot
        self.end_keywords = config.END_CONVERSATION_KEYWORDS
        
        if config.BOT_TYPE == "dify":
            self.bot = DifyBotClient(
                api_url=config.DIFY_API_URL,
                api_key=config.DIFY_API_KEY
            )
        else:
            self.conversation_history = []
            openai.api_key = config.OPENAI_API_KEY
        
    async def get_response(self, message):
        """
        Get response from GPT model for user input.
        
        Args:
            message (str): User's message text
            
        Returns:
            str: Bot's response
            
        Note:
            Maintains conversation history for context
            Handles API errors gracefully
        """
        if self.config.BOT_TYPE == "dify":
            # Reset conversation nếu là tin nhắn đầu tiên
            if not hasattr(self, 'conversation_started'):
                self.bot.reset_conversation()
                self.conversation_started = True
            return await self.bot.get_response(message)
        else:
            self.conversation_history.append({"role": "user", "content": message})
            
            try:
                response = openai.ChatCompletion.create(
                    model=self.config.GPT_MODEL,
                    messages=self.conversation_history
                )
                
                bot_response = response.choices[0].message.content
                self.conversation_history.append({
                    "role": "assistant", 
                    "content": bot_response
                })
                
                return bot_response
                
            except Exception as e:
                print(f"Error calling OpenAI API: {e}")
                return "Xin lỗi, tôi đang gặp sự cố kỹ thuật."
    
    def should_end_conversation(self, text: str) -> bool:
        """
        Check if the conversation should be ended based on user input.
        
        Args:
            text (str): User's message text
            
        Returns:
            bool: True if end conversation is detected, False otherwise
        """
        # Kiểm tra từ khóa kết thúc
        if any(keyword in text.lower() for keyword in self.end_keywords):
            return True
        
        # Kiểm tra marker kết thúc
        if "##END##" in text:
            return True
        
        return False