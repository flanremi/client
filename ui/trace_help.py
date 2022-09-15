# coding=utf-8
import json
import time
from concurrent.futures import ThreadPoolExecutor
import subprocess

import requests


# 物体追踪辅助类，该类下耗时操作最好异步进行，如start函数
class TraceManager:
    def __init__(self) -> None:
        super().__init__()
        self.tp = ThreadPoolExecutor(max_workers=4)
        # 获取系统平台
        self.position = [[], [], []]
        self.i_pos = [[], [], []]
        self.focus = -1
        self.turn = 0
        self.can_turn = 0
        self.on = True
        # self.init()

    def init(self):
        def req(pos):
            res = requests.post("http://192.168.50.205:5000/yolo_get", data={"camera": "c" + str(pos)})
            self.position[pos] = json.loads(res.text)
            if (len(self.position[pos]) > 0 and len(self.i_pos[pos]) == 0) or self.focus != pos:
                self.i_pos[pos] = self.position[pos]

        def run():
            while self.on:
                time.sleep(0.5)
                self.tp.submit(req, 0)
                self.tp.submit(req, 1)
                self.tp.submit(req, 2)

        self.tp.submit(run)

    def start(self):
        def start_screen(i):
            subprocess.check_output(
                "python ../test_by_net2.py " +
                "192.168.50.25" + str(i) + " " + str(1) + " -1 True c" + str(i),
                shell=True).decode("UTF-8")
        i = 0

        self.tp.submit(start_screen, 0)
        # requests.post("http://192.168.50.205:5000/count_move_2", data={"pos": "0"})
        while True:
            time.sleep(1)
            res = requests.post("http://192.168.50.205:5000/yolo_get", data={"camera": "c" + str(0)})
            result = json.loads(res.text)
            i += 1
            if len(result) > 0 and 150 <= int(result[0][0]) <= 1500:
                break
            subprocess.check_output(
                "python ../t_CameraManager.py " + "192.168.50.25" + str(0) + " " + str(i),
                shell=True).decode("UTF-8")
        time.sleep(15)
        subprocess.check_output(
            "python ../t_CameraManager.py " + "192.168.50.25" + str(0) + " " + str((i + 5) % 21),
            shell=True).decode("UTF-8")
        time.sleep(3)

        self.tp.submit(start_screen, 1)
        subprocess.check_output(
            "python ../t_CameraManager.py " + "192.168.50.25" + str(1) + " " + str(10),
            shell=True).decode("UTF-8")
        time.sleep(14)

        subprocess.check_output(
            "python ../t_CameraManager.py " + "192.168.50.25" + str(1) + " " + str(15),
            shell=True).decode("UTF-8")
        time.sleep(3)

        self.tp.submit(start_screen, 2)
        subprocess.check_output(
            "python ../t_CameraManager.py " + "192.168.50.25" + str(2) + " " + str(8),
            shell=True).decode("UTF-8")
        time.sleep(14)

        subprocess.check_output(
            "python ../t_CameraManager.py " + "192.168.50.25" + str(2) + " " + str(14),
            shell=True).decode("UTF-8")
        time.sleep(3)

# subprocess.check_output(
#     "python ../t_CameraManager.py " + "\"192.168.50.25" + str(0) + "\" " + "\"" + "stop" + "\"",
#     shell=True).decode("UTF-8")
