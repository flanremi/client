import cv2


class switch:

    def __init__(self) -> None:
        super().__init__()
        self.open = True


def video_demo(s: switch):
    capture = cv2.VideoCapture(1)  # 0为电脑内置摄像头
    while s.open:
        ret, frame = capture.read()  # 摄像头读取,ret为是否成功打开摄像头,true,false。 frame为视频的每一帧图像
        frame = cv2.flip(frame, 1)  # 摄像头是和人对立的，将图像左右调换回来正常显示。
        cv2.imshow("video", frame)
        c = cv2.waitKey(50)


