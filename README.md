# Bad Apple!! in vanilla DOOM

Bad Apple!! playing inside the original DOS DOOM v1.9, running in DOSBox 0.74-3. The video is drawn by the DOOM renderer on an ordinary wall, and the sound is the real track played through the DOOM sound effects code.

You start it from a new "Bad apple" item in the main menu. After the clip, the game shows a short text screen and the episode 3 ending (the bunny scroll and THE END). Everything else in the game works as before.

This repository only has the build scripts. It does not include DOOM, the WAD or the video. You need your own copies.

## What you need

- `DOOM.EXE` v1.9, MD5 `e2382b7dc47ae2433d26b6e6bc312999`
- `DOOM.WAD` registered v1.9, MD5 `1cd63c5ddff1bf8ce844237f580e9cf3`
- `badapple.mp4`, the shadow art PV (any resolution). The song is 3:39. My copy runs 3:52 because it has end credits after the song, and the build cuts them off.
- Python 3 with `numpy` and `Pillow` (`pip install -r requirements.txt`; `capstone` is only used by `tools/disasm.py`)
- `ffmpeg` in PATH
- DOSBox 0.74-3

Put `DOOM.EXE`, `DOOM.WAD` and `badapple.mp4` in the repo root. If you want the release folder to look like a full install, also copy the other files from the DOOM folder (`SETUP.EXE`, `README.TXT` and so on). `make_release.py` copies them if they are there.

## Building

```
build.bat
```

This runs these steps in order:

1. `tools/extract_media.py` - turns the video into 64x82 gray frames at 35 fps and the audio into 11025 Hz unsigned 8-bit mono.
2. `tools/make_menu_gfx.py` - builds the `M_BADAPL` menu graphic.
3. `tools/build_wad.py` - builds `BADAPPLE.WAD` (map, textures, sounds).
4. `tools/patch_exe.py` - patches `DOOM.EXE` into `BADAPPLE.EXE`.
5. `tools/make_release.py` - puts together `release/`, a normal looking DOOM folder where plain `doom` runs everything.

To run it:

- `dosbox_shell.bat` opens DOSBox in `release/`. Type `doom`.
- `run_badapple.bat` runs `BADAPPLE.EXE -file BADAPPLE.WAD` straight away, which is handy while working on it.

Both expect DOSBox in `C:\Program Files (x86)\DOSBox-0.74-3`. If yours is somewhere else, set the `DOSBOX` variable to the full path of `DOSBox.exe`.

## How it works

### The picture

DOOM has a linedef special that scrolls a wall texture to the left by one texel every tic (special 48). A tic is 1/35 of a second. So if column `t` of a texture holds frame `t` of a video, a scrolling wall plays that video at 35 fps.

That gives one pixel column per wall. The screen is made of 64 short walls side by side, and each has its own texture. Texture `BAPLxx` holds column `xx` of every frame. Each wall is 2 map units wide and 82 units tall, so the picture is 64x82 texels, in 4 shades of gray picked from the DOOM palette.

The textures are 8192 columns wide. The scroll wraps around, so this is also the loop length (about 234 seconds). The video file is 8122 frames with the end credits, so it just fits. The credits are blanked out and the rest of the texture is black, so the screen is black before and after the clip.

Vanilla stores column offsets inside a patch as unsigned 16-bit values. One patch can't be 8192 columns of 82 pixels, so each texture is made of 16 patches of 512 columns. Inside a patch, identical columns point to the same data, and new columns overlap the end of the data already written where they can. Bad Apple has a lot of plain black and white, so this saves a lot of space. The WAD ends up at about 18 MB.

The map is one room with the 64 walls along the north side. The player starts at a distance where the wall fills the 90 degree view, 1 unit closer so the side walls never show at the edges. The status bar is off (`screenblocks 11` in the config). The nodes, segs and blockmap are written by hand, since the room is simple enough for one BSP split.

The map goes in the E4M6 slot, which registered DOOM 1.9 doesn't use. For that map, DOOM asks for music lump `D_RUNNIN`, which only exists in DOOM II. The WAD provides a silent MUS under that name, so no music plays over the track.

### The sound

DOOM sound effects are 8-bit PCM lumps, and the whole track at 11025 Hz is about 2.5 MB. One lump that size fails `Z_Malloc` in the 8 MB zone that DOOM allocates, so the track is cut into 4 parts on tic boundaries (315 samples per tic). Each part goes into a sound slot that DOOM 1 never uses (`DSSSSIT`, `DSSSDTH`, `DSKEENPN`, `DSKEENDT`, sounds 101-104, all from DOOM II).

The parts have to start at the exact tic when the previous one ends. That timing comes from the player's weapon state machine. Choosing the menu item points the pistol's "raise" state at state 35. State 35 waits 105 tics and then goes to a chain of 4 states that DOOM 1 doesn't use (they belong to the super shotgun). Each of those states lasts exactly as many tics as its sound part, and its action plays the sound whose number is in the state's `misc1` field. The weapon sprite is pushed off screen with `misc2 = 1000`, so you never see it.

The video is placed in the texture with the same 105 tic offset, so picture and sound start together. `tools/analyze_capture.py` checks the sync on a DOSBox recording against the original video.

### The executable

`DOOM.EXE` is a DOS/4GW LE executable. Any new code has to fit into the existing pages, and every absolute address in it goes through the relocation table. `tools/le.py` is a small LE parser that can read, move and retarget those relocations.

New code goes into functions that never run in DOOM 1:

- `M_ReadThis` becomes `M_BadApple`. It points the pistol raise state at the chain, starts E4M6 through `G_DeferedInitNew` and closes the menu. "Read This!" is replaced by "Bad apple" in the main menu, and F1 still opens the help screens.
- `A_LoadShotgun2` becomes the action of the first chain state. It puts the pistol state back to normal and plays the first sound part. The other chain states use the second half of this code, which just plays the sound from `misc1`.
- `A_BrainAwake` (the DOOM II boss) becomes the ending. It sets the episode to 3, calls `F_StartFinale` and swaps in a custom text.
- `G_InitNew` refuses episodes above 3. That check is changed to 4 so E4M6 can load.

The ending text is stored where DOOM II's `c2text` was, so the real E3 text stays untouched. The script checks the MD5 and the bytes at every address before writing anything, so it stops on a different build of the exe.

### The menu graphic

`M_BADAPL` is made from letters cut out of DOOM's own menu graphics: "Load Game", "Options", "Hurt me plenty" and the big D from "Knee-Deep in the Dead", with a middle bar added to make it a B. Run `tools/make_menu_gfx.py --ascii` to see the letters in the console.

### The release folder

`make_release.py` merges `BADAPPLE.WAD` into a copy of `DOOM.WAD` and copies `BADAPPLE.EXE` in as `DOOM.EXE`. DOOM doesn't need `-file` that way, so it doesn't print the "modified game" warning. `BADAPPLE.CFG` becomes `DEFAULT.CFG` (full screen view, max sound volume, Sound Blaster).

## Other tools

- `tools/check_wad.py` reads `BADAPPLE.WAD` the way the engine does and saves a few frames as PNG to `build/preview/`.
- `tools/disasm.py DOOM.EXE 22b00:40` disassembles code from the exe and marks relocations.
- `tools/patches.py` reads and writes DOOM picture lumps.

## Credits

DOOM is by id Software. Bad Apple!! is from Touhou by ZUN, the vocal arrangement is by Alstroemeria Records, and the shadow art PV is by Anira. None of their files are in this repository.
