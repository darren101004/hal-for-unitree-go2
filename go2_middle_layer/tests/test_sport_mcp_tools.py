import asyncio
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

BASE_URL = "http://localhost:8001/sport/mcp"

async def test_list_tools():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        tools = await client.list_tools()
        print(f"Total tools: {len(tools)}")
        for tool in tools:
            print(tool.name)

async def test_stand_up():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("stand_up", {})
        print(result)

async def test_stand_down():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("stand_down", {})
        print(result)

async def test_move_forward(distance: int = 30):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("move_forward", {"distance": distance})
        print(result)


async def test_move_backward(distance: int = 30):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("move_backward", {"distance": distance})
        print(result)

async def test_step_to_left(distance: int = 30):  
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("step_to_left", {"distance": distance})
        print(result)

async def test_step_to_right(distance: int = 30):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("step_to_right", {"distance": distance})
        print(result)


async def test_turn_left(angle: int = 45):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("turn_left", {"angle": angle})
        print(result)

async def test_turn_right(angle: int = 45):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("turn_right", {"angle": angle})
        print(result)   

async def test_move_to_target_position(angle: float = 45, distance: float = 100):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("move_to_target_position", {"angle": angle, "distance": distance})
        print(result)


async def test_multi_step():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        async def task_1():
            print("Moving forward...")
            result = await client.call_tool("move_forward", {"distance": 300})
            print(result)
            return result
           
        async def task_2():
            await asyncio.sleep(4)
            print("Turning left...")
            result = await client.call_tool("turn_left", {"angle": 180})
            print(result)
            return result
        
        async def task_3():
            await asyncio.sleep(8)
            print("Stopping move...")
            result = await client.call_tool("stop_move", {})
            print(result)
            return result
        
        tasks = [task_1(), task_2(), task_3()]
        results = await asyncio.gather(*tasks)
        print("All tasks completed")
        print(results)
            
    
async def test_all_cmp_tools():
    await test_list_tools()
    import time
    # await test_multi_step()
    # start_time = time.time()
    # await test_stand_up()
    # end_time = time.time()
    # print(f"Time taken for stand up: {end_time - start_time} seconds")
    # await test_move_forward(distance=100)
    # await asyncio.sleep(2) 
    # await test_move_to_target_position(angle=0, distance=1000)
    # print("Waiting for 2 seconds...")
    # await test_move_backward(distance=100)
    # await asyncio.sleep(2) 
    # print("Waiting for 2 seconds...")
    # await test_step_to_left(distance=30)
    # await asyncio.sleep(2) 
    # print("Waiting for 2 seconds...")
    # await test_step_to_right(distance=30)
    # await asyncio.sleep(2) 
    # print("Waiting for 2 seconds...")
    # await test_turn_left(angle=30)
    # await asyncio.sleep(2) 
    # await test_turn_left(angle=30)
    # await asyncio.sleep(2)
    # await test_turn_left(angle=30)
    # await asyncio.sleep(2)    
    # await test_turn_left(angle=30)
    # await asyncio.sleep(2)    
    # await test_turn_left(angle=40)
    # await asyncio.sleep(2)    
    # start_time = time.time()
    await test_turn_left(angle=100)
    # end_time = time.time()
    # print(f"Time taken for turn left: {end_time - start_time} seconds")
    # await asyncio.sleep(2)    
    # print("Waiting for 2 seconds...")
    # await test_turn_right(angle=180)
    await asyncio.sleep(3) 
    # print("Waiting for 3 seconds...")
    # start_time = time.time()
    await test_stand_down()
    # end_time = time.time()
    # print(f"Time taken for stand down: {end_time - start_time} seconds")
    
if __name__ == "__main__":
    asyncio.run(test_all_cmp_tools())