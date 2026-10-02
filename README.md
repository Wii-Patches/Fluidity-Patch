# Fluidity Patch

Play **Fluidity** (WiiWare, USA) and **Hydroventure** (Europe) with a **Classic
Controller** or a **GameCube controller** instead of a Wii Remote. The Classic
Controller layer is [Vague Rant's](https://gbatemp.net/threads/new-classic-controller-hacks.659837/)
Gecko hack; the GameCube controller is presented to the game as a Classic Controller
(the same technique as [ACCF-Patch](https://github.com/quatric/ACCF-Patch) and
[Excite-Patch](https://github.com/quatric/Excite-Patch)), so every feature of his hack
works with it too.

The patches are applied to your own copy of the game: give the patcher your `.wad`
and it writes a patched copy next to it. Nothing from the game is included in this
repository.

![Fluidity](assets/logo.png)

## Status

Tested in Dolphin, on both releases, with scripted pad input read back out of the
game's own controller state: every button, both sticks, tilt, shake and the
right-stick D-pad+1 trick, and with no Wii Remote connected at all. **Not yet tested on a
real Wii** — see [On a real Wii](#on-a-real-wii).

**Known limits:**

- GameCube port 1 only
- the Wii Remote and a GameCube pad can both be used; the pad takes over the
  Classic Controller slot of player 1 only while no real Classic Controller is attached
- the Gecko versions of the GameCube codes (`codes/*-gc.txt`) are generated from the
  same data as the patcher but are not part of the Dolphin testing; prefer the patched WAD
- the Nunchuk remapper / tilt assembly from the forum thread is not included

## Controls

### GameCube controller

| Input | Action |
| --- | --- |
| Control stick | Tilt (steers the water) · HOME Menu pointer |
| A | Wii Remote 2 (confirm / interact) |
| B | Wii Remote 1 (cancel / gather) |
| X | Wii Remote A (zoom out, enter the playroom) |
| Y | Shake (jump, rain) |
| C-stick | Right stick: D-pad + 1 (Vague Rant's code) |
| L / R | Menu left / right |
| D-pad | Menu navigation (sideways remote layout) |
| Start | Pause / options (+) |
| Z | Map / tutorial (−) |
| Start + Z | HOME Menu |

### Classic Controller

Vague Rant's mapping, unchanged (see his thread for the table).

## Installing

### Patch your WAD

You need a clean `.wad` of the game. The 16-byte Wii **common key**
(`common-key.bin`), which a WAD is re-encrypted with, ships in `tools/prebuilt/`;
pass `--key` to use another. Download the patcher for your system from the releases page, or run
it from source (Python 3 with tkinter and `pycryptodome`):

```bash
pip install pycryptodome tkinterdnd2
python3 tools/gui.py
```

Command line:

```bash
python3 tools/patcher.py "Fluidity (USA).wad" "Fluidity (USA) patched.wad" [--key common-key.bin] [--no-gc] [--sharp]
```

The patcher recognises the stock game by its `main.dol`; other versions and WADs
already patched are refused. The result is fake-signed, so install it with a
signature-patched IOS or an installer that allows it (as with any patched WAD).

Options: Classic Controller, GameCube controller, and *copy filter off* (the sharper
picture, also from the thread).

### Gecko codes (Dolphin)

`codes/WFLE-cc.txt` (USA) and `codes/WFLP-cc.txt` (Europe) are Vague Rant's codes
as posted. `*-sharp.txt` turns the copy filter off. `*-gc.txt` is the Classic
Controller code plus the GameCube hook.

## On a real Wii

- Connect the GameCube controller before starting the game.
- The new code lives in a data section loaded at `0x80001820`; the GameCube hook
  polls the pad over the serial interface itself, so no loader support is required.
- Reports from real hardware are welcome.

## Building from source

With [devkitPPC](https://devkitpro.org/) and your own `main.dol` dumps
(`python3 tools/getdol.py <wad> common-key.bin dols/WFLE.dol` extracts them into `dols/`):

```bash
python3 tools/gcbuild.py        # rebuilds tools/prebuilt/patches.json and codes/
python3 tools/check.py          # consistency checks (no game files needed)
```

Tests (Dolphin, GDB stub, no game data in the repository) are in `tests/`;
`DEBUG_FEED=1 python3 tools/gcbuild.py` builds a variant that reads the pad from
memory so `tests/feedtest.py` can drive it deterministically.

How the patches work is in [docs/TECHNICAL.md](docs/TECHNICAL.md).

## Credits

- **Vague Rant** — the Classic Controller hack, including the right stick as D-pad + 1
  and the HOME Menu pointer. These are his codes.
- **awesomeee** — the Nunchuk / Classic remapping research this grew out of.
- The GameCube-as-Classic-Controller technique follows Crediar's and Barrel Blast's
  work, as used in ACCF-Patch.

## Contact

quatricsoftware@gmail.com

No support will be provided for this tool.

## License

MIT — see [LICENSE](LICENSE).

Copyright (c) 2026 quatric
