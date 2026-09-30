"""brand-film CLI.

  python make_film.py doctor                     check python packages, ffmpeg, fonts
  python make_film.py validate film.json         print the timeline, check duration <= 90 s
  python make_film.py music    film.json         synthesize the score -> out/music.wav
  python make_film.py stills   film.json 3,40.5  render single frames -> out/stills/
  python make_film.py sheet    film.json         contact sheets of every scene -> out/sheet_*.jpg
  python make_film.py video    film.json [--fps 30] [--draft] [--res 720|1080]   render + mux -> out/<name>.mp4
                                                 (default 1920x1080; "resolution" in film.json or --res overrides)
  python make_film.py all      film.json         validate + music + sheet + video
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image, ImageDraw

import bf_core as C
from bf_core import *

TL = None
S = None
OUT = None


def setup(cfg_path):
    global TL, S, OUT
    import bf_score
    import bf_scenes
    load_config(cfg_path)
    TL = bf_score.Timeline(C.CFG)
    bf_scenes.set_timeline(TL)
    S = bf_scenes
    OUT = os.path.join(C.CFG['_dir'], C.CFG.get('out_dir', 'out'))
    os.makedirs(OUT, exist_ok=True)
    return TL


def nostalgia():
    return C.CFG.get('grade', {}).get('nostalgia', True)


def warmth(t):
    if not nostalgia():
        return 0.0
    wu = C.CFG.get('grade', {}).get('warm_until', TL.T2 * .7)
    return 1 - sstep(wu * .25, wu, t)


def frame_at(i, fps=FPS):
    t = i / fps
    if t < TL.T2:
        parts = []
        for k, sc in enumerate(TL.p1):
            a, b, _, _ = TL.scene1_window(k)
            if a <= t < b:
                parts.append([a, b, sc, 1.0])
        parts = parts[-2:] or [[0, 0, TL.p1[-1], 1.0]]
        if len(parts) == 2:
            A, B = parts
            m = ease_io((t - B[0]) / max(1e-3, A[1] - B[0]))
            A[3], B[3] = 1 - m, m
        img = None
        for a, b, sc, wgt in parts:
            arr = render_frame(S.PART1[sc['type']](sc, t)) * wgt
            img = arr if img is None else img + arr
        fl = sum(g * .3 * math.exp(-(t - tc) * 5) for tc, g in TL.crashes if tc <= t < TL.T2)
        w = warmth(t)
        if w > 0:
            lm = img @ np.array([.3, .59, .11], np.float32)
            sep = np.stack([lm * 1.07 + 12, lm * .93 + 6, lm * .72], -1)
            img = img * (1 - .55 * w) + sep * .55 * w
        img = img * (C.VIG * .3 + .7)
        img += C.GRAIN[i % 6].repeat(2, 0).repeat(2, 1)[..., None] * (9 * w + 2.5)
        img += fl * 255
        img *= sstep(0, 1.3, t)
    else:
        sec = TL.section2_at(t)
        img = render_frame(S.PART2[sec['type']](sec, t))
        for tw in TL.whips:
            dt = abs(t - tw)
            if dt < .1:
                img = hblur_img(img, 160 * (1 - dt / .1))
        for ts, amp in TL.shakes:
            if 0 <= t - ts < .3:
                a = amp * math.exp(-(t - ts) * 14)
                img = np.roll(img, (int(round(a * .6 * math.cos((t - ts) * 70))), int(round(a * math.sin((t - ts) * 90)))),
                              axis=(0, 1))
        img += sum(g * math.exp(-(t - tf) * d) for tf, g, d in TL.flashes2 if t >= tf) * 255
        img += C.GRAIN[i % 6].repeat(2, 0).repeat(2, 1)[..., None] * 4.5
        img *= 1 - sstep(TL.DUR - .55, TL.DUR, t) * .98
    return np.clip(img, 0, 255).astype(np.uint8)


_FPS = FPS


def _init_worker(cfg_path, fps, res):
    global _FPS
    setup(cfg_path)
    C.set_resolution(res)
    _FPS = fps


def _render(i):
    return C.to_output(frame_at(i, _FPS)).tobytes()


def key_times():
    ts = []
    for k, sc in enumerate(TL.p1):
        _, _, a, b = TL.scene1_window(k)
        ts += [(a + (b - a) * .35, f'P1-{k + 1} {sc["type"]}'), (a + (b - a) * .8, f'P1-{k + 1} {sc["type"]}')]
    for sc in TL.p2:
        a = TL.b2(sc['bar0'])
        ts += [(a + TL.BEAT2 * 1.8, f'P2 {sc["type"]}')]
        if sc['bars'] > 1:
            ts += [(a + TL.BAR2 + TL.BEAT2 * 1.6, f'P2 {sc["type"]}')]
    return ts


def cmd_sheet():
    ts = key_times()
    w, h, cols = 640, 360, 4
    per = 16
    for p in range(0, len(ts), per):
        sub = ts[p:p + per]
        rows = math.ceil(len(sub) / cols)
        sheet = Image.new('RGB', (w * cols, h * rows))
        d = ImageDraw.Draw(sheet)
        for j, (t, lab) in enumerate(sub):
            im = Image.fromarray(frame_at(int(round(t * FPS)))).resize((w, h))
            sheet.paste(im, ((j % cols) * w, (j // cols) * h))
            d.rectangle([(j % cols) * w, (j // cols) * h, (j % cols) * w + 250, (j // cols) * h + 22], fill=(0, 0, 0))
            d.text(((j % cols) * w + 6, (j // cols) * h + 5), f'{t:6.2f}s  {lab}', fill=(255, 220, 80))
        path = os.path.join(OUT, f'sheet_{p // per + 1}.jpg')
        sheet.save(path, quality=85)
        print('wrote', path)


def cmd_video(cfg_path, fps=FPS, draft=False, res='720p'):
    import subprocess
    from multiprocessing import Pool
    import imageio_ffmpeg
    wav = os.path.join(OUT, 'music.wav')
    if not os.path.exists(wav):
        cmd_music()
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    n = int(TL.DUR * fps)
    name = C.CFG.get('output_name', 'brand_film') + f'_{C.OUT_H}p' + ('_draft' if draft else '')
    out = os.path.join(OUT, name + '.mp4')
    cmd = [ff, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{C.OUT_W}x{C.OUT_H}', '-r', str(fps), '-i', '-', '-i', wav,
           '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'veryfast' if draft else 'slow',
           '-crf', '26' if draft else '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
           '-movflags', '+faststart', '-shortest', out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    t0 = time.time()
    procs = max(1, (os.cpu_count() or 2) - 1)
    with Pool(procs, initializer=_init_worker, initargs=(cfg_path, fps, res)) as pool:
        for k, buf in enumerate(pool.imap(_render, range(n), chunksize=2)):
            proc.stdin.write(buf)
            if k % (fps * 5) == 0:
                print(f'  frame {k}/{n}  {time.time() - t0:.0f}s', flush=True)
    proc.stdin.close()
    proc.wait()
    print('wrote', out, f'{C.OUT_W}x{C.OUT_H} @ {fps}fps', f'({time.time() - t0:.0f}s)')
    return out


def cmd_music():
    import bf_music
    rep = bf_music.build(TL, os.path.join(OUT, 'music.wav'), nostalgia())
    print('\n'.join(rep))
    print('wrote', os.path.join(OUT, 'music.wav'))


def cmd_doctor():
    ok = True
    for mod in ('numpy', 'PIL', 'imageio_ffmpeg'):
        try:
            __import__(mod)
            print('ok  ', mod)
        except ImportError:
            ok = False
            print('MISSING', mod, '-> pip install numpy pillow imageio-ffmpeg')
    try:
        import imageio_ffmpeg
        print('ok   ffmpeg', imageio_ffmpeg.get_ffmpeg_exe())
    except Exception as e:
        ok = False
        print('MISSING ffmpeg', e)
    for k, p in detect_fonts().items():
        print('font', k, p)
    missing = {'b', 'r', 'l', 'en', 'enl'} - set(detect_fonts())
    if missing:
        print('fonts not found for', missing, '-> set "fonts" in film.json (CJK needs a CJK font such as Noto Sans CJK)')
    print('cpu', os.cpu_count())
    return ok


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'doctor':
        sys.exit(0 if cmd_doctor() else 1)
    cfg = sys.argv[2]
    setup(cfg)
    fps = FPS
    if '--fps' in sys.argv:
        fps = int(sys.argv[sys.argv.index('--fps') + 1])
    draft = '--draft' in sys.argv
    res = C.set_resolution(sys.argv[sys.argv.index('--res') + 1] if '--res' in sys.argv
                           else C.CFG.get('resolution', '1080p'))
    if draft and '--fps' not in sys.argv:
        fps = 12
    if cmd in ('validate', 'all'):
        print(TL.summary())
        errs = TL.validate()
        for e in errs:
            print('ERROR:', e)
        if errs:
            sys.exit(2)
    if cmd in ('music', 'all'):
        cmd_music()
    if cmd == 'stills':
        os.makedirs(os.path.join(OUT, 'stills'), exist_ok=True)
        for tt in [float(x) for x in sys.argv[3].split(',')]:
            p = os.path.join(OUT, 'stills', f's_{tt:06.2f}.jpg')
            Image.fromarray(C.to_output(frame_at(int(round(tt * FPS))))).save(p, quality=90)
            print('wrote', p)
    if cmd in ('sheet', 'all'):
        cmd_sheet()
    if cmd in ('video', 'all'):
        cmd_video(cfg, fps, draft, res)


if __name__ == '__main__':
    main()
