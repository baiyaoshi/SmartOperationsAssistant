import os

from openai import AsyncOpenAI
import asyncio
from dotenv import load_dotenv
load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL")
)

async def main():
    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[{"role": "user", "content": "你好"}]
    )
    #print(resp.choices[0].message.content)

#asyncio.run(main())