import asyncio
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

BASE_URL = "http://localhost:8001/sport_state/mcp"

EXPECTED_TOOLS = {"get_sport_mode_state", "get_sport_mode_state_using_ros2"}


async def test_list_tools():
    client = Client(transport=StreamableHttpTransport(url=BASE_URL))
    async with client:
        assert client.is_connected()
        tools = await client.list_tools()
        names = {t.name for t in tools}
        print(f"Total tools: {len(tools)} -> {sorted(names)}")
        assert EXPECTED_TOOLS <= names, f"Missing tools: {EXPECTED_TOOLS - names}"


async def test_get_sport_mode_state_using_ros2():
    client = Client(transport=StreamableHttpTransport(url=BASE_URL))
    async with client:
        assert client.is_connected()
        for _ in range(3):
            result = await client.call_tool("get_sport_mode_state_using_ros2", {})
            content = result.structured_content
            assert content is not None

            if not content.get("success"):
                # Expected when the SDK is missing or the robot is off.
                print("unavailable:", content.get("message"))
                assert content.get("code") in (425, 503)
            else:
                sport = (content.get("data") or {}).get("sportmodestate") or {}
                print("Mode:", sport.get("mode"))
                assert "mode" in sport

            await asyncio.sleep(0.2)


async def test_get_sport_mode_state():
    client = Client(transport=StreamableHttpTransport(url=BASE_URL))
    async with client:
        assert client.is_connected()
        result = await client.call_tool("get_sport_mode_state", {})
        content = result.structured_content
        assert content is not None
        print("success:", content.get("success"), "code:", content.get("code"))
        print("message:", content.get("message"))


async def test_all_cmp_tools():
    await test_list_tools()
    print("---------------Sport Mode State Using ROS2-----------------")
    await test_get_sport_mode_state_using_ros2()
    print("---------------Sport Mode State-----------------")
    await test_get_sport_mode_state()


if __name__ == "__main__":
    asyncio.run(test_all_cmp_tools())
