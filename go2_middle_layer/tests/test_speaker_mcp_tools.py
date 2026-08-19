import asyncio
import time

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

BASE_URL = "http://localhost:8001/speaker/mcp"


async def test_list_tools():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        tools = await client.list_tools()
        print(f"Total tools: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")


async def test_speak_text(text: str = "Hello! I am the robot dog. Nice to meet you."):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        start_time = time.time()
        result = await client.call_tool("speak_text", {"text": text})
        elapsed = time.time() - start_time
        struct_content = result.structured_content
        print(f"speak_text result:")
        print(f"  Success: {struct_content.get('success')}")
        print(f"  Message: {struct_content.get('message')}")
        print(f"  Time: {elapsed:.2f}s")


async def test_speak_text_with_interrupt():
    """Test speaking with interrupt: start a long sentence, then interrupt with a short one."""
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()

        async def long_speech():
            result = await client.call_tool("speak_text", {
                "text": "This is a very long sentence that should take a while to finish speaking. I am going to keep talking for a long time so that the interrupt can be tested properly.",
            })
            struct_content = result.structured_content
            print(f"Long speech result: success={struct_content.get('success')}, message={struct_content.get('message')}")

        async def interrupt_speech():
            await asyncio.sleep(2)
            print("Sending interrupt speech...")
            result = await client.call_tool("speak_text", {
                "text": "Interrupted!",
                "interrupt": True,
            })
            struct_content = result.structured_content
            print(f"Interrupt speech result: success={struct_content.get('success')}, message={struct_content.get('message')}")

        await asyncio.gather(long_speech(), interrupt_speech())


async def test_recorded_audio_speak(audio_name: str = "greeting"):
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        start_time = time.time()
        result = await client.call_tool("recorded_audio_speak", {"audio_name": audio_name, "times": 5})
        elapsed = time.time() - start_time
        struct_content = result.structured_content
        print(f"recorded_audio_speak('{audio_name}') result:")
        print(f"  Success: {struct_content.get('success')}")
        print(f"  Message: {struct_content.get('message')}")
        print(f"  Time: {elapsed:.2f}s")


async def test_recorded_audio_speak_not_found():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("recorded_audio_speak", {"audio_name": "bark"})
        struct_content = result.structured_content
        print(f"recorded_audio_speak('bark') result:")
        print(f"  Success: {struct_content.get('success')}")
        print(f"  Message: {struct_content.get('message')}")


async def test_stop_speaking():
    """Test stop_speaking: start speech then stop it mid-way."""
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()

        async def long_speech():
            result = await client.call_tool("speak_text", {
                "text": "I will keep talking for a while so that the stop command can be tested. Let me tell you a story about a robot dog who loved to explore the world.",
            })
            struct_content = result.structured_content
            print(f"Long speech result: success={struct_content.get('success')}, message={struct_content.get('message')}")

        async def stop_after_delay():
            await asyncio.sleep(2)
            print("Sending stop_speaking...")
            result = await client.call_tool("stop_speaking", {})
            struct_content = result.structured_content
            print(f"stop_speaking result: success={struct_content.get('success')}, message={struct_content.get('message')}")

        await asyncio.gather(long_speech(), stop_after_delay())


async def test_speak_empty_text():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("speak_text", {"text": ""})
        struct_content = result.structured_content
        print(f"speak_text (empty) result:")
        print(f"  Success: {struct_content.get('success')}")
        print(f"  Message: {struct_content.get('message')}")


async def test_all_speaker_tools():
    print("=" * 60)
    print("TEST: list tools")
    print("=" * 60)
    await test_list_tools()

    print("\n" + "=" * 60)
    print("TEST: speak_text")
    print("=" * 60)
    await test_speak_text()

    print("\n" + "=" * 60)
    print("TEST: speak_text (empty text)")
    print("=" * 60)
    await test_speak_empty_text()

    print("\n" + "=" * 60)
    print("TEST: recorded_audio_speak (bark)")
    print("=" * 60)
    await test_recorded_audio_speak_not_found()

    print("\n" + "=" * 60)
    print("TEST: recorded_audio_speak (greeting)")
    print("=" * 60)
    await test_recorded_audio_speak("bark")

    print("\n" + "=" * 60)
    print("TEST: speak_text with interrupt")
    print("=" * 60)
    await test_speak_text_with_interrupt()

    # print("\n" + "=" * 60)
    # print("TEST: stop_speaking")
    # print("=" * 60)
    # await test_stop_speaking()


if __name__ == "__main__":
    asyncio.run(test_all_speaker_tools())
