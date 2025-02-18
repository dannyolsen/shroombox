import asyncio
from tapo import ApiClient
from time import sleep

client = ApiClient("dannyolsen1980@gmail.com", "xerted-6wexwu-nyqraD")
humidifier = asyncio.run(client.p115("192.168.8.158"))
heater = asyncio.run(client.p115("192.168.8.158"))
device3 = asyncio.run(client.p115("192.168.8.158"))

"""asyncio.run(humidifier.on())
sleep(5)
asyncio.run(humidifier.off())"""

