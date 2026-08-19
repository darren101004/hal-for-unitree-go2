import asyncio
import base64
import time
import httpx

import cv2
import numpy as np
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from pickle import bytes_types

BASE_URL = "http://localhost:8001/depth_camera/mcp"

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

async def test_capture_depth_camera_frame():
    transport = StreamableHttpTransport(url=BASE_URL)
    async with Client(transport=transport) as client:
        processed_times = []
        for i in range(3):
            assert client.is_connected()
            start_time = time.time()
            result = await client.call_tool("capture_image", {"need_description": True})
            end_time = time.time()
            time_taken = end_time - start_time
            struct_content = result.structured_content
            # print(struct_content)
            print(type(struct_content))
            print("Success: ", struct_content.get("success"))
            print("Message: ", struct_content.get("message"))
            print("Code: ", struct_content.get("code"))
            extra_data = struct_content.get("extra_data")
            if extra_data:
                objects = extra_data["data"]["objects"]
                print("Natural language description: ", extra_data["data"]["natural_language_description"])
                print("Objects: ", objects)
            else:
                print("No extra data received!")
            
            base64_data = struct_content.get("data")
            if base64_data:
                img_bytes = base64.b64decode(base64_data)
                filename = "captured_depth_camera.jpg"

                with open(filename, "wb") as f:
                    f.write(img_bytes)

                cv2_img = cv2.imread(filename, cv2.IMREAD_COLOR)
                if cv2_img is not None:
                    for obj in objects:
                        import random
                        xyxyn = obj.get("xyxyn")
                        # Convert xyxyn (normalized coordinates) to xyxy (pixel coordinates) based on actual width/height
                        if xyxyn is not None and len(xyxyn) == 4:
                            x1n, y1n, x2n, y2n = xyxyn
                            h, w, *_ = cv2_img.shape
                            x1 = int(x1n * w)
                            x2 = int(x2n * w)
                            y1 = int(y1n * h)
                            y2 = int(y2n * h)
                        name = obj.get("name", "")
                        color = (
                            random.randint(0, 255),
                            random.randint(0, 255),
                            random.randint(0, 255)
                        )
                        thickness = 2
                        # Draw rectangle
                        cv2.rectangle(cv2_img, (x1, y1), (x2, y2), color, thickness)
                        # Draw label (name)
                        label = str(name)
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 0.7
                        font_thickness = 2
                        text_size, _ = cv2.getTextSize(label, font, font_scale, font_thickness)
                        text_w, text_h = text_size
                        text_bg_color = color
                        text_color = (0, 0, 0)
                        # Draw text background
                        cv2.rectangle(cv2_img, (x1, y1 - text_h - 6), (x1 + text_w, y1), text_bg_color, -1)
                        cv2.putText(cv2_img, label, (x1, y1 - 4), font, font_scale, text_color, font_thickness, cv2.LINE_AA)
                    h, w, *_ = cv2_img.shape
                    center = (w // 2, h // 2)
                    cv2.circle(cv2_img, center, 8, (0, 0, 255), thickness=-1)
                    cv2.imwrite(filename, cv2_img)
                else:
                    print("Warning: Cannot decode image by cv2 after saving.")
                print(f"Image saved as: {filename}")
            else:
                print("No image data received!")
            
            print(f"[{i}].Time taken: {time_taken} seconds")
            processed_times.append(time_taken)
        print(f"Processed times: {processed_times}")
        print(f"Average time taken: {sum(processed_times) / len(processed_times)} seconds")

async def test_all_cmp_tools():
    await test_list_tools()
    await test_capture_depth_camera_frame()
    
if __name__ == "__main__":
    asyncio.run(test_all_cmp_tools())