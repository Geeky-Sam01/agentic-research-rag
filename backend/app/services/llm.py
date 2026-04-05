import httpx
import json
import logging
from app.core.config import settings
from typing import AsyncGenerator
from app.services.prompts import RAG_SYSTEM_PROMPT, RAG_USER_PROMPT

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

async def generate_answer(query: str, context: str) -> str:
    """Generate answer using OpenRouter."""
    
    system_prompt = RAG_SYSTEM_PROMPT
    
    user_prompt = RAG_USER_PROMPT.format(context=context, query=query)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "stream": False
                },
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-OpenRouter-Title": "Agentic RAG"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"OpenRouter error: {response.text}")
                raise Exception(f"LLM API error: {response.status_code}")
            
            data = response.json()
            return data['choices'][0]['message']['content']
            
    except Exception as e:
        logger.error(f"LLM error: {str(e)}")
        raise

async def generate_answer_stream(query: str, context: str) -> AsyncGenerator[str, None]:
    """Generate answer using OpenRouter with streaming."""
    
    system_prompt = RAG_SYSTEM_PROMPT
    
    user_prompt = RAG_USER_PROMPT.format(context=context, query=query)
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                OPENROUTER_API_URL,
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "stream": True
                },
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:4200",
                    "X-OpenRouter-Title": "Agentic RAG"
                }
            ) as response:
                
                if response.status_code != 200:
                    logger.error(f"OpenRouter stream error: {await response.atext()}")
                    raise Exception(f"LLM streaming error: {response.status_code}")
                
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)
                                if data.get('choices') and data['choices'][0].get('delta', {}).get('content'):
                                    yield data['choices'][0]['delta']['content']
                            except json.JSONDecodeError:
                                continue
                    
    except Exception as e:
        logger.error(f"LLM streaming error: {str(e)}")
        raise
