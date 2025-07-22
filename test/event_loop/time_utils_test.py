from pybragi.base.time_utils import AsyncElapseCtx, async_elapsed_time
import asyncio


@async_elapsed_time(0.3)
async def xx():
    await asyncio.sleep(0.4)
    print("xx end")

async def xx2():
    async with AsyncElapseCtx(label="xx2"):
        await asyncio.sleep(0.4)
        print("xx2 end")

if __name__ == "__main__":
    asyncio.run(xx())
    asyncio.run(xx2())

