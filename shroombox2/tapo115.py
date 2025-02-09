import asyncio
from tapo import ApiClient

async def main():
    # Create an ApiClient instance
    client = ApiClient("dannyolsen1980@gmail.com", "xerted-6wexwu-nyqraD")
    
    # Connect to the P115 plug
    device = await client.p115("192.168.8.158")
    
    # Turn the plug on
    await device.on()
    
    # Wait for a few seconds
    await asyncio.sleep(5)
    
    # Turn the plug off
    await device.off()
    
    # Get device info
    device_info = await device.get_device_info()
    print(device_info)
    
    # Get energy usage (P115 specific feature)
    energy_usage = await device.get_energy_usage()
    print(energy_usage)

asyncio.run(main())
