import requests
#
# res = requests.post("http://192.168.139.137:4995/query")
# print(res.text)
#
# res = requests.post("http://192.168.139.44:5000/cdn",
#                     data={"name": "cheat.mp4", "lat": 100, "lng": 100, "dur": 5})

res = requests.post("http://192.168.139.44:5000/get_cache")
# res = requests.post("http://192.168.139.44:5000/remove_video")
#
#
print(res.text)