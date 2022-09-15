__log = ''
__log_screen = None


def log(*l):
    global __log
    global __log_screen
    for s in l:
        __log += str(s)
    __log += '\n'
    if __log_screen:
        __log_screen.logNotify()


def getLog():
    global __log
    return __log


def addLog(*l):
    global __log
    for s in l:
        __log += str(s)
    __log += '\n'


def bindScreen(screen):
    global __log_screen
    __log_screen = screen


def unbindScreen():
    global __log_screen
    __log_screen = None
