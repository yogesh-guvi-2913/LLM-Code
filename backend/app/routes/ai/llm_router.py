import logging
import json
from typing import AsyncIterator, Optional, Dict, Any, List
from openai import AsyncOpenAI
import app.config as config
from app.routes.ai.prompt_builder import parse_ai_response
from app.routes.ai.model import FileChange, CodeAction

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self):
        self.api_key = config.BEDROCK_API_KEY
        self.base_url = config.BEDROCK_BASE_URL
        self.model = config.BEDROCK_MODEL
        
        if not self.api_key or not self.base_url:
            logger.warning("BEDROCK_API_KEY or BEDROCK_BASE_URL not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info(f"LLMRouter initialized with model: {self.model}")
    
    def is_available(self) -> bool:
        return self.client is not None
    
    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> AsyncIterator[Dict[str, Any]]:
        if not self.client:
            yield {"type": "error", "error": "LLM not configured"}
            return
        
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            accumulated_text = ""
            
            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text = delta.content
                        accumulated_text += text
                        yield {"type": "text", "content": text}
            
            message, file_changes = parse_ai_response(accumulated_text)
            
            if file_changes:
                yield {"type": "code", "files": file_changes}
            
            yield {"type": "done"}
            
        except Exception as e:
            logger.error(f"LLM streaming error: {str(e)}")
            yield {"type": "error", "error": str(e)}
    
    async def chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        if not self.client:
            return {"type": "error", "error": "LLM not configured"}
        
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            content = response.choices[0].message.content
            message, file_changes = parse_ai_response(content)
            
            return {
                "type": "done",
                "message": message,
                "files": file_changes,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"LLM chat error: {str(e)}")
            return {"type": "error", "error": str(e)}

llm_router = LLMRouter()

def get_llm_router() -> LLMRouter:
    return llm_router