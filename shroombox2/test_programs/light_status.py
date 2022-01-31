light_status = {
    "status" : "",
    "color" : "",
    "rgb" : []
}

def setlight():
    light_status["rgb"] = [0,255,255]

light_status["rgb"] = [255,255,255]

print(light_status["rgb"])

light_status.update(something="else")

print(light_status)

setlight()
print(light_status)