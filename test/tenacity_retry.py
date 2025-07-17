import asyncio
from pybragi.base import time_utils
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import RateLimitError, APIConnectionError, APITimeoutError
import numpy as np


@retry(
    stop=stop_after_attempt(10), # call func total 10 times (retry 9 times)
    wait=wait_exponential(multiplier=1, min=1, max=9), # wait 1s, 2s, 4s, 8s, 9s, 9s...
    retry=retry_if_exception_type(
        (RateLimitError, APIConnectionError, APITimeoutError, Warning)
    ),
)
async def embedding_func(texts: list[str]) -> np.ndarray:
    logging.info(f"embedding_func start")
    raise Warning("test")



if __name__ == "__main__":
    asyncio.run(embedding_func(["test"]))
    print("end")

