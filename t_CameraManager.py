import ctypes
import json
import os
import platform
import sys
import time
import tkinter
from tkinter import *

import requests

from HCNetSDK import *
from PlayCtrl import *
from time import sleep
from concurrent.futures import ThreadPoolExecutor


# 21 21 18 各摄像头定点个数
# 专门用来方便subprocess调用的摄像头控制类
class CameraManager:

    def __init__(self, ip: str, username: str = "admin", password: str = "osm123onap") -> None:
        super().__init__()
        # 登录的设备信息
        self.reset_num = [21, 21, 18]
        self.DEV_IP = create_string_buffer(bytes(ip, "utf-8"))
        self.DEV_PORT = 8000
        self.DEV_USER_NAME = create_string_buffer(bytes(username, "utf-8"))
        self.DEV_PASSWORD = create_string_buffer(bytes(password, "utf-8"))
        self.theard_pool = ThreadPoolExecutor(max_workers=4)
        self.yolo_stop = False

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
        self.lUserId = -1
        self.cv = None
        self.device_info = None

    def RealDataCallBack_V30(self, lPlayHandle, dwDataType, pBuffer, dwBufSize, pUser):
        # 码流回调函数
        pass

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

    def InputData(self, fileMp4):
        while True:
            pFileData = fileMp4.read(4096)
            if pFileData is None:
                break

            if not self.Playctrldll.PlayM4_InputData(self.PlayCtrl_Port, pFileData, len(pFileData)):
                break

    def init(self):
        os.chdir(
            'E:\\java_project\hikvision\\CH-HCNetSDKV6.1.9.4_build20220412_win64\\Demo示例\\5- Python开发示例\\1-预览取流解码Demo')

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
        self.device_info = device_info

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


    def up(self):
        self.in_control = 1
        # 开始云台控制
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_UP, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')

    def down(self):
        self.in_control = 1
        # 开始云台控制
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_DOWN, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')

    def left(self):
        self.in_control = 1
        # 开始云台控制
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')

    def right(self):
        self.in_control = 1
        # 开始云台控制
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % self.Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')

    def stop(self):
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 1)
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 1)
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_DOWN, 1)
        lRet = self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, TILT_UP, 1)

    def preset(self, pos):
        print(self.Objdll.NET_DVR_PTZPreset(self.lRealPlayHandle, 39, pos))
        print('error code is: %d' % self.Objdll.NET_DVR_GetLastError())

    def close(self):
        # 关闭预览
        self.Objdll.NET_DVR_StopRealPlay(self.lRealPlayHandle)
        # self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_RIGHT, 1)
        # self.Objdll.NET_DVR_PTZControl(self.lRealPlayHandle, PAN_LEFT, 1)

        # 停止解码，释放播放库资源
        if self.PlayCtrl_Port.value > -1:
            self.Playctrldll.PlayM4_Stop(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_CloseStream(self.PlayCtrl_Port)
            self.Playctrldll.PlayM4_FreePort(self.PlayCtrl_Port)
            self.PlayCtrl_Port = c_long(-1)

        # 登出设备
        self.Objdll.NET_DVR_Logout(self.lUserId)

        # 释放资源
        self.Objdll.NET_DVR_Cleanup()


# cm = CameraManager(ip="192.168.50.250")
cm = CameraManager(ip=sys.argv[1])
cm.init()
cm.preset(int(sys.argv[2]) + 1)
# todo 处理资源释放问题
# #
# if sys.argv[2] == "l":
#     cm.left()
# elif sys.argv[2] == "r":
#     cm.right()
# elif sys.argv[2] == "stop":
#     cm.stop()
cm.close()
