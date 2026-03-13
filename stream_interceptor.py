import asyncio
import logging
import re
from collections.abc import AsyncIterator

logger = logging.getLogger("pii_proxy.interceptor")
_TOKEN_RE = re.compile(r"^\[[A-Z_]+_\d+\]$")
MAX_BUFFER_SIZE = 50
UNKNOWN_TOKEN_PLACEHOLDER = "***"

async def unmask_stream(
    source: AsyncIterator[str],
    mapping: dict[str, str],
) -> AsyncIterator[str]:
    buffer = ""
    buffering = False
    async for chunk in source:
        for char in chunk:
            if buffering:
                buffer += char
                if char == "]":
                    if _TOKEN_RE.match(buffer):
                        if buffer in mapping:
                            yield mapping[buffer]
                        else:
                            logger.warning(
                                "Unknown mask token in LLM response: %s",
                                buffer,
                            )
                            yield UNKNOWN_TOKEN_PLACEHOLDER
                    else:
                        yield buffer
                    buffer = ""
                    buffering = False
                elif len(buffer) > MAX_BUFFER_SIZE:
                    yield buffer
                    buffer = ""
                    buffering = False
            else:
                if char == "[":
                    buffering = True
                    buffer = "["
                else:
                    yield char
    if buffer:
        yield buffer

async def _demo():
    mapping = {
        "[PER_1]": "Иванов Иван",
        "[PHONE_1]": "+7 999 123-45-67",
    }
    chunks_1 = [
        "Здравствуйте, ",
        "[",
        "PER",
        "_1]",
        "! Ваш номер: ",
        "[PHONE",
        "_1]",
        ". Чем могу помочь?",
    ]
    async def stream_1():
        for c in chunks_1:
            yield c
    result = []
    async for piece in unmask_stream(stream_1(), mapping):
        result.append(piece)
    text = "".join(result)
    expected = "Здравствуйте, Иванов Иван! Ваш номер: +7 999 123-45-67. Чем могу помочь?"
    assert text == expected
    chunks_2 = ["Привет, ", "[PER_99]", "!"]
    async def stream_2():
        for c in chunks_2:
            yield c
    result = []
    async for piece in unmask_stream(stream_2(), mapping):
        result.append(piece)
    text = "".join(result)
    expected = f"Привет, {UNKNOWN_TOKEN_PLACEHOLDER}!"
    assert text == expected
    chunks_3 = ["Список: [1] яблоки, [2] груши"]
    async def stream_3():
        for c in chunks_3:
            yield c
    result = []
    async for piece in unmask_stream(stream_3(), mapping):
        result.append(piece)
    text = "".join(result)
    expected = "Список: [1] яблоки, [2] груши"
    assert text == expected
    long_content = "x" * 60
    chunks_4 = [f"текст [{long_content}] конец"]
    async def stream_4():
        for c in chunks_4:
            yield c
    result = []
    async for piece in unmask_stream(stream_4(), mapping):
        result.append(piece)
    text = "".join(result)
    assert long_content[:49] in text

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_demo())
