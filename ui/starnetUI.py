# -*- coding: utf-8 -*-
import json
import sys
from time import sleep

import requests
import test_by_net
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMainWindow
from util import *
from camera import *
from test_only_camera import start_camera, w_quit
import player

from concurrent.futures import ThreadPoolExecutor

theard_pool = ThreadPoolExecutor(max_workers=4)
window = None
url = "http://192.168.50.205:5000/"


# url = "http://10.10.3.2:5000/"


class QTypeSignal(QObject):
    sendMsg = pyqtSignal(str)
    sendMsg2 = pyqtSignal(str)
    sendMsg3 = pyqtSignal(str)

    def __init__(self, ):
        super(QTypeSignal, self).__init__()

    def sendInfo(self, msg):
        self.sendMsg.emit(msg)

    def sendSecond(self, msg):
        self.sendMsg2.emit(msg)

    def sendLog(self, msg):
        self.sendMsg3.emit(msg)


cacheInfoSignal = QTypeSignal()
secondSignal = QTypeSignal()


# 0 海康 1 普通摄像头  该方法应在异步环境调用
def showMovie(type, start, lasting):
    import subprocess
    # if type == 0:
    # w_start()
    # sleep(int(start) / 10)
    # theard_pool.submit(start_camera, "192.168.50.25" + str(type))
    # sleep((int(lasting) / 10))
    # w_quit()
    # elif type == 1:
    #     sw = switch()
    #     if start > 40:
    #         start -= 40
    #     sleep(int(start) / 10)
    #     theard_pool.submit(video_demo, sw)
    #     sleep((int(lasting) / 10))
    #     sw.open = False

    def run(ip, timeout):
        subprocess.check_output("python ../test_by_net2.py " + ip + " 1 " + str(timeout) + " False c-1",
                                shell=True).decode(
            'utf-8')

    sleep(int(start) / 20)
    theard_pool.submit(run, "192.168.50.25" + str(type), int(int(lasting) / 20))


sw_tik = switch()


def tik():
    global sw_tik
    t = 0
    while sw_tik.open:
        sleep(1)
        t += 1
        if t < 10:
            secondSignal.sendSecond("连通时间：00:0" + str(t))
        else:
            secondSignal.sendSecond("连通时间：00:" + str(t))
    for i in range(1):
        sleep(1)
        t += 1
        if t < 10:
            secondSignal.sendSecond("连通时间：00:0" + str(t))
        else:
            secondSignal.sendSecond("连通时间：00:" + str(t))


# 该方法应在异步环境调用
def showVideo(u, start, lasting):
    if start == 0:
        start += 10
    sleep(int(start) / 10 - 1)
    # requests.post(url + "play_video", data={"url": u})
    play = player.Player()
    play.play(u)
    sleep((int(lasting) / 10))
    play.stop()
    # requests.post(url + "stop_video")


def refreshCacheInfo():
    global window

    def get_cache_info():
        while True:
            sleep(1)
            res = requests.post(url + "get_cache")
            result = json.loads(res.text)
            info_str = ''
            for obj in result:
                info_str += "节点名: " + obj.get("name") + "\n"
                info_str += "节点cache清单: " + obj.get("cache") + "\n"
            cacheInfoSignal.sendInfo(info_str)

    theard_pool.submit(get_cache_info)


def deleteSys():
    log("开始清除环境")
    log(requests.post(url + "remove_sys").text)


def deleteVideo():
    log("开始清除任务")
    log(requests.post(url + "remove_video").text)


# from myVlc.play import Player
# time.sleep(int(start) / 10)
# player = Player()
# player.play(url)
# time.sleep((int(end) - int(start)) / 10)
# player.stop()


def observation(lat, lon, dur):
    log("开始协同观测")
    res = requests.post(url=url + "time_v", data={"lat": lat, "lng": lon, "dur": dur})
    log(res.text)
    result = json.loads(res.text)
    i = 0
    for obj in result:
        theard_pool.submit(showMovie, i % 3, obj.get("start") * 60, obj.get("lasting") * 60)
        i += 1

    # import _thread
    # from time_varying.TimeVarying import getResult
    # play_queue = getResult(lat, lon, dur)
    # log(str(play_queue))
    # for p in play_queue:
    #     _thread.start_new_thread(showMovie, (p.get("url"), p.get("start"), p.get('end')))


def countMove():
    # 和k8s同网段会导致pod内部无法向外部路由，待处理，先写死
    import subprocess
    requests.post("http://192.168.50.205:5000/count_move")
    log("基于卫星拓扑\n选择节点d02迁移摄像头250图像识别任务\n选择节点d03迁移摄像头251图像识别任务\n选择节点d05迁移摄像头252图像识别任务\n")

    def run(ip, position):
        subprocess.check_output("python ../test_by_net2.py " + ip + " " + str(position) + " -1 True c" + str(position),
                                shell=True).decode('utf-8')

    theard_pool.submit(run, "192.168.50.250", 0)
    theard_pool.submit(run, "192.168.50.251", 1)
    theard_pool.submit(run, "192.168.50.252", 2)


def cache():
    def run(t):
        if t == 0:
            t_url = requests.post(url=url + "cdn_show", data={"host": "cache"}).text
            player.Player().play(t_url)
        else:
            t_url = requests.post(url=url + "cdn_show", data={"host": "no_cache"}).text
            player.Player().play(t_url)

    log("推送边缘节点流媒体服务")
    theard_pool.submit(run, 0)
    log("推送中心节点流媒体服务")
    theard_pool.submit(run, 1)


def trace():
    import trace_help
    theard_pool.submit(trace_help.TraceManager().start)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 1000)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        # self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        # self.pushButton.setGeometry(QtCore.QRect(30, 20, 89, 25))
        # self.pushButton.setObjectName("pushButton")
        self.pushButton_2 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_2.setGeometry(QtCore.QRect(550, 40, 89, 25))
        self.pushButton_2.setObjectName("pushButton_2")

        self.pushButton_5 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_5.setGeometry(QtCore.QRect(660, 40, 89, 25))
        self.pushButton_5.setObjectName("pushButton_5")

        self.pushButton_6 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_6.setGeometry(QtCore.QRect(550, 10, 89, 25))
        self.pushButton_6.setObjectName("pushButton_6")

        self.pushButton_7 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_7.setGeometry(QtCore.QRect(660, 10, 89, 25))
        self.pushButton_7.setObjectName("pushButton_7")

        self.pushButton_8 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_8.setGeometry(QtCore.QRect(25, 20, 89, 25))
        self.pushButton_8.setObjectName("pushButton_7")

        self.textBrowser = QtWidgets.QTextBrowser(self.centralwidget)
        self.textBrowser.setGeometry(QtCore.QRect(30, 90, 751, 461))
        self.textBrowser.setObjectName("textBrowser")

        self.textBrowser2 = QtWidgets.QTextBrowser(self.centralwidget)
        self.textBrowser2.setGeometry(QtCore.QRect(30, 600, 751, 300))
        self.textBrowser2.setObjectName("textBrowser2")

        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(40, 60, 70, 17))
        self.label.setTextFormat(QtCore.Qt.AutoText)
        self.label.setObjectName("label")

        self.label2 = QtWidgets.QLabel(self.centralwidget)
        self.label2.setGeometry(QtCore.QRect(40, 570, 70, 17))
        self.label2.setTextFormat(QtCore.Qt.AutoText)
        self.label2.setObjectName("label2")

        self.pushButton_3 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_3.setGeometry(QtCore.QRect(140, 20, 89, 25))
        self.pushButton_3.setObjectName("pushButton_3")

        self.pushButton_4 = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton_4.setGeometry(QtCore.QRect(250, 20, 89, 25))
        self.pushButton_4.setObjectName("pushButton_4")

        self.textEdit = QtWidgets.QTextEdit(self.centralwidget)
        self.textEdit.setGeometry(QtCore.QRect(470, 0, 50, 31))
        self.textEdit.setObjectName("textEdit")
        self.label_2 = QtWidgets.QLabel(self.centralwidget)
        self.label_2.setGeometry(QtCore.QRect(400, 10, 67, 17))
        self.label_2.setObjectName("label_2")
        self.label_3 = QtWidgets.QLabel(self.centralwidget)
        self.label_3.setGeometry(QtCore.QRect(400, 40, 67, 17))
        self.label_3.setObjectName("label_3")
        self.textEdit_2 = QtWidgets.QTextEdit(self.centralwidget)
        self.textEdit_2.setGeometry(QtCore.QRect(470, 30, 50, 31))
        self.textEdit_2.setObjectName("textEdit_2")
        self.textEdit_3 = QtWidgets.QTextEdit(self.centralwidget)
        self.textEdit_3.setGeometry(QtCore.QRect(470, 60, 50, 31))
        self.textEdit_3.setObjectName("textEdit_3")
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setGeometry(QtCore.QRect(400, 70, 67, 17))
        self.label_4.setObjectName("label_4")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 22))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "StarNet"))
        # self.pushButton.setText(_translate("MainWindow", "任务迁移"))
        self.pushButton_2.setText(_translate("MainWindow", "协同观测"))
        self.pushButton_3.setText(_translate("MainWindow", "清除任务"))
        self.pushButton_4.setText(_translate("MainWindow", "清除环境"))
        self.pushButton_5.setText(_translate("MainWindow", "卫星CDN"))
        self.pushButton_6.setText(_translate("MainWindow", "缓存效果"))
        self.pushButton_7.setText(_translate("MainWindow", "计算迁移"))
        self.pushButton_8.setText(_translate("MainWindow", "物体追踪"))
        self.textBrowser.setHtml(_translate("MainWindow",
                                            "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
                                            "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
                                            "p, li { white-space: pre-wrap; }\n"
                                            "</style></head><body style=\" font-family:\'Ubuntu\'; font-size:11pt; font-weight:400; font-style:normal;\">\n"
                                            "<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>"))
        self.textBrowser2.setHtml(_translate("MainWindow",
                                             "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
                                             "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
                                             "p, li { white-space: pre-wrap; }\n"
                                             "</style></head><body style=\" font-family:\'Ubuntu\'; font-size:11pt; font-weight:400; font-style:normal;\">\n"
                                             "<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>"))
        self.label.setText(_translate("MainWindow", "日志信息"))
        self.label2.setText(_translate("MainWindow", "缓存信息"))
        self.label_2.setText(_translate("MainWindow", "用户纬度"))
        self.label_3.setText(_translate("MainWindow", "用户经度"))
        self.label_4.setText(_translate("MainWindow", "服务时长"))


def cdn(lat, lon, dur):
    # secondSignal.sendSecond("连通时间：00:00")
    # sw_tik.open = True
    # theard_pool.submit(tik)
    res = requests.post(url=url + "cdn", data={"lat": lat, "lng": lon, "dur": dur, "name": "mv.mp4"})
    result = json.loads(res.text)
    print(result)
    # secondSignal.sendLog(res.text)
    # sw_tik.open = False
    for obj in result:
        theard_pool.submit(showVideo, obj.get("url"), obj.get("start") * 60, obj.get("lasting") * 60)
    for obj in result:
        if obj.get("url").find("192.168.50.13") != -1:
            obj.update({"url": "d02"})
        elif obj.get("url").find("192.168.50.192") != -1:
            obj.update({"url": "d03"})
        else:
            obj.update({"url": "d05"})
    log(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # self.ui.pushButton.clicked.connect(lambda: self.onClick_Button())
        self.ui.pushButton_2.clicked.connect(lambda: self.onClick_Button())
        self.ui.pushButton_3.clicked.connect(lambda: self.onClick_Button())
        self.ui.pushButton_4.clicked.connect(lambda: self.onClick_Button())
        self.ui.pushButton_5.clicked.connect(lambda: self.onClick_Button())
        self.ui.pushButton_6.clicked.connect(lambda: self.onClick_Button())
        self.ui.pushButton_7.clicked.connect(lambda: self.onClick_Button())
        self.ui.pushButton_8.clicked.connect(lambda: self.onClick_Button())
        bindScreen(self)
        cacheInfoSignal.sendMsg.connect(self.cacheInfoNotify)
        secondSignal.sendMsg2.connect(self.secondNotify)
        secondSignal.sendMsg3.connect(self.logNotify2)

    def onClick_Button(self):
        sender = self.sender()
        # if sender == self.ui.pushButton:
        if False:
            # yolo()
            pass
        # CDN
        elif sender == self.ui.pushButton_5:
            # theard_pool.submit(cdn, self.ui.textEdit.toPlainText(),
            #                    self.ui.textEdit_2.toPlainText(),
            #                    self.ui.textEdit_3.toPlainText())
            cdn(self.ui.textEdit.toPlainText(),
                self.ui.textEdit_2.toPlainText(),
                self.ui.textEdit_3.toPlainText())
        # 协同观测
        elif sender == self.ui.pushButton_2:
            observation(self.ui.textEdit.toPlainText(),
                        self.ui.textEdit_2.toPlainText(),
                        self.ui.textEdit_3.toPlainText())
        elif sender == self.ui.pushButton_3:
            deleteVideo()
        elif sender == self.ui.pushButton_4:
            deleteSys()
        elif sender == self.ui.pushButton_7:
            countMove()
        elif sender == self.ui.pushButton_6:
            cache()
        elif sender == self.ui.pushButton_8:
            trace()

    def logNotify(self):
        self.ui.textBrowser.setText(getLog())
        self.ui.textBrowser.moveCursor(self.ui.textBrowser.textCursor().End)

    def logNotify2(self, s: str):
        addLog(s)
        self.ui.textBrowser.setText(getLog())
        self.ui.textBrowser.moveCursor(self.ui.textBrowser.textCursor().End)

    def cacheInfoNotify(self, info: str):
        self.ui.textBrowser2.setText(info)

    def secondNotify(self, second: str):
        # self.ui.label3.setText(second)
        pass


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    refreshCacheInfo()
    sys.exit(app.exec_())
