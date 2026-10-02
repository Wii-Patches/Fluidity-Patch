# How it works

## WAD

Header `>I2sH6I`, 64-byte aligned certificate chain / ticket / TMD / contents. Contents
are AES-128-CBC; the title key is in the ticket, itself encrypted with the Wii common
key (IV = title id + 8 zero bytes); each content's IV is its index (u16) + zeros.
Content 1 is the game's `main.dol`, LZ11-compressed (`tools/lz11.py`). `tools/wad.py`
decrypts and checks every SHA-1, replaces a content, re-encrypts, updates the TMD sizes
and hashes and fake-signs the TMD and ticket (padding brute-forced until the SHA-1
begins with `00`).

## Code placement

The new code goes into a **data** section of the DOL (slots 7–17) at `0x80001820`:
a new text section stops the loader from booting the title. The first `0x40` bytes
of the section are the state block. A hook is a branch at the hook site to a body whose
last word branches back to site+4 (Gecko `C2` semantics, so the same bodies serve both
delivery methods).

## Classic Controller

Vague Rant's four hooks (`read_kpad_acc`, `calc_dpd_variable`, `read_kpad_ext`, `read_kpad_button`)
are applied verbatim, relocated per region (`codes/*-cc.txt`).

## GameCube controller

- **Frame hook** (before the game's per-frame controller pass): polls port 1 through the
  serial interface (`0xCD006400`; auto-poll is configured and the SDK's shadow kept in step);
  the game does not call `KPADRead` while no Wii Remote is connected, so when a pad appears
  the hook invokes the WPAD connect callback (`channel block + 0x8E8`) and on unplug reports
  a disconnect.
- **WPADProbe hook**: reports a Classic Controller (type 2) on channel 0 while the pad is
  plugged in and no real extension is there.
- **Sample hook** (inside `KPADiRead`): writes two fresh Classic Controller samples
  (extension 2, format 8) into channel 0's sample ring each frame — the older with the
  previous frame's buttons, so press and release edges are not lost — and decorates real samples
  of a bare Wii Remote. A real Nunchuk or Classic Controller is never touched.

Addresses are resolved per region from masked instruction windows (`tools/anchors.py`)
and checked against the displaced instructions before anything is written.

## Testing

`tests/` boots patched WADs in a private Dolphin user directory and reads memory over the
GDB stub. `tests/feedtest.py` writes pad responses into the state block (a `DEBUG_FEED` build)
and prints the game's KPAD channel 0 (`hold`, `ext`, sticks, acceleration) for every input.
