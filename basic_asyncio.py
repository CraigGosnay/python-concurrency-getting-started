import asyncio
import time
import logging
import concurrent.futures
logging.basicConfig()

class AsyncTesting():
    
    def slow_factorial(self, n):
        if n == 0:
            return 1
        else:
            return n * self.slow_factorial(n-1)

    async def factorial_async(self, loop, executor, n):
        # allows us to execute the synchronous "library" call as async
        nfact = await loop.run_in_executor(executor, self.slow_factorial, n)
        logging.info(f"factorial of {n} is {nfact}")

    async def solve(self):
        start = time.perf_counter()
        logging.info("starting")
        await self.some_io()
        end = time.perf_counter()
        logging.info(f"complete in {end - start}")
    
    async def some_io(self):
        logging.info("beginning io")
        await asyncio.sleep(10)
        logging.info("completed io")
    
    def run_basic(self):
        asyncio.run(self.solve())

    def run_combine_async_multiproc(self):
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=3)
        loop = asyncio.get_event_loop()
        n = 25
        loop.run_until_complete(self.factorial_async(loop, executor, n))