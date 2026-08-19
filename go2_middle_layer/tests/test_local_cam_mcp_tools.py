import asyncio
import base64
from pickle import bytes_types

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

BASE_URL = "http://localhost:8001/local_camera/mcp"

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

async def test_capture_image():
    client = Client(
        transport=StreamableHttpTransport(url=BASE_URL)
    )
    async with client:
        assert client.is_connected()
        result = await client.call_tool("capture_image", {})
        struct_content = result.structured_content
        # print(struct_content)
        print(type(struct_content))
        print("Success: ", struct_content.get("success", "N/A"))
        print("Message: ", struct_content.get("message", "N/A"))
        print("Code: ", struct_content.get("code", "N/A"))
        
        base64_data = struct_content.get("data", None)
        if base64_data:
            img_bytes = base64.b64decode(base64_data)
            filename = "captured_image_from_local_cam_mcp_tools.jpg"
            with open(filename, "wb") as f:
                f.write(img_bytes)
            print(f"Image saved as: {filename}")
        else:
            print("No image data received!")
        


async def test_all_cmp_tools():
    await test_list_tools()
    await test_capture_image()
    
if __name__ == "__main__":
    asyncio.run(test_all_cmp_tools())