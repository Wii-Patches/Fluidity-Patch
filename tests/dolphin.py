"""Run Fluidity in a private, resettable Dolphin and look at / poke it from outside.

Everything lives in a throwaway user directory; the GDB stub gives memory access, the Pipe device a
scripted GameCube pad, and frame dumping gives pictures.  Env: DOLPHIN (path to the binary / app).
"""
import glob, os, shutil, struct, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from gdbmem import Gdb

APP = os.environ.get('DOLPHIN_APP', '/Applications/Dolphin.app')
PORT = int(os.environ.get('FLUID_GDB_PORT', 2371))
WORK = os.environ.get('FLUID_WORK', os.path.join(__import__('tempfile').gettempdir(), 'fluid'))


def prepare(user, gecko=None, gid=None, wiimote=False, pad=True, frames=False, extra_core=''):
    shutil.rmtree(user, ignore_errors=True)
    for d in ('Config', 'GameSettings', 'Pipes'):
        os.makedirs(os.path.join(user, d))
    os.mkfifo(os.path.join(user, 'Pipes', 'gc'))
    open(os.path.join(user, 'Config', 'Dolphin.ini'), 'w').write(
        "[General]\nGDBPort = %d\n[Interface]\nConfirmStop = False\nUsePanicHandlers = False\n"
        "[Core]\nMMU = True\nCPUThread = False\nCPUCore = 4\nEnableDebugging = True\nEnableCheats = True\n"
        "WiimoteContinuousScanning = False\nWiimoteControllerInterface = False\nSIDevice0 = %d\nSIDevice1 = 0\n%s"
        "[Analytics]\nPermissionAsked = True\nEnabled = False\n" % (PORT, 6 if pad else 0, extra_core) +
        ("[Movie]\nDumpFrames = True\nDumpFramesSilent = True\nDumpFramesAsImages = True\n" if frames else ""))
    open(os.path.join(user, 'Config', 'GCPadNew.ini'), 'w').write(
        "[GCPad1]\nDevice = Pipe/0/gc\n" + "".join("Buttons/%s = `Button %s`\n" % (b, b) for b in 'ABXYZ') +
        "Buttons/Start = `Button START`\n" +
        "".join("D-Pad/%s = `Button D_%s`\n" % (d.title(), d.upper()) for d in ('up', 'down', 'left', 'right')) +
        "Triggers/L = `Button L`\nTriggers/R = `Button R`\n"
        "Main Stick/Up = `Axis MAIN Y +`\nMain Stick/Down = `Axis MAIN Y -`\nMain Stick/Left = `Axis MAIN X -`\nMain Stick/Right = `Axis MAIN X +`\n"
        "C-Stick/Up = `Axis C Y +`\nC-Stick/Down = `Axis C Y -`\nC-Stick/Left = `Axis C X -`\nC-Stick/Right = `Axis C X +`\n")
    open(os.path.join(user, 'Config', 'WiimoteNew.ini'), 'w').write("[Wiimote1]\nSource = %d\n" % (1 if wiimote else 0))
    if gecko:
        lines = [l for l in open(gecko).read().split('\n')]
        body = "\n".join(lines[1:]).strip()
        open(os.path.join(user, 'GameSettings', gid + '.ini'), 'w').write(
            "[Gecko_Enabled]\n$TEST\n[Gecko]\n$TEST\n%s\n" % body)


def launch(user, image, video='Null'):
    subprocess.check_call(['open', '-n', '-a', APP, '--args', '-b', '-u', user, '-e', image, '-v', video])
    time.sleep(2)


def pid(user):
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
    for ln in out.splitlines():
        if user in ln and 'Dolphin' in ln and 'dolphin.py' not in ln:
            return int(ln.split()[0])


def stop(user):
    p = pid(user)
    if p:
        os.kill(p, 15)
        time.sleep(2)
        if pid(user):
            os.kill(pid(user), 9)


def connect(tries=120):
    for _ in range(tries):
        try:
            return Gdb(port=PORT, timeout=30)
        except OSError:
            time.sleep(1)
    raise RuntimeError('no GDB stub')


class Pad:
    def __init__(self, user):
        self.f = os.open(os.path.join(user, 'Pipes', 'gc'), os.O_WRONLY | os.O_NONBLOCK)

    def cmd(self, s):
        os.write(self.f, (s + '\n').encode())

    def press(self, b): self.cmd('PRESS ' + b)
    def release(self, b): self.cmd('RELEASE ' + b)
    def stick(self, which, x, y): self.cmd('SET %s %.3f %.3f' % (which, x, y))
    def trig(self, which, v): self.cmd('SET %s %.3f' % (which, v))


def frames(user):
    return sorted(glob.glob(os.path.join(user, 'Dump', 'Frames', '**', '*.png'), recursive=True), key=os.path.getmtime)
