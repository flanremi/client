# coding=utf-8
import json
import os
import platform
import sys
import tkinter
from tkinter import *

import requests

from HCNetSDK import *
from PlayCtrl import *
from time import sleep
from concurrent.futures import ThreadPoolExecutor


# 方便shell调用的类，不要直接调用
class Box:

    def __init__(self, l: int, t: int, r: int, b: int, color: str) -> None:
        super().__init__()
        self.left = l
        self.right = r
        self.bottom = b
        self.top = t
        self.color = color
        self.stop = False
        self.canvas = None
        self.tp = None
        self.line1 = None
        self.line2 = None
        self.line3 = None
        self.line4 = None

    def init(self, canvas: tkinter.Canvas, tp: ThreadPoolExecutor):
        self.canvas = canvas
        self.tp = tp
        self.line1 = self.canvas.create_line(self.left, self.top, self.right, self.top, fill=self.color, width=3)
        self.line2 = self.canvas.create_line(self.right, self.top, self.right, self.bottom, fill=self.color,
                                             width=3)
        self.line3 = self.canvas.create_line(self.right, self.bottom, self.left, self.bottom, fill=self.color,
                                             width=3)
        self.line4 = self.canvas.create_line(self.left, self.bottom, self.left, self.top, fill=self.color, width=3)

    def draw(self, yolo_stop):
        def tmp():
            while not yolo_stop and not self.stop:
                sleep(0.5)
                self.canvas.tag_raise(self.line1)
                self.canvas.tag_raise(self.line2)
                self.canvas.tag_raise(self.line3)
                self.canvas.tag_raise(self.line4)

        self.tp.submit(tmp)

    def destroy(self):
        # self.stop = True
        self.canvas.delete(self.line1)
        self.canvas.delete(self.line2)
        self.canvas.delete(self.line3)
        self.canvas.delete(self.line4)


class BoxManager:
    def __init__(self, canvas: tkinter.Canvas, tp: ThreadPoolExecutor):
        self.box_list: list = []
        self.box_trace = None
        self.canvas = canvas
        # 0 left 1 right
        self.turn = -1
        # 缓存上一次改变的位置
        self.tmp_turn = -1
        self.tp = tp

    def refresh(self, boxes: list, yolo_stop: bool):
        i, j = 0, 0
        tmp: list = []
        while i < len(boxes):
            box_new = boxes[i]
            add = True
            while j < len(self.box_list):
                box_old = self.box_list[j]
                if box_old.right == box_new.right and box_old.left == box_new.left and \
                        box_old.top == box_new.top and box_old.bottom == box_new.bottom:
                    add = False
                    break
                j += 1
            if add:
                box_new.init(self.canvas, self.tp)
                tmp.append(box_new)
                box_new.draw(yolo_stop)
            i += 1
        i, j = 0, 0
        while i < len(self.box_list):
            box_old = self.box_list[i]
            delete = True
            while j < len(boxes):
                box_new = boxes[j]
                if box_old.right == box_new.right and box_old.left == box_new.left and \
                        box_old.top == box_new.top and box_old.bottom == box_new.bottom:
                    delete = False
                    break
                j += 1
            if delete:
                self.box_list.remove(box_old)
                box_old.destroy()
                i -= 1
            i += 1
        self.box_list.extend(tmp)

    def trace(self, box: Box, yolo_stop: bool):
        if not self.box_trace:
            self.box_trace = box
            self.box_trace.init(self.canvas, self.tp)
            self.box_trace.draw(yolo_stop)
            # 当目标出现在镜头中时，仅记录一次被识别到的位置，并以此判断往哪边转，同时因为第一次出现，所以方向自然要归-1
            if self.tmp_turn == -1:
                self.tmp_turn = self.box_trace.left
                self.turn = -1
            self.box_trace.destroy()
            return
        t = self.tmp_turn - box.left
        print(str(self.tmp_turn) + "   " + str(box.left))
        if self.tmp_turn != -1:
            if t > 100:
                self.turn = 0
                self.tmp_turn = -1
            elif t < -100:
                self.turn = 1
                self.tmp_turn = -1
        self.box_trace.destroy()
        self.box_trace = box
        self.box_trace.init(self.canvas, self.tp)
        self.box_trace.draw(yolo_stop)


class CameraManager:

    def __init__(self, ip: str, username: str = "admin", password: str = "osm123onap", position: int = 1,
                 timeout: int = -1, yolo_on: bool = True, bind_camera: str = "") -> None:
        super().__init__()
        # 登录的设备信息
        self.DEV_IP = create_string_buffer(bytes(ip, "utf-8"))
        self.DEV_PORT = 8000
        self.DEV_USER_NAME = create_string_buffer(bytes(username, "utf-8"))
        self.DEV_PASSWORD = create_string_buffer(bytes(password, "utf-8"))
        self.theard_pool = ThreadPoolExecutor(max_workers=4)
        self.yolo_stop = False
        self.position = position
        self.timeout = timeout
        self.yolo_on = yolo_on
        self.bind_camera = bind_camera

        self.WINDOWS_FLAG = True
        self.win = None  # 预览窗口
        self.funcRealDataCallBack_V30 = None  # 实时预览回调函数，需要定义为全局的
        self.PlayCtrl_Port = c_long(-1)  # 播放句柄
        self.Playctrldll = None  # 播放库
        self.FuncDecCB = None  # 播放库解码回调函数，需要定义为全局的

        self.box_manager = None  # yolo绘制方框插件

        self.width_rate = 512 / 1920
        self.height_rate = 384 / 1080

        self.lRealPlayHandle = -1
        # 是否在自动转向
        self.is_turn = -1
        # 是否被按钮控制
        self.in_control = -1

        self.Objdll = None

        self.cv = None
        self.lUserId = -1

    # 获取当前系统环境
    def GetPlatform(self):
        sysstr = platform.system()
        print('' + sysstr)
        if sysstr != "Windows":
            self.WINDOWS_FLAG = False

    # 设置SDK初始化依赖库路径
    def SetSDKInitCfg(self):
        # 设置HCNetSDKCom组件库和SSL库加载路径
        # print(os.getcwd())
        if self.WINDOWS_FLAG:
            strPath = os.getcwd().encode('gbk')
            sdk_ComPath = NET_DVR_LOCAL_SDK_PATH()
            sdk_ComPath.sPath = strPath
            self.Objdll.NET_DVR_SetSDKInitCfg(2, byref(sdk_ComPath))
            self.Objdll.NET_DVR_SetSDKInitCfg(3, create_string_buffer(strPath + b'\libcrypto-1_1-x64.dll'))
            self.Objdll.NET_DVR_SetSDKInitCfg(4, create_string_buffer(strPath + b'\libssl-1_1-x64.dll'))
        else:
            strPath = os.getcwd().encode('utf-8')
            sdk_ComPath = NET_DVR_LOCAL_SDK_PATH()
            sdk_ComPath.sPath = strPath
            self.Objdll.NET_DVR_SetSDKInitCfg(2, byref(sdk_ComPath))
            self.Objdll.NET_DVR_SetSDKInitCfg(3, create_string_buffer(strPath + b'/libcrypto.so.1.1'))
            self.Objdll.NET_DVR_SetSDKInitCfg(4, create_string_buffer(strPath + b'/libssl.so.1.1'))

    def LoginDev(self):
        # 登录注册设备
        device_info = NET_DVR_DEVICEINFO_V30()
        lUserId = self.Objdll.NET_DVR_Login_V30(self.DEV_IP, self.DEV_PORT, self.DEV_USER_NAME, self.DEV_PASSWORD,
                                                byref(device_info))
        return lUserId, device_info

    def DecCBFun(self, nPort, pBuf, nSize, pFrameInfo, nUser, nReserved2):
        # 解码回调函数
        if pFrameInfo.contents.nType == 3:
            # 解码返回视频YUV数据，将YUV数据转成jpg图片保存到本地
            # 如果有耗时处理，需要将解码数据拷贝到回调函数外面的其他线程里面处理，避免阻塞回调导致解码丢帧
            # sFileName = ('../../pic/test_stamp[%d].jpg' % pFrameInfo.contents.nStamp)
            sFileName = 'yolov5/data/images/tmp.jpg'
            nWidth = pFrameInfo.contents.nWidth
            nHeight = pFrameInfo.contents.nHeight
            nType = pFrameInfo.contents.nType
            dwFrameNum = pFrameInfo.contents.dwFrameNum
            nStamp = pFrameInfo.contents.nStamp
            # print(nWidth, nHeight, nType, dwFrameNum, nStamp, sFileName)
            # lRet = self.Playctrldll.PlayM4_ConvertToJpegFile(pBuf, nSize, nWidth, nHeight, nType,
            #                                                  c_char_p(sFileName.encode()))
            #
            # if lRet == 0:
            #     print('PlayM4_ConvertToJpegFile fail, error code is:', self.Playctrldll.PlayM4_GetLastError(nPort))
            # else:
            #     # print('PlayM4_ConvertToJpegFile success')
            #     pass

    def RealDataCallBack_V30(self, lPlayHandle, dwDataType, pBuffer, dwBufSize, pUser):
        # 码流回调函数
        if dwDataType == NET_DVR_SYSHEAD:
            # 设置流播放模式
            self.Playctrldll.PlayM4_SetStreamOpenMode(self.PlayCtrl_Port, 0)
            # 打开码流，送入40字节系统头数据
            if self.Playctrldll.PlayM4_OpenStream(self.PlayCtrl_Port, pBuffer, dwBufSize, 1024 * 1024):
                # 设置解码回调，可以返回解码后YUV视频数据
                self.FuncDecCB = DECCBFUNWIN(self.DecCBFun)
                self.Playctrldll.PlayM4_SetDecCallBackExMend(self.PlayCtrl_Port, self.FuncDecCB, None, 0, None)
                # 开始解码播放
                if self.Playctrldll.PlayM4_Play(self.PlayCtrl_Port, self.cv.winfo_id()):
                    print(u'播放库播放成功')
                else:
                    print(u'播放库播放失败')
            else:
                print(u'播放库打开流失败')
        elif dwDataType == NET_DVR_STREAMDATA:
            self.Playctrldll.PlayM4_InputData(self.PlayCtrl_Port, pBuffer, dwBufSize)
        else:
            print(u'其他数据,长度:', dwBufSize)

    def OpenPreview(self, lUserId, callbackFun):
        '''
        打开预览
        '''
        preview_info = NET_DVR_PREVIEWINFO()
        preview_info.hPlayWnd = 0
        preview_info.lChannel = 1  # 通道号
        preview_info.dwStreamType = 0  # 主码流
        preview_info.dwLinkMode = 0  # TCP
        preview_info.bBlocked = 1  # 阻塞取流

        # 开始预览并且设置回调函数回调获取实时流数据
        self.lRealPlayHandle = self.Objdll.NET_DVR_RealPlay_V40(lUserId, byref(preview_info), callbackFun, None)

    def InputData(self, fileMp4):
        while True:
            pFileData = fileMp4.read(4096)
            if pFileData is None:
                break

            if not self.Playctrldll.PlayM4_InputData(self.PlayCtrl_Port, pFileData, len(pFileData)):
                break



    def display(self):
        os.chdir(
            'E:\\java_project\hikvision\\CH-HCNetSDKV6.1.9.4_build20220412_win64\\Demo示例\\5- Python开发示例\\1-预览取流解码Demo')
        # 创建窗口
        win = tkinter.Tk()
        # 固定窗口大小
        win.resizable(0, 0)
        win.overrideredirect(True)

        sw = win.winfo_screenwidth()
        # 得到屏幕宽度
        sh = win.winfo_screenheight()
        # 得到屏幕高度

        # 窗口宽高
        ww = 512
        wh = 384
        x = (sw - ww) / 2
        y = (sh - wh) / 2
        if self.position == 0:
            offset = x - ww - 10
        elif self.position == 1:
            offset = x
        else:
            offset = x + ww + 10
        win.geometry("%dx%d+%d+%d" % (ww, wh, offset, y))

        def left():
            # 开始云台控制
            self.in_control = 1
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 0)
            if lRet == 0:
                print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
            else:
                print('Start ptz control success')

        def right():
            self.in_control = 1
            # 开始云台控制
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 0)
            if lRet == 0:
                print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
            else:
                print('Start ptz control success')

        def up():
            self.in_control = 1
            # 开始云台控制
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_UP, 0)
            if lRet == 0:
                print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
            else:
                print('Start ptz control success')

        def down():
            self.in_control = 1
            # 开始云台控制
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_DOWN, 0)
            if lRet == 0:
                print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
            else:
                print('Start ptz control success')

        def stop():
            self.in_control = -1
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_UP, 1)
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_DOWN, 1)
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 1)
            lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 1)

        def quit():
            win.quit()
            self.yolo_stop = True

        # 记录开启时间
        def time2stop():
            def run():
                while self.timeout >= 0:
                    sleep(1)
                    self.timeout -= 1
                stop()
            self.theard_pool.submit(run)

        if self.timeout >= 0:
            time2stop()

        # 创建退出按键
        b1 = Button(win, text='退出', command=quit)
        b1.place(x=20, y=1, anchor=N)
        b2 = Button(win, text='左转', command=left)
        b2.place(x=150, y=1, anchor=N)
        b3 = Button(win, text='右转', command=right)
        b3.place(x=200, y=1, anchor=N)
        b4 = Button(win, text='向上', command=up)
        b4.place(x=250, y=1, anchor=N)
        b5 = Button(win, text='向下', command=down)
        b5.place(x=300, y=1, anchor=N)
        b6 = Button(win, text='停止', command=stop)
        b6.place(x=350, y=1, anchor=N)

        # 创建一个Canvas，设置其背景色为白色
        self.cv = tkinter.Canvas(win, bg='white', width=ww, height=wh)
        self.cv.place(x=0, y=35)

        box_manager = BoxManager(self.cv, self.theard_pool)

        def yolo():

            def run():
                sleep(0.5)
                # 避免过敏
                times = 0
                while True:
                    try:
                        # self.Objdll.NET_DVR_PTZPreset(self.lRealPlayHandle, 39,21)
                        sleep(0.5)
                        if self.in_control == 1:
                            continue
                        results = json.loads(
                            requests.post(url="http://" + "192.168.50.205:5000" + "/yolo_get",
                                          data={"camera": self.bind_camera}).text)
                        boxes = []
                        print(results)
                        p = 0
                        for result in results:
                            if int(result[0]) < 200 or int(result[1]) < 100 or result[2] > 1600 or result[3] > 1000:
                                continue
                            if p <= result[4]:
                                boxes.append(Box(int(result[0] * self.width_rate), int(result[1] * self.height_rate),
                                                 int(result[2] * self.width_rate), int(result[3] * self.height_rate),
                                                 "#ff0000"))
                                p = result[4]
                        if len(boxes) > 0:
                            box_manager.trace(boxes[len(boxes) - 1], self.yolo_stop)
                            #
                            # box_manager.refresh(boxes, self.yolo_stop)
                            continue
                            self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 1)
                            self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 1)
                            # 画面中出现目标就应该停止转动
                            self.is_turn = -1
                            times = 0
                        else:
                            continue
                            print(box_manager.turn)
                            if box_manager.box_trace:
                                box_manager.box_trace.destroy()
                                box_manager.box_trace = None
                            # 具有转动方向且失去目标时间达到阈值，则寻找目标
                            if box_manager.turn != -1:
                                if box_manager.turn == 0:
                                    if self.is_turn == 1:
                                        self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 1)
                                        self.is_turn = -1
                                    elif self.is_turn == -1:
                                        self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 0)
                                        self.is_turn = 0
                                else:
                                    if self.is_turn == 0:
                                        self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 1)
                                        self.is_turn = -1
                                    elif self.is_turn == -1:
                                        self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 0)
                                        self.is_turn = 1
                            elif self.is_turn != -1:
                                self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 1)
                                self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 1)
                                self.is_turn = -1
                                pass
                    except:
                        pass

            self.theard_pool.submit(run)
        if self.yolo_on:
            yolo()

        # 获取系统平台
        self.GetPlatform()

        # 加载库,先加载依赖库
        if self.WINDOWS_FLAG:
            os.chdir(r'./lib/win')
            self.Objdll = ctypes.CDLL(r'./HCNetSDK.dll')  # 加载网络库
            self.Playctrldll = ctypes.CDLL(r'./PlayCtrl.dll')  # 加载播放库
        else:
            os.chdir(r'./lib/linux')
            self.Objdll = cdll.LoadLibrary(r'./libhcnetsdk.so')
            self.Playctrldll = cdll.LoadLibrary(r'./libPlayCtrl.so')

        self.SetSDKInitCfg()  # 设置组件库和SSL库加载路径

        # 初始化DLL
        self.Objdll.NET_DVR_Init()
        # 启用SDK写日志
        self.Objdll.NET_DVR_SetLogToFile(3, bytes('./SdkLog_Python/', encoding="utf-8"), False)

        # 获取一个播放句柄
        if not self.Playctrldll.PlayM4_GetPort(byref(self.PlayCtrl_Port)):
            print(u'获取播放库句柄失败')

        # 登录设备
        (lUserId, device_info) = self.LoginDev()
        if lUserId < 0:
            err = self.Objdll.NET_DVR_GetLastError()
            print('Login device fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
            # 释放资源
            self.Objdll.NET_DVR_Cleanup()
            exit()
        self.lUserId = lUserId
        dw_returned = ctypes.c_uint16(0)

        # 定义码流回调函数
        funcRealDataCallBack_V30 = REALDATACALLBACK(self.RealDataCallBack_V30)
        # 开启预览
        self.OpenPreview(lUserId, funcRealDataCallBack_V30)
        if self.lRealPlayHandle < 0:
            print('Open preview fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
            # 登出设备
            self.Objdll.NET_DVR_Logout(lUserId)
            # 释放资源
            self.Objdll.NET_DVR_Cleanup()
            exit()

        # show Windows
        win.mainloop()

        # 关闭预览
        self.Objdll.NET_DVR_StopRealPlay(self.lRealPlayHandle)
        self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 1)
        self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 1)

        # 停止解码，释放播放库资源
        if self.PlayCtrl_Port.value > -1:
            self.Playctrldll.PlayM4_Stop(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_CloseStream(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_FreePort(self.PlayCtrl_Port)
            self.PlayCtrl_Port = c_long(-1)

        # 登出设备
        self.Objdll.NET_DVR_Logout(lUserId)

        # 释放资源
        self.Objdll.NET_DVR_Cleanup()


CameraManager(ip=sys.argv[1], position=int(sys.argv[2]), timeout=int(sys.argv[3]), yolo_on=bool(sys.argv[4]),
              bind_camera=sys.argv[5]).display()
