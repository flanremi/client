# coding=utf-8

import os
import platform
import tkinter
from tkinter import *
from HCNetSDK import *
from PlayCtrl import *
from time import sleep
from concurrent.futures import ThreadPoolExecutor

# 登录的设备信息
DEV_IP = create_string_buffer(b'192.168.50.250')
DEV_PORT = 8000
DEV_USER_NAME = create_string_buffer(b'admin')
DEV_PASSWORD = create_string_buffer(b'osm123onap')
theard_pool = ThreadPoolExecutor(max_workers=4)
yolo_stop = False

WINDOWS_FLAG = True
win = None  # 预览窗口
funcRealDataCallBack_V30 = None  # 实时预览回调函数，需要定义为全局的
PlayCtrl_Port = c_long(-1)  # 播放句柄
Playctrldll = None  # 播放库
FuncDecCB = None  # 播放库解码回调函数，需要定义为全局的

box_manager = None  # yolo绘制方框插件

width_rate = 512 / 1920
height_rate = 384 / 1080

lRealPlayHandle = -1
# 是否在自动转向
is_turn = -1
# 是否被按钮控制
in_control = -1


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
        self.line2 = self.canvas.create_line(self.right, self.top, self.right, self.bottom, fill=self.color, width=3)
        self.line3 = self.canvas.create_line(self.right, self.bottom, self.left, self.bottom, fill=self.color, width=3)
        self.line4 = self.canvas.create_line(self.left, self.bottom, self.left, self.top, fill=self.color, width=3)

    def draw(self):
        def tmp():
            while not yolo_stop and not self.stop:
                sleep(0.5)
                self.canvas.tag_raise(self.line1)
                self.canvas.tag_raise(self.line2)
                self.canvas.tag_raise(self.line3)
                self.canvas.tag_raise(self.line4)

        self.tp.submit(tmp)

    def destroy(self):
        self.stop = True
        self.canvas.delete(self.line1)
        self.canvas.delete(self.line2)
        self.canvas.delete(self.line3)
        self.canvas.delete(self.line4)


class BoxManager:
    def __init__(self, canvas: tkinter.Canvas, tp: ThreadPoolExecutor):
        self.box_list: list[Box] = []
        self.box_trace = None
        self.canvas = canvas
        # 0 left 1 right
        self.turn = -1
        # 缓存上一次改变的位置
        self.tmp_turn = -1
        self.tp = tp

    def refresh(self, boxes: list[Box]):
        i, j = 0, 0
        tmp: list[Box] = []
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
                box_new.draw()
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

    def trace(self, box: Box):
        if not self.box_trace:
            self.box_trace = box
            self.box_trace.init(self.canvas, self.tp)
            self.box_trace.draw()
            # 当目标出现在镜头中时，仅记录一次被识别到的位置，并以此判断往哪边转，同时因为第一次出现，所以方向自然要归-1
            if self.tmp_turn == -1:
                self.tmp_turn = self.box_trace.left
                self.turn = -1
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
        self.box_trace.draw()


# 获取当前系统环境
def GetPlatform():
    sysstr = platform.system()
    print('' + sysstr)
    if sysstr != "Windows":
        global WINDOWS_FLAG
        WINDOWS_FLAG = False


# 设置SDK初始化依赖库路径
def SetSDKInitCfg():
    # 设置HCNetSDKCom组件库和SSL库加载路径
    # print(os.getcwd())
    if WINDOWS_FLAG:
        strPath = os.getcwd().encode('gbk')
        sdk_ComPath = NET_DVR_LOCAL_SDK_PATH()
        sdk_ComPath.sPath = strPath
        Objdll.NET_DVR_SetSDKInitCfg(2, byref(sdk_ComPath))
        Objdll.NET_DVR_SetSDKInitCfg(3, create_string_buffer(strPath + b'\libcrypto-1_1-x64.dll'))
        Objdll.NET_DVR_SetSDKInitCfg(4, create_string_buffer(strPath + b'\libssl-1_1-x64.dll'))
    else:
        strPath = os.getcwd().encode('utf-8')
        sdk_ComPath = NET_DVR_LOCAL_SDK_PATH()
        sdk_ComPath.sPath = strPath
        Objdll.NET_DVR_SetSDKInitCfg(2, byref(sdk_ComPath))
        Objdll.NET_DVR_SetSDKInitCfg(3, create_string_buffer(strPath + b'/libcrypto.so.1.1'))
        Objdll.NET_DVR_SetSDKInitCfg(4, create_string_buffer(strPath + b'/libssl.so.1.1'))


def LoginDev(Objdll):
    # 登录注册设备
    device_info = NET_DVR_DEVICEINFO_V30()
    lUserId = Objdll.NET_DVR_Login_V30(DEV_IP, DEV_PORT, DEV_USER_NAME, DEV_PASSWORD, byref(device_info))
    return (lUserId, device_info)


def DecCBFun(nPort, pBuf, nSize, pFrameInfo, nUser, nReserved2):
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
        lRet = Playctrldll.PlayM4_ConvertToJpegFile(pBuf, nSize, nWidth, nHeight, nType, c_char_p(sFileName.encode()))

        if lRet == 0:
            print('PlayM4_ConvertToJpegFile fail, error code is:', Playctrldll.PlayM4_GetLastError(nPort))
        else:
            # print('PlayM4_ConvertToJpegFile success')
            pass


def RealDataCallBack_V30(lPlayHandle, dwDataType, pBuffer, dwBufSize, pUser):
    # 码流回调函数
    if dwDataType == NET_DVR_SYSHEAD:
        # 设置流播放模式
        Playctrldll.PlayM4_SetStreamOpenMode(PlayCtrl_Port, 0)
        # 打开码流，送入40字节系统头数据
        if Playctrldll.PlayM4_OpenStream(PlayCtrl_Port, pBuffer, dwBufSize, 1024 * 1024):
            # 设置解码回调，可以返回解码后YUV视频数据
            global FuncDecCB
            FuncDecCB = DECCBFUNWIN(DecCBFun)
            Playctrldll.PlayM4_SetDecCallBackExMend(PlayCtrl_Port, FuncDecCB, None, 0, None)
            # 开始解码播放
            if Playctrldll.PlayM4_Play(PlayCtrl_Port, cv.winfo_id()):
                print(u'播放库播放成功')
            else:
                print(u'播放库播放失败')
        else:
            print(u'播放库打开流失败')
    elif dwDataType == NET_DVR_STREAMDATA:
        Playctrldll.PlayM4_InputData(PlayCtrl_Port, pBuffer, dwBufSize)
    else:
        print(u'其他数据,长度:', dwBufSize)




def OpenPreview(Objdll, lUserId, callbackFun):
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
    global lRealPlayHandle
    lRealPlayHandle = Objdll.NET_DVR_RealPlay_V40(lUserId, byref(preview_info), callbackFun, None)
    return lRealPlayHandle


def InputData(fileMp4, Playctrldll):
    while True:
        pFileData = fileMp4.read(4096)
        if pFileData is None:
            break

        if not Playctrldll.PlayM4_InputData(PlayCtrl_Port, pFileData, len(pFileData)):
            break


if __name__ == '__main__':
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
    win.geometry("%dx%d+%d+%d" % (ww, wh, x, y))


    def left():
        # 开始云台控制
        global in_control
        in_control = 1
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_LEFT, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')


    def right():
        global in_control
        in_control = 1
        # 开始云台控制
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_RIGHT, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')


    def up():
        global in_control
        in_control = 1
        # 开始云台控制
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, TILT_UP, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')


    def down():
        global in_control
        in_control = 1
        # 开始云台控制
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, TILT_DOWN, 0)
        if lRet == 0:
            print('Start ptz control fail, error code is: %d' % Objdll.NET_DVR_GetLastError())
        else:
            print('Start ptz control success')


    def stop():
        global in_control
        in_control = -1
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, TILT_UP, 1)
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, TILT_DOWN, 1)
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_RIGHT, 1)
        lRet = Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_LEFT, 1)


    def quit():
        win.quit()
        global yolo_stop
        yolo_stop = True


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
    cv = tkinter.Canvas(win, bg='white', width=ww, height=wh)
    cv.place(x=0, y=35)

    box_manager = BoxManager(cv, theard_pool)


    def yolo():
        import yolov5.detect
        opt = yolov5.detect.parse_opt()


        def run():
            global is_turn
            sleep(5)
            # 避免过敏
            times = 0
            while True:
                try:
                    sleep(0.5)
                    if in_control == 1:
                        continue
                    results = yolov5.detect.main(opt)[0]
                    boxes = []
                    print(results)
                    for result in results:
                        boxes.append(Box(int(result[0] * width_rate), int(result[1] * height_rate),
                                         int(result[2] * width_rate), int(result[3] * height_rate), "#ff0000"))
                    if len(boxes) > 0:
                        box_manager.trace(boxes[0])
                        Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_RIGHT, 1)
                        Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_LEFT, 1)
                        # 画面中出现目标就应该停止转动
                        is_turn = -1
                        times = 0
                    else:
                        print(box_manager.turn)
                        times += 1
                        if box_manager.box_trace:
                            box_manager.box_trace.destroy()
                            box_manager.box_trace = None
                        # 具有转动方向且失去目标时间达到阈值，则寻找目标
                        if box_manager.turn != -1 and times >= 2:
                            if box_manager.turn == 0:
                                if is_turn == 1:
                                    Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_LEFT, 1)
                                    is_turn = -1
                                elif is_turn == -1:
                                    Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_LEFT, 0)
                                    is_turn = 0
                            else:
                                if is_turn == 0:
                                    Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_RIGHT, 1)
                                    is_turn = -1
                                elif is_turn == -1:
                                    Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_RIGHT, 0)
                                    is_turn = 1
                        elif is_turn != -1:
                            Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_RIGHT, 1)
                            Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_LEFT, 1)
                            is_turn = -1
                            pass
                except:
                    pass

        theard_pool.submit(run)


    yolo()

    # 获取系统平台
    GetPlatform()

    # 加载库,先加载依赖库
    if WINDOWS_FLAG:
        os.chdir(r'./lib/win')
        Objdll = ctypes.CDLL(r'./HCNetSDK.dll')  # 加载网络库
        Playctrldll = ctypes.CDLL(r'./PlayCtrl.dll')  # 加载播放库
    else:
        os.chdir(r'./lib/linux')
        Objdll = cdll.LoadLibrary(r'./libhcnetsdk.so')
        Playctrldll = cdll.LoadLibrary(r'./libPlayCtrl.so')

    SetSDKInitCfg()  # 设置组件库和SSL库加载路径

    # 初始化DLL
    Objdll.NET_DVR_Init()
    # 启用SDK写日志
    Objdll.NET_DVR_SetLogToFile(3, bytes('./SdkLog_Python/', encoding="utf-8"), False)


    # 获取一个播放句柄
    if not Playctrldll.PlayM4_GetPort(byref(PlayCtrl_Port)):
        print(u'获取播放库句柄失败')

    # 登录设备
    (lUserId, device_info) = LoginDev(Objdll)
    if lUserId < 0:
        err = Objdll.NET_DVR_GetLastError()
        print('Login device fail, error code is: %d' % Objdll.NET_DVR_GetLastError())
        # 释放资源
        Objdll.NET_DVR_Cleanup()
        exit()

    dw_returned = ctypes.c_uint16(0)

    # 定义码流回调函数
    funcRealDataCallBack_V30 = REALDATACALLBACK(RealDataCallBack_V30)
    # 开启预览
    lRealPlayHandle = OpenPreview(Objdll, lUserId, funcRealDataCallBack_V30)
    if lRealPlayHandle < 0:
        print('Open preview fail, error code is: %d' % Objdll.NET_DVR_GetLastError())
        # 登出设备
        Objdll.NET_DVR_Logout(lUserId)
        # 释放资源
        Objdll.NET_DVR_Cleanup()
        exit()

    # show Windows
    win.mainloop()

    # 关闭预览
    Objdll.NET_DVR_StopRealPlay(lRealPlayHandle)
    Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_RIGHT, 1)
    Objdll.NET_DVR_PTZControl(lRealPlayHandle, PAN_LEFT, 1)

    # 停止解码，释放播放库资源
    if PlayCtrl_Port.value > -1:
        Playctrldll.PlayM4_Stop(PlayCtrl_Port)
        Playctrldll.PlayM4_CloseStream(PlayCtrl_Port)
        Playctrldll.PlayM4_FreePort(PlayCtrl_Port)
        PlayCtrl_Port = c_long(-1)

    # 登出设备
    Objdll.NET_DVR_Logout(lUserId)

    # 释放资源
    Objdll.NET_DVR_Cleanup()
