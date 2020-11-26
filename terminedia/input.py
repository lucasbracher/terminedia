"""non-blocking Keyboard reading and other input related code
"""
import enum
import os
import re
import sys
import time

from collections import defaultdict, namedtuple
from contextlib import contextmanager

from terminedia.utils import mirror_dict, V2
from terminedia.events import Event, dispatch, EventTypes


# Keyboard reading code copied and evolved from
# https://stackoverflow.com/a/6599441/108205
# (@mheyman, Mar, 2011)


@contextmanager
def _posix_keyboard():
    """
    This context manager reconfigures `stdin` so that key presses
    are read in a non-blocking way.

    Inside a managed block, the :any:`inkey` function can be called and will
    return whether a key is currently pressed, and which it is.

    An app that will make use of keyboard reading alongside screen
    controling can enter both this and an instance of :any:`Screen` in the
    same "with" block.

    (Currently Posix only)

    """
    fd = sys.stdin.fileno()
    # save old state
    flags_save = fcntl.fcntl(fd, fcntl.F_GETFL)
    attrs_save = termios.tcgetattr(fd)
    # make raw - the way to do this comes from the termios(3) man page.
    attrs = list(attrs_save)  # copy the stored version to update
    # iflag
    attrs[0] &= ~(
        termios.IGNBRK
        | termios.BRKINT
        | termios.PARMRK
        | termios.ISTRIP
        | termios.INLCR
        | termios.IGNCR
        | termios.ICRNL
        | termios.IXON
    )
    # oflag
    attrs[1] &= ~termios.OPOST
    # cflag
    attrs[2] &= ~(termios.CSIZE | termios.PARENB)
    attrs[2] |= termios.CS8
    # lflag
    attrs[3] &= ~(
        termios.ECHONL | termios.ECHO | termios.ICANON | termios.ISIG | termios.IEXTEN
    )
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags_save | os.O_NONBLOCK)
    try:
        yield
    finally:
        # restore old state
        termios.tcsetattr(fd, termios.TCSAFLUSH, attrs_save)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags_save)

def _posix_inkey(break_=True, clear=True, _dispatch=False):
    """Return currently pressed key as a string

    Args:
      - break\_ (bool): Boolean parameter specifying whether "CTRL + C"
        (\x03) should raise KeyboardInterrupt or be returned as a
        keycode. Defaults to True.
      -clear (bool): clears the keyboard buffer contents
      - _dispatch (bool): dispatch keyboard Events for keypresses
             used internally for event-based keyboard input

    *Important*: This function only works inside a
    :any:`keyboard` managed context. (Posix)

    Code values or code sequences for non-character keys,
    like ESC, direction arrows, fkeys are kept as constants
    in the "KeyCodes" class.

    Unfortunatelly, due to the nature of console streaming,
    this can't receive "keypress" or "keyup" events, and repeat-rate
    is not configurable, nor can it detect modifier keys, or
    simultaneous key-presses.

    """
    keycode = ""

    if clear:
        c = sys.stdin.read(10000)
        if c:
            c = c[
                c.rfind("\x1b") :
            ]  # if \x1b is not found, rfind returns -1, which is the desired value
    else:
        c = sys.stdin.read(1)  # returns a single character

    while True:
        if not c:
            break
        if c == "\x03" and break_:
            raise KeyboardInterrupt()
        keycode += c
        if (len(keycode) == 1 or keycode in KeyCodes.codes) and keycode != "\x1b":
            break
        if mouse.enabled:
            m = mouse.match(keycode)
            if m:
                return ""
        c = sys.stdin.read(1)

    if _dispatch:
        dispatch(Event(EventTypes.KeyPress, key=keycode))

    return keycode


def getch(timeout=0) -> str:
    """Enters non-blocking keyboard mode and returns the first keypressed
    Args:
      - timeout (float): time in seconds to wait. If 0 (default), waits forever

    """
    step = 1 / 30
    ellapsed = step
    with keyboard():
        time.sleep(step)
        key = inkey()
        while not key:
            key = inkey()
            time.sleep(step)
            ellapsed += step
            if timeout and ellapsed >= timeout:
                key = ""
                break
    return key


def pause(timeout=0) -> None:
    """Enters non-blocking keyboard mode and waits for any keypress
    Args:
      - timeout (float): time in seconds to wait. If 0 (default), waits forever

    """
    getch(timeout)

def _testkeys():
    """Debug function to print out keycodes as read by :any:`inkey`"""
    with keyboard():
        while True:
            try:
                key = inkey()
            except KeyboardInterrupt:
                break
            if key:
                print("", key.encode("utf-8"), end="", flush=True)
            print(".", end="", flush=True)
            time.sleep(0.3)


class _posix_KeyCodes:
    """Character keycodes as they appear in stdin

    (and as they are reported by :any:`inkey` function). This class
    is used only as a namespace. Also note that printable-character
    keys, such as upper and lower case letters, numbers and symbols
    are not listed here, as their "code" is just a string containing
    themselves.
    """

    F1 = "\x1bOP"
    F2 = "\x1bOQ"
    F3 = "\x1bOR"
    F4 = "\x1bOS"
    F5 = "\x1b[15~"
    F6 = "\x1b[17~"
    F7 = "\x1b[18~"
    F8 = "\x1b[19~"
    F9 = "\x1b[20~"
    F10 = "\x1b[21~"
    F11 = "\x1b[23~"
    F12 = "\x1b[24~"
    ESC = "\x1b"
    BACK = "\x7f"
    DELETE = "\x1b[3~"
    ENTER = "\r"
    PGUP = "\x1b[5~"
    PGDOWN = "\x1b[6~"
    HOME = "\x1b[H"
    END = "\x1b[F"
    INSERT = "\x1b[2~"
    UP = "\x1b[A"
    RIGHT = "\x1b[C"
    DOWN = "\x1b[B"
    LEFT = "\x1b[D"

    codes = mirror_dict(locals())


@contextmanager
def _win32_keyboard():
    """
    This context manager is available to offer compatibility with the Posix equivalent.

    It is not really needed under Windows.

    """
    try:
        yield
    finally:
        pass



def _win32_inkey(break_=True, clear=True, _dispatch=True):
    """Return currently pressed key as a string

    Args:
      - break\_ (bool): Boolean parameter specifying whether "CTRL + C"
        (\x03) should raise KeyboardInterrupt or be returned as a
        keycode. Defaults to True.
      - clear (bool): clears the keyboard buffer contents
      - _dispatch (bool): dispatch keyboard Events for keypresses
            used internally for event-based keyboard reading

    *Important*: This function only works inside a
    :any:`keyboard` managed context. (Posix)

    Code values or code sequences for non-character keys,
    like ESC, direction arrows, fkeys are kept as constants
    in the "KeyCodes" class.

    Unfortunatelly, due to the nature of console streaming,
    this can't receive "keypress" or "keyup" events, and repeat-rate
    is not configurable, nor can it detect modifier keys, or
    simultaneous key-presses.

    """

    if not msvcrt.kbhit():
        return ""

    code = msvcrt.getwch()
    if code in "\x00à" : # and msvcrt.kbhit():
        code += msvcrt.getwch()

    if _dispatch:
        dispatch(Event(EventTypes.KeyPress, key=keycode))

    return code


def _testkeys():
    """Debug function to print out keycodes as read by :any:`inkey`"""
    with keyboard():
        while True:
            try:
                key = inkey()
            except KeyboardInterrupt:
                break
            if key:
                print("", key.encode("utf-8"), end="", flush=True)
            print(".", end="", flush=True)
            time.sleep(0.3)

def _testmouse():
    # https://stackoverflow.com/questions/59864485/capturing-mouse-in-virtual-terminal-with-ansi-escape
    # change stdin and stdout into unbuffered
    with keyboard():
        # ignite mouse through ancient, unknown brujeria
        sys.stdout.write("\x1b[?1003h\x1b[?1015h\x1b[?1006h")
        #sys.stdout.write("\x1b[?1005h") #\x1b[?1015h\x1b[?1006h")
        sys.stdout.flush()
        counter = 0
        while counter < 200:

            data = sys.stdin.buffer.read(16)
            if data:
                print(data)
            time.sleep(0.05)
            counter += 1

    print("\x1b[?1005l")

class _win32_KeyCodes:
    """Character keycodes as they appear in stdin

    (and as they are reported by :any:`inkey` function). This class
    is used only as a namespace. Also note that printable-character
    keys, such as upper and lower case letters, numbers and symbols
    are not listed here, as their "code" is just a string containing
    themselves.
    """

    F1 = "\x00;"
    F2 = "\x00<"
    F3 = "\x00="
    F4 = "\x00>"
    F5 = "\x00?"
    F6 = "\x00@"
    F7 = "\x00A"
    F8 = "\x00B"
    F9 = "\x00C"
    F10 = "\x00D"
    F11 = "á\x85"
    F12 = "á\x86"
    ESC = "\x1b"
    BACK = "\x08"
    DELETE = "à5"
    ENTER = "\r"
    PGUP = "àI"
    PGDOWN = "àQ"
    HOME = "àG"
    END = "àO"
    INSERT = "àR"
    UP = "àH"
    RIGHT = "àM"
    DOWN = "àP"
    LEFT = "àK"

    codes = mirror_dict(locals())


class MouseButtons(enum.IntFlag):
    Button1 = 1
    Button2 = 2
    Button3 = 4
    MouseWheelUp = 8
    MouseWheelDown = 16
    Button4 = 8     # SIC: this is an alias
    Button5 = 16
    Button6 = 32
    Button7 = 64


_button_map = {
    0: MouseButtons.Button1,
    1: MouseButtons.Button2,
    2: MouseButtons.Button3,
    64: MouseButtons.Button4,
    65: MouseButtons.Button5,
    128: MouseButtons.Button6,
    129: MouseButtons.Button7,
}


class _Mouse:

    CLICK_THRESHOLD = 0.3

    def __init__(self):
        # TBD: check for re-entering?
        self.enabled = False
        self.last_click = (0, 0)

    def __enter__(self):
        self.keyboard = keyboard()
        self.keyboard.__enter__()
        self.enabled = True
        # sys.stdout.write("\x1b[?1005h")
        sys.stdout.write("\x1b[?1003h\x1b[?1015h\x1b[?1006h")
        sys.stdout.flush()

    def __exit__(self, *args):
        sys.stdout.write("\x1b[?1005l")
        sys.stdout.flush()
        self.enabled = False
        self.keyboard.__exit__(*args)


    def match(self, sequence):
        # The ANSI sequence for a mouse event in mode 1006 is '<ESC>[B;Col;RowM' (last char is 'm' if button-release)
        m = re.match(r"\x1b\[\<(?P<button>\d+);(?P<column>\d+);(?P<row>\d+)(?P<press>[Mm])", sequence)
        if not m:
            return None
        params = m.groupdict()
        pressed = params["press"] == "M"
        button = _button_map.get(int(params["button"]) & (~0x20), None)
        moving = bool(int(params["button"]) & 0x20)

        col = int(params["column"]) - 1
        row = int(params["row"]) - 1

        click_event = event = None

        # TBD: check for different buttons in press events and send combined button events
        if moving:
            event = Event(EventTypes.MouseMove, pos=V2(col, row), buttons=button)
        elif pressed:
            event = Event(EventTypes.MousePress, pos=V2(col, row), buttons=button)
            self.last_click = (time.time(), button)
        else:
            event = Event(EventTypes.MouseRelease, pos=V2(col, row), buttons=button)
            if time.time() - self.last_click[0] < self.CLICK_THRESHOLD and button == self.last_click[1]:
                click_event = Event(EventTypes.MouseClick, pos=V2(col, row), buttons=button)

        if event:
            dispatch(event)

        if click_event:
            dispatch(click_event)

        return event



mouse = _Mouse()



if sys.platform != "win32":
    import fcntl
    import termios

    inkey = _posix_inkey
    keyboard = _posix_keyboard
    KeyCodes = _posix_KeyCodes
else:
    import msvcrt
    inkey = _win32_inkey
    keyboard = _win32_keyboard
    KeyCodes = _win32_KeyCodes


