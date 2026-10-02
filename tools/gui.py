#!/usr/bin/env python3
"""Drag-and-drop patcher: drop a Fluidity or Hydroventure WAD on the window, done.

Patches the game's main.dol for the options you tick and writes a new WAD next to the original
(`<name> (CC+GC).wad`); the original is never touched.  Re-encrypting a WAD needs the Wii common key, which
is bundled in prebuilt/; choose another with the button if needed.
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patcher

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAVE_DND = True
except ImportError:                                    # fall back to click-to-browse
    HAVE_DND = False


def asset(name):
    if getattr(sys, 'frozen', False):
        return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'assets', name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', name)


BASE = TkinterDnD.Tk if HAVE_DND else tk.Tk


class App(BASE):
    def __init__(self):
        super().__init__()
        self.title('Fluidity-Patcher')
        self.geometry('620x640')
        self.msgq = queue.Queue()
        self.busy = False
        self.key = patcher.find_key()

        try:
            img = tk.PhotoImage(file=asset('logo.png'))
            self.logo = img.subsample(max(1, img.width() // 300))
            tk.Label(self, image=self.logo).pack(pady=(10, 0))
        except Exception:                              # the window is fine without its logo
            pass
        tk.Label(self, text='Fluidity (USA)  -  Hydroventure (Europe)',
                 font=('Helvetica', 12, 'bold')).pack(pady=(4, 6))

        opts = tk.LabelFrame(self, text='Patches')
        opts.pack(fill='x', padx=10)
        self.cc = tk.BooleanVar(value=True)
        tk.Checkbutton(opts, text='Classic Controller', variable=self.cc, command=self.sync).pack(anchor='w')
        self.gc = tk.BooleanVar(value=True)
        self.gc_cb = tk.Checkbutton(opts, text='GameCube controller (port 1)', variable=self.gc)
        self.gc_cb.pack(anchor='w')
        self.sharp = tk.BooleanVar(value=False)
        tk.Checkbutton(opts, text='Turn the copy filter off (sharper picture)', variable=self.sharp).pack(anchor='w')

        keyrow = tk.Frame(self)
        keyrow.pack(fill='x', padx=10, pady=(8, 0))
        self.keylabel = tk.Label(keyrow, anchor='w')
        self.keylabel.pack(side='left', fill='x', expand=True)
        tk.Button(keyrow, text='Choose common-key.bin...', command=self.pick_key).pack(side='right')
        self.show_key()

        hint = ('Drop a .wad here\n\n(or click to choose one)' if HAVE_DND else 'Click to choose a .wad')
        self.drop = tk.Label(self, text=hint, relief='ridge', bd=2, padx=10, pady=24, cursor='hand2')
        self.drop.pack(fill='x', padx=10, pady=10)
        self.drop.bind('<Button-1>', lambda e: self.pick())
        if HAVE_DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind('<<Drop>>', self.on_drop)

        tk.Label(self, text='The original WAD is not modified; a patched copy is written beside it', fg='#666').pack()

        self.log = tk.Text(self, height=10, state='disabled', wrap='word')
        self.log.pack(fill='both', expand=True, padx=10, pady=10)
        self.after(100, self.poll_queue)

    def sync(self):
        self.gc_cb.configure(state='normal' if self.cc.get() else 'disabled')

    def show_key(self):
        if self.key:
            self.keylabel.configure(text='Wii common key: %s' % os.path.basename(self.key), fg='#060')
        else:
            self.keylabel.configure(text='Wii common key: not found (16-byte common-key.bin)', fg='#a00')

    def pick_key(self):
        p = filedialog.askopenfilename(title='Select the Wii common key', filetypes=[('Key file', '*.bin'), ('All files', '*')])
        if p:
            if os.path.getsize(p) != 16:
                messagebox.showerror('Not a common key', 'The common key file must be exactly 16 bytes.')
                return
            self.key = p
            self.show_key()

    def on_drop(self, event):
        paths = self.tk.splitlist(event.data)          # handles {braced paths with spaces}
        if paths:
            self.start(paths[0])

    def pick(self):
        if self.busy:
            return
        p = filedialog.askopenfilename(title='Select a WAD', filetypes=[('Wii channel', '*.wad'), ('All files', '*')])
        if p:
            self.start(p)

    def append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == 'log':
                    self.append_log(payload)
                elif kind == 'done':
                    ok, msg = payload
                    self.busy = False
                    self.drop.configure(state='normal')
                    if ok:
                        messagebox.showinfo('Done', 'Wrote:\n%s' % msg)
                    else:
                        messagebox.showerror('Patch failed', msg)
        except queue.Empty:
            pass
        self.after(100, self.poll_queue)

    def run(self, src, dst, which):
        try:
            patcher.patch_wad(src, dst, self.key, which, log=lambda t: self.msgq.put(('log', t)))
            self.msgq.put(('done', (True, dst)))
        except Exception as e:                         # shown to the user, not swallowed
            self.msgq.put(('done', (False, str(e))))

    def start(self, path):
        if self.busy:
            return
        if not os.path.isfile(path):
            messagebox.showerror('Not a file', '%s is not a file.' % path)
            return
        if not self.key:
            messagebox.showerror('No common key', 'Choose the 16-byte Wii common key (common-key.bin) first.')
            return
        which = []
        if self.cc.get():
            which.append('cc')
            if self.gc.get():
                which.append('gc')
        if self.sharp.get():
            which.append('sharp')
        if not which:
            messagebox.showerror('Nothing selected', 'Tick at least one patch.')
            return
        tag = '+'.join({'cc': 'CC', 'gc': 'GC', 'sharp': 'Sharp'}[w] for w in which)
        dst = '%s (%s).wad' % (os.path.splitext(path)[0], tag)
        self.busy = True
        self.drop.configure(state='disabled')
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        threading.Thread(target=self.run, args=(path, dst, which), daemon=True).start()


if __name__ == '__main__':
    App().mainloop()
