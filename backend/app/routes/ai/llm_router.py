import logging
import json
import re
from typing import AsyncIterator, Optional, Dict, Any, List
from openai import AsyncOpenAI
import app.config as config
from app.routes.ai.prompt_builder import parse_ai_response
from app.routes.ai.model import FileChange, CodeAction

logger = logging.getLogger(__name__)

def is_response_incomplete(text: str) -> bool:
    code_block_pattern = r'```(?:file|delete):[^\n]*\n'
    code_block_starts = len(re.findall(code_block_pattern, text))
    code_block_ends = text.count('```') - code_block_starts
    
    if code_block_starts > code_block_ends:
        return True
    
    last_code_start = text.rfind('```file:')
    if last_code_start != -1:
        after_last_block = text[last_code_start:]
        if after_last_block.count('```') < 2:
            return True
    
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    open_parens = text.count('(') - text.count(')')
    
    if abs(open_braces) > 10 or abs(open_brackets) > 10 or abs(open_parens) > 10:
        lines = text.strip().split('\n')
        last_line = lines[-1] if lines else ''
        if not last_line.strip().endswith(('}', ']', ')', '```', '"', "'")):
            return True
    
    return False


class LLMRouter:
    def __init__(self):
        self.api_key = config.BEDROCK_API_KEY
        self.base_url = config.BEDROCK_BASE_URL
        self.model = config.BEDROCK_MODEL
        self.max_retries = 5
        
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
    
    async def _stream_single(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> tuple[str, str]:
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        accumulated_text = ""
        finish_reason = "stop"
        
        async for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    accumulated_text += delta.content
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
        
        return accumulated_text, finish_reason
    
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
        
        accumulated_text = ""
        retry_count = 0
        
        try:
            current_messages = list(messages)
            
            while retry_count < self.max_retries:
                text, finish_reason = await self._stream_single(
                    system_prompt=system_prompt,
                    messages=current_messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                accumulated_text += text
                yield {"type": "text", "content": text}
                
                incomplete = is_response_incomplete(accumulated_text)
                length_limited = finish_reason == "length"
                
                if not incomplete and not length_limited:
                    break
                
                if length_limited or incomplete:
                    retry_count += 1
                    logger.info(f"Response incomplete (length_limited={length_limited}, incomplete_code={incomplete}), retrying ({retry_count}/{self.max_retries})")
                    
                    continuation_prompt = "Continue exactly from where you left off. Do not repeat any previous content. Just continue the code or text that was cut off."
                    current_messages = list(messages)
                    current_messages.append({"role": "assistant", "content": accumulated_text})
                    current_messages.append({"role": "user", "content": continuation_prompt})
                    
                    yield {"type": "retry", "count": retry_count}
                else:
                    break
            
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