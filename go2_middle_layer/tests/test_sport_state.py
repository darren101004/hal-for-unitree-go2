import asyncio
import time
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

# BASE_URL = "http://localhost:8005/mcp/state"
BASE_URL = "http://localhost:8001/sport_state/mcp"

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


async def test_get_sport_mode_state_using_echo():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        cnt = 0
        while cnt < 3:
            result = await client.call_tool("get_sport_mode_state_using_echo", {})
            # print("Result: ", result)
            # print("Type of result: ", type(result))
            structured_content = result.structured_content
            # print("structured_content of result: ", structured_content)
            # print("Type of structured_content: ", type(structured_content))
            
            data = structured_content.get("data")
            # print("data of result: ", data)
            # print("Type of data: ", type(data))
            sport = (data or {}).get("sportmodestate") or {}
            print("Mode: ", sport.get("mode"), type(sport.get("mode")))
            # import json
            # print("data of result: ", json.dumps(data, indent=4))
            
            cnt += 1
            await asyncio.sleep(0.2)

async def test_get_sport_mode_state_using_ros2():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        cnt = 0
        while cnt < 3:
            result = await client.call_tool("get_sport_mode_state_using_ros2", {})
            structured_content = result.structured_content
            
            data = structured_content.get("data")
            sport = (data or {}).get("sportmodestate") or {}
            print("Mode: ", sport.get("mode"), type(sport.get("mode")))
            cnt += 1
            await asyncio.sleep(0.2)
            
    
async def test_get_sport_mode_state():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        for _ in range(20):
            tasks = [
                client.call_tool("get_sport_mode_state_using_echo", {}),
                client.call_tool("get_sport_mode_state_using_ros2", {}),
            ]
            results = await asyncio.gather(*tasks)

            r1 = results[0].structured_content
            
            data1 = r1.get("data") or {}
            mode1 = (data1.get("sportmodestate") or {}).get("mode")

            r2 = results[1].structured_content
            data2 = r2.get("data") or {}
            mode2 = (data2.get("sportmodestate") or {}).get("mode")

            print("Using Echo: ", mode1)
            print("Using ROS2: ", mode2)
            if mode1 == mode2:
                print("--------------------------------")
            else:
                print("Mode is different")

            import json
            with open("r1.json", "w") as f:
                json.dump(r1, f, indent=4)
            with open("r2.json", "w") as f:
                json.dump(r2, f, indent=4)
            await asyncio.sleep(0.05)

async def test_all_cmp_tools():
    await test_list_tools()
    # print("---------------Sport Mode State Using Echo-----------------")
    # await test_get_sport_mode_state_using_echo()
    # print("---------------Sport Mode State Using ROS2-----------------")
    # await test_get_sport_mode_state_using_ros2()
    print("---------------Sport Mode State-----------------")
    await test_get_sport_mode_state()
    
if __name__ == "__main__":
    asyncio.run(test_all_cmp_tools())