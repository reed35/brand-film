"""Scene library. Part 1 = narrative scenes (crossfaded), Part 2 = kinetic sections (hard cuts on bars).
Every scene is a pure function of time and returns a Frame."""
import importlib.util
import math
import os

import numpy as np
from PIL import Image, ImageDraw

from bf_core import *
import bf_core as C

TL = None
KT = np.array([0.0])


def set_timeline(tl):
    global TL, KT
    TL = tl
    KT = np.array(tl.kick_times or [0.0])


def pulse(t, decay=9.0):
    i = np.searchsorted(KT, t, side='right') - 1
    return 0.0 if i < 0 else math.exp(-(t - KT[i]) * decay)


def is_latin(s):
    return all(ord(ch) < 0x2E80 for ch in s)


def kb(s):
    return 'en' if is_latin(s) else 'b'


def kl(s):
    return 'enl' if is_latin(s) else 'l'


# ======================================================================
# ICONS: line art in unit space [-1,1], drawn with a stroke-reveal
# ======================================================================
def _circ(cx, cy, r, a0=0, a1=math.tau, n=40):
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(a0, a1, n)]


def _rrect(x0, y0, x1, y1, r=.12, n=6):
    p = []
    for (cx, cy, a) in ((x1 - r, y0 + r, -math.pi / 2), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, math.pi / 2),
                        (x0 + r, y0 + r, math.pi)):
        p += [(cx + r * math.cos(a + i * math.pi / 2 / n), cy + r * math.sin(a + i * math.pi / 2 / n)) for i in range(n + 1)]
    return p + p[:1]


def _petal(a, r0=.14, r1=.78, w=.5):
    pts = [(r0 + (r1 - r0) * s, w * math.sin(math.pi * s) * .55) for s in np.linspace(0, 1, 12)]
    pts += [(r0 + (r1 - r0) * s, -w * math.sin(math.pi * s) * .2) for s in np.linspace(1, 0, 12)]
    return [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)) for x, y in pts]


def icon_strokes(name, t=0.0):
    rot = t
    I = {
        'fan': lambda: [_circ(0, -.2, .8)] + [[(x, y - .2) for x, y in _petal(rot * 4 + i * math.tau / 3)] for i in range(3)]
        + [[(0, .6), (0, 1.0)], [(-.45, 1.0), (.45, 1.0)]],
        'ac': lambda: [_rrect(-1, -.55, 1, .15, .15), [(-.8, -.05), (.8, -.05)]]
        + [[(-.5 + i * .5, .35), (-.6 + i * .5 + .05 * math.sin(rot * 3 + i), .8)] for i in range(3)],
        'bulb': lambda: [_circ(0, -.25, .6, math.radians(130), math.radians(410)),
                         [(-.3, .3), (-.3, .6), (.3, .6), (.3, .3)], [(-.22, .75), (.22, .75)], [(-.12, .9), (.12, .9)]],
        'house': lambda: [[(-.85, 1), (-.85, -.1), (0, -.9), (.85, -.1), (.85, 1), (-.85, 1)],
                          [(-.25, 1), (-.25, .35), (.25, .35), (.25, 1)]],
        'gear': lambda: [[(math.cos(a) * (.8 if (int((a - rot) / (math.tau / 20)) % 2) else .62),
                           math.sin(a) * (.8 if (int((a - rot) / (math.tau / 20)) % 2) else .62))
                          for a in np.linspace(rot, rot + math.tau, 161)], _circ(0, 0, .28)],
        'chip': lambda: [_rrect(-.6, -.6, .6, .6, .08), _rrect(-.3, -.3, .3, .3, .04)]
        + [[(x, -.6), (x, -.9)] for x in (-.35, 0, .35)] + [[(x, .6), (x, .9)] for x in (-.35, 0, .35)]
        + [[(-.6, y), (-.9, y)] for y in (-.35, 0, .35)] + [[(.6, y), (.9, y)] for y in (-.35, 0, .35)],
        'phone': lambda: [_rrect(-.48, -.95, .48, .95, .14), [(-.15, -.8), (.15, -.8)], _circ(0, .75, .07)],
        'car': lambda: [[(-1, .35), (-1, 0), (-.7, -.05), (-.4, -.45), (.35, -.45), (.65, -.05), (1, 0), (1, .35),
                         (-1, .35)], _circ(-.55, .4, .2), _circ(.55, .4, .2)],
        'globe': lambda: [_circ(0, 0, .9), [(-.9, 0), (.9, 0)], [(-.78, -.45), (.78, -.45)], [(-.78, .45), (.78, .45)]]
        + [[(.9 * math.sin(a) * math.cos(rot + k), -.9 * math.cos(a)) for a in np.linspace(0, math.pi, 30)]
           for k in (0, 1.05, 2.1)],
        'leaf': lambda: [[(-.8, .8)] + [(-.8 + 1.6 * s, .8 - 1.6 * s + .55 * math.sin(math.pi * s)) for s in np.linspace(0, 1, 20)]
                         + [(-.8 + 1.6 * s, .8 - 1.6 * s - .55 * math.sin(math.pi * s)) for s in np.linspace(1, 0, 20)],
                         [(-.8, .8), (.6, -.6)]],
        'box': lambda: [[(0, -.9), (.85, -.45), (0, 0), (-.85, -.45), (0, -.9)], [(-.85, -.45), (-.85, .5), (0, .95), (0, 0)],
                        [(0, .95), (.85, .5), (.85, -.45)]],
        'cup': lambda: [[(-.6, -.2), (-.5, .8), (.5, .8), (.6, -.2), (-.6, -.2)], _circ(.72, .2, .22, -math.pi / 2, math.pi / 2)]
        + [[(-.25 + .25 * i + .08 * math.sin(y * 8 + rot * 3), y) for y in np.linspace(-.35, -.9, 8)] for i in range(3)],
        'plane': lambda: [[(-1, 0), (-.2, -.05), (.3, -.7), (.45, -.7), (.2, -.05), (.85, -.02), (1, -.2), (1.05, 0),
                           (1, .2), (.85, .02), (.2, .05), (.45, .7), (.3, .7), (-.2, .05), (-1, 0)]],
        'heart': lambda: [[(.9 * 16 * math.sin(a) ** 3 / 16, -.9 * (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a)
                                                                      - math.cos(4 * a)) / 16 + .05) for a in np.linspace(0, math.tau, 60)]],
        'chart': lambda: [[(-.9, -.9), (-.9, .9), (.9, .9)], [(-.7, .5), (-.25, .1), (.1, .3), (.75, -.6)],
                          [(.45, -.6), (.75, -.6), (.75, -.3)]],
        'bolt': lambda: [[(.15, -1), (-.55, .1), (-.05, .1), (-.2, 1), (.55, -.15), (.05, -.15), (.15, -1)]],
        'battery': lambda: [_rrect(-.9, -.45, .75, .45, .1), [(.75, -.18), (.95, -.18), (.95, .18), (.75, .18)]]
        + [[(-.65 + i * .35, -.25), (-.65 + i * .35, .25)] for i in range(int(1 + (rot * 2) % 4))],
        'screen': lambda: [_rrect(-1, -.75, 1, .45, .06), [(-.3, .45), (-.4, .85), (.4, .85), (.3, .45)]],
        'cart': lambda: [[(-1, -.7), (-.7, -.7), (-.45, .35), (.7, .35), (.9, -.4), (-.6, -.4)], _circ(-.3, .65, .13),
                         _circ(.55, .65, .13)],
        'factory': lambda: [[(-1, .9), (-1, -.1), (-.45, -.45), (-.45, -.1), (.1, -.45), (.1, -.1), (.65, -.45), (.65, -.9),
                             (.9, -.9), (.9, .9), (-1, .9)]] + [[(-.7 + i * .45, .35), (-.5 + i * .45, .35)] for i in range(3)],
        'drop': lambda: [[(0, -1)] + [(.62 * math.sin(a), .25 - .62 * math.cos(a)) for a in np.linspace(.6, math.tau - .6, 30)] + [(0, -1)]],
        'star': lambda: [[(math.cos(-math.pi / 2 + i * math.pi / 5) * (.95 if i % 2 == 0 else .4),
                           math.sin(-math.pi / 2 + i * math.pi / 5) * (.95 if i % 2 == 0 else .4)) for i in range(11)]],
        'wifi': lambda: [_circ(0, .7, r, math.radians(-135), math.radians(-45), 20) for r in (.4, .8, 1.2)] + [_circ(0, .7, .06)],
        'pill': lambda: [_rrect(-.9, -.38, .9, .38, .38, 8), [(0, -.38), (0, .38)]],
        'book': lambda: [[(0, -.6), (-.95, -.8), (-.95, .7), (0, .9), (.95, .7), (.95, -.8), (0, -.6), (0, .9)]],
        'fridge': lambda: [_rrect(-.55, -1, .55, 1, .1), [(-.55, -.3), (.55, -.3)], [(.35, -.75), (.35, -.5)],
                           [(.35, -.1), (.35, .3)]],
        'washer': lambda: [_rrect(-.85, -.9, .85, .9, .1), [(-.85, -.55), (.85, -.55)], _circ(0, .2, .45),
                           [(0, .2), (.35 * math.cos(rot * 5), .2 + .35 * math.sin(rot * 5))]],
        'robot': lambda: [[(-.8, .95), (.2, .95)], [(-.3, .95), (-.3, .6), (-.55, -.15), (.35, -.6), (.75, -.25)],
                          _circ(-.3, .6, .12), _circ(-.55, -.15, .12), _circ(.35, -.6, .1)],
        'spark': lambda: [[(0, -1), (0, 1)], [(-1, 0), (1, 0)], [(-.6, -.6), (.6, .6)], [(-.6, .6), (.6, -.6)], _circ(0, 0, .3)],
        'wind': lambda: [[(-1, y) for y in (0,)] + [(x, -.4 + .15 * math.sin(x * 3 + rot * 3)) for x in np.linspace(-1, .8, 20)],
                         [(x, .1 + .15 * math.sin(x * 3 + rot * 3 + 1)) for x in np.linspace(-.9, 1, 20)],
                         [(x, .6 + .15 * math.sin(x * 3 + rot * 3 + 2)) for x in np.linspace(-1, .6, 20)]],
        'cap': lambda: [_circ(0, -.3, .75, 0, math.tau, 48), [(-.75, -.3), (-.75, .25)], [(.75, -.3), (.75, .25)],
                        _circ(0, .25, .75, 0, math.pi, 30)] + [[(.75 * math.cos(a), -.3 + .27 * math.sin(a)),
                                                                (.75 * math.cos(a), .25 + .27 * math.sin(a))]
                                                               for a in np.linspace(.2, math.pi - .2, 9)],
    }
    return I.get(name, I['spark'])()


ICONS = ['fan', 'ac', 'bulb', 'house', 'gear', 'chip', 'phone', 'car', 'globe', 'leaf', 'box', 'cup', 'plane', 'heart',
         'chart', 'bolt', 'battery', 'screen', 'cart', 'factory', 'drop', 'star', 'wifi', 'pill', 'book', 'fridge', 'washer',
         'robot', 'spark', 'wind', 'cap']


def draw_icon(cv, lv, name, cx, cy, size, reveal=1.0, col=(255, 255, 255), glow=(255, 200, 140), width=4, t=0.0, galpha=.35):
    strokes = [[(cx + x * size, cy + y * size) for x, y in s] for s in icon_strokes(name, t)]
    lens = [sum(math.dist(a, b) for a, b in zip(s, s[1:])) for s in strokes]
    total = sum(lens) * clamp(reveal)
    for s, L in zip(strokes, lens):
        if total <= 0:
            break
        if total >= L:
            part = s
        else:
            part, acc = [s[0]], 0
            for a, b in zip(s, s[1:]):
                d = math.dist(a, b)
                if acc + d >= total:
                    f = (total - acc) / max(d, 1e-6)
                    part.append((lerp(a[0], b[0], f), lerp(a[1], b[1], f)))
                    break
                part.append(b)
                acc += d
        total -= L
        cv.line(part, rgba(col, 1), width)
        if lv is not None:
            lv.line(part, rgba(glow, galpha), width * 2.5)


# ======================================================================
# PART 1
# ======================================================================
DUST = rnd(1).uniform(0, 1, (160, 5))
WINDL = rnd(5).uniform(0, 1, (46, 4))


def cool_at(t):
    """0 = warm nostalgic, 1 = cool/brand, across part 1"""
    wu = CFG.get('grade', {}).get('warm_until', TL.T2 * .7)
    return sstep(0, wu, t)


def room_bg(t, gx=960, gy=500, pw=1.0):
    c = cool_at(t)
    warm_top, warm_bot, warm_gl = (60, 38, 24), (22, 14, 8), (170, 110, 60)
    deep = PAL['deep']
    cool_top = mix(deep, (255, 255, 255), .1)
    cool_bot = mix(deep, (0, 0, 0), .7)
    cool_gl = mix(deep, (255, 255, 255), .45)
    return grad_bg(lerpc(warm_top, cool_top, c), lerpc(warm_bot, cool_bot, c),
                   ((gx, gy, 900, lerpc(warm_gl, cool_gl, c), .55 * pw),))


def tone(t):
    """(text color, highlight, glow) for part-1 scenes"""
    c = cool_at(t)
    return (lerpc((255, 232, 196), PAL['text_light'], c), lerpc(PAL['warm'], PAL['accent'], c),
            lerpc((255, 190, 120), mix(PAL['accent'], (255, 255, 255), .3), c))


def sc_origin(s, t):
    t0 = TL.b1(s['bar0'])
    lt = t - t0
    dur = s['bars'] * TL.BAR1
    on = max(clamp((lt - .6) / .25) * (0.85 + 0.15 * math.sin(lt * 37) * (1 - sstep(1, 2, lt))), sstep(1.5, 2.2, lt))
    fr = Frame(grad_bg((22, 13, 7), (6, 4, 2), ((960, 250, 820, (120, 70, 25), .9 * on),)))
    z = lerp(1.0, 1.14, ease_io(lt / dur))
    cv, lv = fr.cv(z=z, cx=960, cy=620), fr.lv(z=z, cx=960, cy=620)
    sway = 14 * math.sin(lt * 1.05)
    bx, by = 960 + sway, 250
    for i in range(6):
        sp = 170 + i * 70
        cv.poly([(bx - 16, by + 10), (bx + 16, by + 10), (bx + sp * 1.9, 900), (bx - sp * 1.9, 900)],
                fill=rgba((255, 190, 110), .035 * on))
    cv.line([(960, -200), (bx, by - 26)], (40, 30, 20, 255), 3)
    cv.rect(bx - 12, by - 36, bx + 12, by - 14, fill=(60, 48, 34, 255))
    cv.ellipse(bx, by, 24, 28, fill=rgba(lerpc((70, 50, 30), (255, 244, 214), on), 1))
    lv.ellipse(bx, by, 60, 60, fill=rgba((255, 200, 120), on))
    lv.ellipse(bx, by, 200, 200, fill=rgba((255, 160, 70), .35 * on))
    cv.rect(-400, 770, 2400, 1500, fill=(34, 21, 12, 255))
    cv.rect(-400, 770, 2400, 782, fill=rgba((150, 100, 55), .9 * on + .1))
    for i in range(7):
        cv.line([(-400, 810 + i * 38), (2400, 816 + i * 38)], rgba((55, 35, 20), .9), 2)
    icon = s.get('icon', 'spark')
    draw_icon(cv, lv, icon, 960, 690, 70, reveal=ease_io((lt - 1.2) / 1.6), col=lerpc((120, 90, 60), (255, 236, 205), on),
              glow=(255, 190, 120), width=4, t=lt * .3, galpha=.4 * on)
    for (u, v, sp, ph, sz) in DUST:
        x = (u * 1400 + 260 + math.sin(lt * .3 + ph * 9) * 40) % 1920
        y = (v * 620 + 260 - lt * (6 + sp * 10)) % 620 + 260
        inside = clamp(1 - abs(x - bx) / (80 + (y - by) * .9))
        a = inside * on * (.25 + .6 * (0.5 + .5 * math.sin(lt * 2 + ph * 20)))
        if a > .03:
            cv.ellipse(x, y, 1.2 + sz * 2.2, fill=rgba((255, 225, 170), a))
    lines = [x for x in (s.get('place'), s.get('title')) if x]
    caption(fr, t, t0 + 1.2, t0 + dur + .2, s.get('year', ''), lines, x=170, y=380, ycol=PAL['warm'],
            lcol=(255, 232, 196), big=150)
    side = s.get('side', [])
    a = win(t, t0 + dur * .45, t0 + dur + .2, .8, .6)
    for i, ln in enumerate(side[:2]):
        fr.text(ln, 1750, 400 + i * 62, 44 if i == 0 else 34, (255, 232, 196), a * (1 if i == 0 else .8), key='b' if i == 0 else 'r',
                anchor='r', track=.06)
    return fr


def sc_milestone(s, t):
    t0 = TL.b1(s['bar0'])
    lt = t - t0
    dur = s['bars'] * TL.BAR1
    items = s.get('items') or [s]
    n = len(items)
    seg = dur / n
    k = min(n - 1, int(lt // seg))
    it = items[k]
    llt = lt - k * seg
    p = pulse(t)
    tc, hl, gl = tone(t)
    fr = Frame(room_bg(t, 1180, 500, 1 + .3 * p))
    z = lerp(1.05, 1.0, ease_out(lt / 3)) + p * .005
    cv, lv = fr.cv(z=z), fr.lv(z=z)
    flow = s.get('flow', 'wind')
    for (u, v, sp, ph) in WINDL:
        if flow == 'wind':
            y0 = 260 + u * 560
            xh = 1180 - ((lt * (500 + sp * 500) + ph * 1600) % 1500)
            pts = [(x, y0 + 30 * math.sin(x / 130 + ph * 6 + lt * 2)) for x in range(int(xh), int(xh) + 260, 26)]
        elif flow == 'rise':
            x0 = 700 + u * 1000
            yh = 1000 - ((lt * (200 + sp * 200) + ph * 900) % 900)
            pts = [(x0 + 12 * math.sin(y / 60 + ph * 5), y) for y in range(int(yh), int(yh) + 90, 15)]
        elif flow == 'orbit':
            a0 = lt * (.6 + sp * .5) + ph * 6.28
            R = 330 + u * 120
            pts = [(1180 + R * math.cos(a0 + i * .05), 480 + R * .45 * math.sin(a0 + i * .05)) for i in range(10)]
        else:
            continue
        a = sstep(0, 1.5, lt) * (.12 + .12 * v)
        cv.line(pts, rgba(tc, a), 2.2)
        lv.line(pts, rgba(gl, a * 1.2), 3)
    ic_x, ic_y, size = 1180, 470, 240
    ring = ease_out((llt - .1) / .9)
    cv.ellipse(ic_x, ic_y, 360 * ring, outline=rgba(tc, .12), width=1.5)
    cv.ellipse(ic_x, ic_y, (300 + 10 * p) * ring, outline=rgba(hl, .25), width=1.5)
    lv.ellipse(ic_x, ic_y, 330, fill=rgba(gl, .10 + .06 * p))
    rev = ease_io((llt - .15) / 1.1)
    if k > 0 and llt < .4:
        draw_icon(cv, lv, items[k - 1].get('icon', 'spark'), ic_x, ic_y, size, 1 - llt / .4, tc, gl, 5, lt)
    draw_icon(cv, lv, it.get('icon', 'spark'), ic_x, ic_y, size * (1 + .02 * p), rev, tc, gl, 5, lt)
    cnt = it.get('counter')
    if cnt:
        v = lerp(cnt['from'], cnt['to'], ease_io((llt - .6) / (seg * .6)))
        txt = f"{v:.{cnt.get('decimals', 0)}f}{cnt.get('suffix', '')}"
        fr.text(txt, 150, 860, 180, hl, sstep(.4, 1.0, llt) * (1 - sstep(seg - .5, seg, llt) * (k < n - 1)), key='enl',
                anchor='l', shadow=.4)
    caption(fr, t, t0 + k * seg + .3, t0 + (k + 1) * seg + (.2 if k == n - 1 else -.1), it.get('year', ''),
            [x for x in (it.get('title'), it.get('sub')) if x], x=150, y=330, ycol=hl, lcol=tc)
    return fr


CITY = []
_r = rnd(21)
_x = -2700
while _x < 4600:
    w = _r.uniform(260, 620)
    h = _r.uniform(700, 2400) * (1.0 if abs(_x - 960) > 700 else 0)
    if h > 0:
        CITY.append((_x, w, h, _r.uniform(0, 1)))
    _x += w + _r.uniform(30, 140)
GROUND = 1400
STARS = rnd(22).uniform(0, 1, (220, 3))
CARS = rnd(23).uniform(0, 1, (90, 3))


def _building(cv, lv, x0, w, h, t, t_on, seed, detail, tint, warmc, coolc):
    top = GROUND - h
    cv.rect(x0, top, x0 + w, GROUND, fill=lerpc((16, 22, 38), (22, 34, 60), tint) + (255,))
    cw, ch = 50, 58
    cols = max(1, int((w - 40) // cw))
    rows = int((h - 40) // ch)
    ox = x0 + (w - cols * cw) / 2
    rand = rnd(seed).uniform(0, 1, (rows, cols))
    for r_ in range(rows):
        y = top + 30 + r_ * ch
        for c in range(cols):
            x = ox + c * cw
            lit = t_on + math.hypot(x + 15 - 958, y + 18 - 540) * .0016 + rand[r_, c] * 1.6 + (4 if rand[r_, c] < .12 else 0)
            s = clamp((t - lit) / .35)
            col = lerpc(coolc, warmc, clamp(1 - (lit - t_on - .3) / 5.5))
            if s > 0:
                cv.rect(x + 8, y + 10, x + 38, y + 46, fill=rgba(col, .25 + .75 * s))
                if detail > .5 and s > .5 and rand[r_, c] > .55:
                    lv.rect(x + 2, y + 4, x + 44, y + 52, fill=rgba(col, .35))
            else:
                cv.rect(x + 8, y + 10, x + 38, y + 46, fill=(28, 36, 54, 255))


def sc_city(s, t):
    t0 = TL.b1(s['bar0'])
    lt = t - t0
    dur = s['bars'] * TL.BAR1
    p = pulse(t)
    deep = PAL['deep']
    fr = Frame(grad_bg(mix(deep, (0, 0, 0), .75), mix(deep, (0, 0, 0), .25), ((960, 1000, 1400, mix(deep, (255, 255, 255), .3), .6),)))
    zA = math.exp(lerp(math.log(42.0), 0, ease_out(lt / (dur * .45))))
    zB = math.exp(lerp(0, math.log(.30), ease_io((lt - dur * .4) / (dur * .5))))
    z = zA * zB
    cy = lerp(540, 150, ease_io((lt - dur * .36) / (dur * .56)))
    cv, lv = fr.cv(z=z, cx=958, cy=cy), fr.lv(z=z, cx=958, cy=cy)
    warmc = (255, 200, 120)
    coolc = mix(PAL['text_light'], mix(PAL['accent'], (255, 255, 255), .5), .3)
    for u, v, s_ in STARS:
        cv.ellipse(u * 1920 * 4 - 2900, v * 1500 - 1500, 2 + s_ * 3, fill=rgba((200, 220, 255), .3 + .4 * s_))
    if z < .9:
        for x0, w, h, sd in CITY:
            _building(cv, lv, x0, w, h, t, t0 + 1.2, int(sd * 1e6), z, sd, warmc, coolc)
    _building(cv, lv, 658, 600, 1672, t, t0 + 1.2, 77, 1, 0, warmc, coolc)
    cv.rect(943, 522, 973, 558, fill=mix(deep, (255, 255, 255), .2) + (255,))
    lv.rect(928, 504, 988, 576, fill=rgba(coolc, .8 * min(1, 2.5 / z)))
    cv.rect(-4000, GROUND, 6000, 3000, fill=(6, 10, 20, 255))
    for u, v, s_ in CARS:
        lane = int(v * 4)
        y = GROUND + 30 + lane * 36
        d = 1 if lane % 2 else -1
        x = ((u * 8000 + d * lt * (600 + s_ * 500)) % 8000) - 3000
        col = (255, 90, 70) if d > 0 else (255, 240, 210)
        cv.line([(x, y), (x - d * 160, y)], rgba(col, .7), 8)
        lv.line([(x, y), (x - d * 160, y)], rgba(col, .7), 10)
    lv.rect(-4000, GROUND - 60, 6000, GROUND + 200, fill=rgba(mix(deep, (255, 255, 255), .4), .25 + .15 * p))
    caption(fr, t, t0 + 1.2, t0 + dur * .5, s.get('year', ''), [x for x in (s.get('title'), s.get('sub')) if x], x=150, y=640,
            ycol=mix(PAL['accent'], (255, 255, 255), .3), lcol=(255, 255, 255))
    if s.get('text'):
        center_title(fr, t, t0 + dur * .5 + .5, t0 + dur + .2, s['text'], y=880, size=76, col=(255, 255, 255), track=.16)
    return fr


def sc_network(s, t):
    t0 = TL.b1(s['bar0'])
    lt = t - t0
    dur = s['bars'] * TL.BAR1
    p = pulse(t)
    deep, acc, lt_c = PAL['deep'], PAL['accent'], PAL['text_light']
    fr = Frame(grad_bg(mix(deep, (0, 0, 0), .3), mix(deep, (0, 0, 0), .8), ((1060, 520, 1000, mix(deep, (255, 255, 255), .15),
                                                                              .55 + .12 * p),)))
    z = lerp(1.06, 1.0, ease_out(lt / 3)) + .02 * ease_io((lt - 3) / 7)
    cv, lv = fr.cv(z=z, cx=960, cy=540), fr.lv(z=z, cx=960, cy=540)
    ga = sstep(0, 1.2, lt)
    for x in range(-240, 2200, 96):
        cv.line([(x, -300), (x, 1400)], rgba(PAL['muted'], .06 * ga), 1)
    for y in range(-288, 1400, 96):
        cv.line([(-300, y), (2200, y)], rgba(PAL['muted'], .06 * ga), 1)
    hub = (1160, 540)
    for i, r in enumerate((150, 300, 450, 640)):
        cv.ellipse(*hub, r + 6 * p, outline=rgba(acc, (.18 - i * .035) * sstep(.6, 1.6, lt)), width=1)
    nodes = s.get('nodes', [])
    n = max(1, len(nodes))
    for i, nd in enumerate(nodes):
        name, icon = (nd, 'spark') if isinstance(nd, str) else (nd.get('label', ''), nd.get('icon', 'spark'))
        a = -math.pi / 2 + i * math.tau / n + lt * .05
        x, y = hub[0] + 420 * math.cos(a), hub[1] + 330 * math.sin(a)
        t_in = 1.0 + i * TL.BEAT1 * .5
        sv = ease_out((lt - t_in) / .5)
        if sv <= 0:
            continue
        la = sstep(t_in + .2, t_in + .9, lt)
        mid = ((x + hub[0]) / 2 + (y - hub[1]) * .18, (y + hub[1]) / 2 - (x - hub[0]) * .18)
        bez = lambda u, x=x, y=y, mid=mid: ((1 - u) ** 2 * x + 2 * (1 - u) * u * mid[0] + u * u * hub[0],
                                            (1 - u) ** 2 * y + 2 * (1 - u) * u * mid[1] + u * u * hub[1])
        cv.line([bez(u) for u in np.linspace(0, la, 18)], rgba(acc, .45), 1.2)
        for kk in range(3):
            u = (lt * .9 + kk / 3 + i * .13) % 1
            if u < la:
                px, py = bez(u)
                cv.ellipse(px, py, 3.5, fill=rgba(mix(acc, (255, 255, 255), .3), .95))
                lv.ellipse(px, py, 10, fill=rgba(acc, .6))
        cv.ellipse(x, y, 62 * sv, fill=rgba(mix(deep, (0, 0, 0), .5), .9), outline=rgba(lt_c, .35), width=1)
        draw_icon(cv, lv, icon, x, y, 34 * sv, ease_io((lt - t_in) / .8), lt_c, acc, 2.2, lt, .18)
        fr.text(name, *cv.sp(x, y + 88), 22, PAL['muted'], sv * .95, key='r', anchor='m', track=.25, shadow=0)
    ha = sstep(.6, 1.3, lt)
    hx, hy = cv.sp(*hub)
    fr.mat(circle_pts(hx, hy, 70 * z * (.9 + .1 * ha)), 'accent', sheen=.2 + .3 * math.sin(lt), shadow=0, alpha=ha)
    lv.ellipse(*hub, 150, fill=rgba(acc, .3 * ha))
    hl = s.get('hub', '')
    if hl:
        fr.text(hl, hx, hy, 34 if len(hl) <= 2 else 24, on_color(acc), ha, key=kb(hl), anchor='m', shadow=0)
    mid_t = t0 + dur * .5
    caption(fr, t, t0 + .5, mid_t, s.get('year', ''), [x for x in (s.get('title'), s.get('sub')) if x], x=110, y=200,
            ycol=mix(acc, (255, 255, 255), .25), lcol=lt_c)
    l2 = s.get('lines2', [])
    if l2:
        caption(fr, t, mid_t + .2, t0 + dur + .3, '', l2, x=110, y=240, lcol=lt_c)
    return fr


def sc_bridge(s, t):
    t0 = TL.b1(s['bar0'])
    lt = t - t0
    dur = s['bars'] * TL.BAR1
    fr = Frame(grad_bg(mix(PAL['dark'], (255, 255, 255), .03), PAL['dark']))
    cv = fr.cv()
    for i, r in enumerate((180, 320, 520)):
        cv.ellipse(960, 540, r * (1 + .15 * lt), outline=rgba(PAL['accent'], .12 * (1 - sstep(0, dur * .6, lt))), width=1)
    r = lerp(70, 9, ease_io((lt - .2) / (dur * .7)))
    fr.mat(circle_pts(960, 540, r, 96), 'accent', shadow=0)
    fr.lv().ellipse(960, 540, 30 + r, fill=rgba(PAL['accent'], .4))
    if s.get('text'):
        fr.text(s['text'], 960, 690, 40, PAL['text_light'], win(t, t0 + .7, t0 + dur - .5, .8, .7), key=kl(s['text']),
                anchor='m', track=.5, shadow=0)
    return fr


_custom_cache = {}


def sc_custom(s, t):
    path = os.path.join(CFG['_dir'], s['module'])
    mod = _custom_cache.get(path)
    if mod is None:
        spec = importlib.util.spec_from_file_location('custom_' + str(len(_custom_cache)), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _custom_cache[path] = mod
    fn = getattr(mod, s.get('func', 'scene'))
    t0 = TL.b1(s['bar0']) if s in TL.p1 else TL.b2(s['bar0'])
    return fn(t, t - t0, s, TL)


PART1 = {'origin': sc_origin, 'milestone': sc_milestone, 'city': sc_city, 'network': sc_network, 'bridge': sc_bridge,
         'custom': sc_custom}


# ======================================================================
# PART 2
# ======================================================================
def hud(fr, t, bg):
    t2 = t - TL.T2
    bar = min(TL.n2 - 1, int(t2 // TL.BAR2))
    beat = int((t2 % TL.BAR2) // TL.BEAT2)
    col = mix(on_color(bg), bg, .45)
    cv = fr.cv()
    for (x, y, sx, sy) in ((40, 40, 1, 1), (1880, 40, -1, 1), (40, 1040, 1, -1), (1880, 1040, -1, -1)):
        cv.line([(x, y + sy * 26), (x, y), (x + sx * 26, y)], rgba(col, .8), 1.5)
    name = CFG.get('hud_name', CFG.get('company', '')).upper()
    fr.text(f'{name}   ·   PART II', 66, 46, 15, col, .9, key='r', anchor='l', track=.25, shadow=0)
    fr.text(f'BAR {bar + 1:02d} / {TL.n2:02d}     {TL.bpm2:.0f} BPM', 1790, 46, 15, col, .9, key='r', anchor='r', track=.25, shadow=0)
    for i in range(4):
        cv.rect(1804 + i * 16, 40, 1814 + i * 16, 52, fill=rgba(col, .95 if i == beat else .25))
    f = int(round(t * FPS))
    fr.text(f'F{f:05d}    00:{int(t) // 60:02d}:{int(t) % 60:02d}:{f % FPS:02d}', 1854, 1034, 15, col, .9, key='r',
            anchor='r', track=.2, shadow=0)
    fr.text(CFG.get('years', ''), 66, 1034, 15, col, .9, key='r', anchor='l', track=.3, shadow=0)


def sec_dots(s, t):
    t2 = t - TL.b2(s['bar0'])
    B, BAR = TL.BEAT2, TL.BAR2
    bg = PAL['dark']
    fr = Frame(bg_for(bg, .3))
    cv, lv = fr.cv(), fr.lv()
    hb = B / 2
    n = min(8, 1 + int(t2 / hb))
    sv = ease_out((t2 - (n - 1) * hb) / .16) if n > 1 else 1
    rot = t2 * 1.4
    R = max(0, 18 * (n - 1) * sv + (18 * (n - 2) if n > 1 else 0) * (1 - sv)) + 150 * ease_io((t2 - BAR) / (B * 2.6))
    conv = ease_in((t2 - BAR - B * 2.6) / (B * .6))
    R *= 1 - conv
    guide = sstep(.3, 1.2, t2) * (1 - conv)
    mc = PAL['muted']
    cv.ellipse(960, 540, max(R, 1), outline=rgba(mc, .35 * guide), width=1)
    cv.line([(660, 540), (1260, 540)], rgba(mc, .18 * guide), 1)
    cv.line([(960, 240), (960, 840)], rgba(mc, .18 * guide), 1)
    sq = 260 + 40 * math.sin(t2)
    cv.line([(960 + sq * math.cos(t2 * .5 + i * math.pi / 2), 540 + sq * math.sin(t2 * .5 + i * math.pi / 2)) for i in range(5)],
            rgba(PAL['accent'], .22 * guide * sstep(1.8, 2.4, t2)), 1)
    fr.text(f'N = {n}', 960, 540 + R + 70, 16, mc, guide * .9, key='r', anchor='m', track=.3, shadow=0)
    for i in range(n):
        a = rot + (lerp(math.tau * min(i, n - 2) / (n - 1), math.tau * i / n, sv) if n > 1 else 0)
        x, y = 960 + R * math.cos(a), 540 + R * math.sin(a)
        fr.mat(circle_pts(x, y, 9 + 3 * pulse(t, 12), 40), 'accent', shadow=0)
        lv.ellipse(x, y, 26, fill=rgba(PAL['accent'], .35))
    fl = ease_in((t2 - BAR - B * 3.2) / (B * .8))
    if fl > 0:
        fr.mat(circle_pts(960, 540, 14 + fl * 1250, 160), 'accent', ang=-1.2, sheen=-.2, shadow=0)
    hud(fr, t, bg)
    return fr


def sec_slam(s, t):
    lt = t - TL.b2(s['bar0'])
    B, BAR = TL.BEAT2, TL.BAR2
    bg = PAL['accent']
    fr = Frame(bg_for(bg, .35))
    cv = fr.cv()
    tc = on_color(bg)
    hi = PAL['brand'] if abs(lum(PAL['brand']) - lum(bg)) > .3 else tc
    x_end = 250
    l1, box = s.get('line1', ''), s.get('box', '')
    n = len(l1 + box)
    if is_latin(l1 + box):
        size = int(clamp(1400 / (0.66 * n + 2.2), 80, 210))
    else:
        size = int(clamp(1400 / (n + 1.2), 90, 176))
    s1 = ease_out(lt / .2)
    fr.text(l1, lerp(1900, x_end, s1), 420, size, tc, 1, key=kb(l1), anchor='l', track=.04, shadow=0, mb=(1 - s1) * 90)
    w1 = text_width(l1, size, kb(l1), .04)
    a2 = sstep(B * 1.4, B * 1.6, lt)
    if box and a2 > 0:
        pop = 1 + .12 * (1 - ease_out((lt - B * 1.5) / .2))
        wb = text_width(box, size, kb(box), .04)
        cx2 = x_end + w1 + 90 + wb / 2
        fr.text(box, cx2, 420, size * pop, tc, a2, key=kb(box), anchor='m', track=.04, shadow=0)
        bw, bh, L = wb / 2 * pop + 28, size * .68 * pop, 34
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x, y = cx2 + sx * bw, 420 + sy * bh
            cv.line([(x, y - sy * L), (x, y), (x - sx * L, y)], rgba(tc, a2), 5)
    if lt >= BAR:
        s3 = ease_out((lt - BAR) / .2)
        l2a, l2b = s.get('line2a', ''), s.get('line2b', '')
        sz2 = int(size * .85)
        x3 = lerp(-900, x_end, s3)
        fr.text(l2a, x3, 680, sz2, tc, 1, key=kb(l2a), anchor='l', track=.04, shadow=0, mb=(1 - s3) * 90)
        w3 = text_width(l2a, sz2, kb(l2a), .04) if l2a else 0
        a4 = sstep(BAR + B * .9, BAR + B * 1.1, lt)
        fr.text(l2b, x3 + w3 + 30, 680, sz2, hi, a4, key=kb(l2b), anchor='l', track=.04, shadow=0,
                mb=(1 - ease_out((lt - BAR - B) / .18)) * 60)
    ra = ease_out((lt - .15) / .6)
    cv.line([(250, 232), (250 + 1400 * ra, 232)], rgba(tc, .8), 1.5)
    fr.text(s.get('label', ''), 252, 205, 17, tc, ra, key='r', anchor='l', track=.35, shadow=0)
    hud(fr, t, bg)
    return fr


TH = np.linspace(0, math.tau, 181)[:-1]


def r_super(a, b, n):
    return (np.abs(np.cos(TH) / a) ** n + np.abs(np.sin(TH) / b) ** n) ** (-1 / n)


def r_poly(verts):
    out = np.zeros_like(TH)
    V = np.array(verts, float)
    for j, th in enumerate(TH):
        d = (math.cos(th), math.sin(th))
        best = 1e9
        for i in range(len(V)):
            p, q = V[i], V[(i + 1) % len(V)]
            e = q - p
            den = d[0] * e[1] - d[1] * e[0]
            if abs(den) < 1e-9:
                continue
            tt = (p[0] * e[1] - p[1] * e[0]) / den
            u = (p[0] * d[1] - p[1] * d[0]) / den
            if tt > 0 and -1e-6 <= u <= 1 + 1e-6:
                best = min(best, tt)
        out[j] = best
    return out


def _ngon(n, r, a0):
    return [(r * math.cos(a0 + i * math.tau / n), r * math.sin(a0 + i * math.tau / n)) for i in range(n)]


RADIALS = [np.ones_like(TH), r_super(.92, .92, 6), r_poly(_ngon(3, 1.18, -math.pi / 2)), r_super(.62, 1.1, 6),
           r_super(.94, .94, 8), r_poly(_ngon(6, 1.05, 0)), r_poly([(-.85, .85), (.85, .85), (.85, -.12), (0, -.95), (-.85, -.12)]),
           .86 + .14 * np.cos(6 * TH)]
MATCYC = ['accent', 'metal', 'deep', 'light', 'metal', 'accent', 'metal', 'accent']


def sec_shapes(s, t):
    lt = t - TL.b2(s['bar0'])
    B, BAR = TL.BEAT2, TL.BAR2
    bg = PAL['dark']
    fr = Frame(bg_for(bg, .35))
    cv = fr.cv()
    items = s.get('items') or [['·', '']]
    k = min(7, int(lt // B))
    it = items[k % len(items)]
    e = ease_out_back((lt - k * B) / .24)
    e1 = ease_out((lt - k * B) / .3)
    prev = RADIALS[k - 1] if k > 0 else np.zeros_like(TH)
    r = prev + (RADIALS[k] - prev) * e
    rot = math.radians(90 * (k - 1) + 90 * e1) if k > 0 else 0
    cx, cy, R = 960, 540, 190
    mc = PAL['muted']
    for i in range(-8, 9):
        cv.line([(cx + i * 120, 0), (cx + i * 120, 1080)], rgba(mc, .05), 1)
    for i in range(-5, 6):
        cv.line([(0, cy + i * 120), (1920, cy + i * 120)], rgba(mc, .05), 1)
    cv.ellipse(cx, cy, R * 1.9, outline=rgba(mc, .14), width=1)
    cv.ellipse(cx, cy, R * 2.6, outline=rgba(PAL['accent'], .10), width=1)
    if e1 < 1 and k > 0:
        for g in (1, 2):
            ag = rot - math.radians(22 * g) * (1 - e1)
            pts = [(cx + R * rr * math.cos(th + ag), cy + R * rr * math.sin(th + ag)) for th, rr in zip(TH, r)]
            cv.line(pts + pts[:1], rgba(PAL['text_light'], .25 * (1 - e1) / g), 1.5)
    if k < 7:
        pts = [(cx + R * rr * math.cos(th + rot), cy + R * rr * math.sin(th + rot)) for th, rr in zip(TH, r)]
        fr.mat(pts, MATCYC[k], ang=-.9 + rot * .3, sheen=.1 + .35 * math.sin(lt * 3), shadow=.5)
        if k == 4:
            fr.mat(circle_pts(cx, cy, R * .52 * e1), 'accent', shadow=.3)
            fr.mat(circle_pts(cx, cy, R * .38 * e1), 'dark', sheen=.4, shadow=0)
    else:
        acc, accl = PAL['accent'], mix(PAL['accent'], (255, 255, 255), .35)

        def sunflower(base, lt=lt, e=e):
            d = ImageDraw.Draw(base, 'RGBA')
            for i in range(240):
                q = i / 240
                a = i * 2.39996 + lt * .6
                rr = R * .98 * math.sqrt(q) * (.86 + .14 * math.cos(6 * a)) * e
                x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
                sz = 5.5 * (1 - .4 * q)
                d.ellipse([x - sz, y - sz, x + sz, y + sz], fill=rgba(lerpc(accl, acc, q), 1))
        fr.post.append(sunflower)
    bs = R * 1.32
    cs = [(cx + bs * 1.414 * math.cos(rot + math.pi / 4 + i * math.pi / 2), cy + bs * 1.414 * math.sin(rot + math.pi / 4 + i * math.pi / 2))
          for i in range(4)]
    cv.line(cs + cs[:1], rgba(mc, .55), 1)
    for i in range(4):
        for p_ in (cs[i], ((cs[i][0] + cs[(i + 1) % 4][0]) / 2, (cs[i][1] + cs[(i + 1) % 4][1]) / 2)):
            cv.rect(p_[0] - 5, p_[1] - 5, p_[0] + 5, p_[1] + 5, fill=rgba(bg, 1), outline=rgba(mc, .9), width=1)
    fr.text(f'ROT  {math.degrees(rot) % 360:05.1f}°', 1350, 300, 16, mc, .95, key='r', anchor='l', track=.25, shadow=0)
    fr.text(f'SHAPE  {k + 1:02d}  ·  {it[1] if len(it) > 1 else ""}', 1350, 328, 16, PAL['accent'], .95, key='r', anchor='l',
            track=.25, shadow=0)
    ta = ease_out((lt - k * B) / .2)
    big = it[0]
    fr.text(big, 330, 520 + (1 - ta) * 30, 250 if len(big) <= 2 else 150, PAL['text_light'], .95 * ta, key=kl(big), anchor='m', shadow=0)
    if len(it) > 1:
        fr.text(it[1], 330, 700, 20, PAL['accent'], ta, key='r', anchor='m', track=.6, shadow=0)
    if s.get('caption'):
        fr.text(s['caption'], 1580, 800, 30, PAL['text_light'], sstep(BAR, BAR + .3, lt), key='b', anchor='r', track=.25, shadow=0)
    hud(fr, t, bg)
    return fr


GS, GC, GR = 48, 42, 24


def _snakes():
    rr = rnd(61)
    out = []
    for si in range(7):
        c, r_ = int(rr.integers(2, GC - 2)), int(rr.integers(2, GR - 2))
        d = [(1, 0), (0, 1), (-1, 0), (0, -1)][int(rr.integers(0, 4))]
        path = []
        for _ in range(260):
            for _ in range(int(rr.integers(4, 13))):
                c, r_ = c + d[0], r_ + d[1]
                if not (0 <= c < GC and 0 <= r_ < GR):
                    c, r_ = c - d[0], r_ - d[1]
                    break
                path.append((c, r_))
            d = (d[1], d[0]) if rr.uniform() < .5 else (-d[1], -d[0])
        out.append((path, si in (1, 4), float(rr.uniform(16, 26))))
    return out


SNAKES = _snakes()


def sec_grid(s, t):
    lt = t - TL.b2(s['bar0'])
    BAR = TL.BAR2
    bg = PAL['light']
    fr = Frame(bg_for(bg, .3))
    cv = fr.cv()
    tc = on_color(bg)
    dotc = mix(bg, tc, .55)
    hi = {}
    for path, acc, sp in SNAKES:
        head = int(lt * sp) + 20
        for j in range(16):
            idx = head - j
            if 0 <= idx < len(path):
                hi[path[idx]] = (PAL['accent'] if acc else (PAL['deep'] if abs(lum(PAL['deep']) - lum(bg)) > .3 else tc), 1 - j / 16)
    tilt = ease_io((lt - BAR) / (BAR * .55))
    a = math.radians(64 * tilt)
    ca, sa = math.cos(a), math.sin(a)
    last = KT[max(0, np.searchsorted(KT, t, side='right') - 1)]
    ring = (t - last) * 1500
    f = 1500
    for r_ in range(GR):
        for c in range(GC):
            X, Y = c * GS + 24 - 960, r_ * GS + 12 - 540
            h = math.sin(X * .008 + lt * 4.5) * 70 * tilt + math.cos(Y * .01 - lt * 3) * 30 * tilt
            Yr, Zr = Y * ca - h * sa, Y * sa + h * ca
            scl = f / (f + Zr + 1e-3)
            if scl <= 0:
                continue
            sx, sy = 960 + X * scl * (1 + .25 * tilt), 560 + Yr * scl + 40 * tilt
            if (80 < sx < 900 and 90 < sy < 280) or (80 < sx < 1100 and 935 < sy < 1010):
                continue
            boost = 1 + .9 * math.exp(-((math.hypot(X, Y) - ring) / 70) ** 2) * (1 - tilt)
            if (c, r_) in hi:
                col, w = hi[(c, r_)]
                cv.ellipse(sx, sy, (3.2 + 2.6 * w) * scl * boost, fill=rgba(col, .35 + .65 * w))
            else:
                cv.ellipse(sx, sy, 2.2 * scl * boost, fill=rgba(dotc, .55))
    title = s.get('title', '')
    s0 = ease_out(lt / .25)
    fr.text(title, 120, 160, 96, tc, s0, key=kb(title), anchor='l', track=.08, shadow=0, mb=(1 - ease_out(lt / .2)) * 60)
    fr.text(s.get('label', ''), 124, 250, 16, mix(PAL['accent'], (0, 0, 0), .25), ease_out((lt - .2) / .4), key='r', anchor='l',
            track=.35, shadow=0)
    subs = s.get('subs', [])
    if subs:
        fr.text(subs[0 if lt < BAR or len(subs) < 2 else 1], 120, 972, 32, mix(tc, bg, .25), 1, key='b', anchor='l', track=.12, shadow=0)
    hud(fr, t, bg)
    return fr


NP = 900
_q = np.arange(NP)
_phi = np.arccos(1 - 2 * (_q + .5) / NP)
_the = math.pi * (1 + 5 ** .5) * _q
SPHERE = np.stack([np.sin(_phi) * np.cos(_the), np.cos(_phi), np.sin(_phi) * np.sin(_the)], 1)
_u = _q / NP * math.tau
_v = (_q * .618034 * 29 % 1) * math.tau
TORUS = np.stack([(1 + .38 * np.cos(_v)) * np.cos(_u), .38 * np.sin(_v), (1 + .38 * np.cos(_v)) * np.sin(_u)], 1) * .85
_E = [((-1, -1, -1), (1, -1, -1)), ((-1, 1, -1), (1, 1, -1)), ((-1, -1, 1), (1, -1, 1)), ((-1, 1, 1), (1, 1, 1)),
      ((-1, -1, -1), (-1, 1, -1)), ((1, -1, -1), (1, 1, -1)), ((-1, -1, 1), (-1, 1, 1)), ((1, -1, 1), (1, 1, 1)),
      ((-1, -1, -1), (-1, -1, 1)), ((1, -1, -1), (1, -1, 1)), ((-1, 1, -1), (-1, 1, 1)), ((1, 1, -1), (1, 1, 1))]
CUBE = np.array([np.array(_E[i % 12][0]) + (np.array(_E[i % 12][1]) - np.array(_E[i % 12][0])) * ((i * .618034) % 1)
                 for i in range(NP)]) * .72
SCAT = rnd(71).normal(0, 2.4, (NP, 3))
STAG = (_q / NP) * .18


def sec_cloud(s, t):
    lt = t - TL.b2(s['bar0'])
    B, BAR = TL.BEAT2, TL.BAR2
    p = pulse(t)
    bg = PAL['deep']
    fr = Frame(bg_for(bg, .45 + .2 * p))
    cv, lv = fr.cv(), fr.lv()
    tc = on_color(bg)
    keys = [(0, SCAT), (.05, SPHERE), (B * 2, TORUS), (BAR, CUBE)]
    P = SCAT
    for (ta, A), (tb, Bq) in zip(keys, keys[1:]):
        if lt >= tb:
            sv = np.clip((lt - tb - STAG) / .42, 0, 1)
            sv = sv * sv * (3 - 2 * sv)
            P = A + (Bq - A) * sv[:, None]
    P = P * (1 + ease_in((lt - BAR - B * 3) / (B * .9)) * 5)
    yaw, pitch = lt * 1.1, .45 + .15 * math.sin(lt)
    x = P[:, 0] * math.cos(yaw) + P[:, 2] * math.sin(yaw)
    z = -P[:, 0] * math.sin(yaw) + P[:, 2] * math.cos(yaw)
    y = P[:, 1] * math.cos(pitch) - z * math.sin(pitch)
    z = P[:, 1] * math.sin(pitch) + z * math.cos(pitch)
    scl = 3.2 / np.maximum(3.2 + z, .05)
    sx, sy = 1060 + x * 330 * scl, 520 + y * 330 * scl
    pc = PAL['text_light'] if lum(bg) < .5 else PAL['text_dark']
    accl = mix(PAL['accent'], (255, 255, 255), .3)
    for i in np.argsort(-z):
        if not (-50 < sx[i] < 1970 and -50 < sy[i] < 1130):
            continue
        dep = clamp((1 - z[i]) / 2)
        gold = i % 17 == 0
        cv.ellipse(sx[i], sy[i], (1.3 + 2.4 * dep) * scl[i] ** .6, fill=rgba(accl if gold else pc, .35 + .6 * dep))
        if gold:
            lv.ellipse(sx[i], sy[i], 8, fill=rgba(PAL['accent'], .5))
    for i in range(3):
        ang = lt * (.4 + i * .15) + i
        pts = [(470 * math.cos(u), 470 * math.sin(u) * (.28 + .1 * i)) for u in np.linspace(0, math.tau, 90)]
        cv.line([(1060 + px * math.cos(ang) - py * math.sin(ang), 520 + px * math.sin(ang) + py * math.cos(ang)) for px, py in pts],
                rgba(PAL['accent'], .16), 1)
    title = s.get('title', '')
    s0 = ease_out(lt / .25)
    fr.text(title, 120, 820, 88, tc, s0, key=kb(title), anchor='l', track=.08, shadow=0, mb=(1 - s0) * 70)
    fr.text(s.get('label', ''), 124, 900, 16, accl, ease_out((lt - .2) / .4), key='r', anchor='l', track=.45, shadow=0)
    subs = s.get('subs', [])
    if subs:
        fr.text(subs[0 if lt < BAR or len(subs) < 2 else 1], 120, 960, 30, mix(tc, bg, .2), 1, key='r', anchor='l', track=.15, shadow=0)
    shape = 'SPHERE' if lt < B * 2 else 'TORUS' if lt < BAR else 'LATTICE'
    fr.text(f'POINTS {NP}   ·   {shape}', 1790, 980, 15, mix(tc, bg, .4), 1, key='r', anchor='r', track=.3, shadow=0)
    hud(fr, t, bg)
    return fr


def _knot(s):
    return 900 + 118 * (math.sin(s) + 2 * math.sin(2 * s)), 505 + 118 * (math.cos(s) - 2 * math.cos(2 * s))


def sec_ribbon(s, t):
    lt = t - TL.b2(s['bar0'])
    BAR = TL.BAR2
    bg = PAL['metal']
    fr = Frame(bg_for(bg, .25))
    fr.post.insert(0, lambda base: base.paste(Image.fromarray(np.clip(
        np.asarray(base, np.float32) + C.BRUSH[..., None] * 3.5, 0, 255).astype(np.uint8))))
    cv = fr.cv()
    tc = on_color(bg)
    sh = math.tau * ease_io(lt / (BAR * 1.7)) + .001
    st = max(0.0, sh - 2.8) + (sh - max(0.0, sh - 2.8)) * ease_in((lt - BAR * 1.6) / (BAR * .37))
    pts = [_knot(v) for v in np.linspace(st, sh, 150)]
    stripes = [(48, PAL['dark']), (38, PAL['light']), (22, PAL['accent']), (7, PAL['brand'])]
    if sh - st > .02:
        cv.line([(x + 14, y + 24) for x, y in pts], rgba((0, 0, 0), .14), 62)
        for wd, col in stripes:
            cv.line(pts, rgba(col, 1), wd)
            for (x, y) in (pts[0], pts[-1]):
                cv.ellipse(x, y, wd / 2, fill=rgba(col, 1))
    hx, hy = _knot(sh)
    if s.get('arm', True):
        bx, by, L1 = 1560, 1220, 600
        dx, dy = hx - bx, hy - by
        d = min(math.hypot(dx, dy), 2 * L1 - 1)
        a1 = math.atan2(dy, dx) + math.acos(clamp(d / (2 * L1), -1, 1))
        ex, ey = bx + L1 * math.cos(a1), by + L1 * math.sin(a1)
        aa = sstep(0, .3, lt) * (1 - sstep(BAR * 1.8, BAR * 1.97, lt))
        if aa > 0:
            for (p0, p1, w1) in (((bx, by), (ex, ey), 64), ((ex, ey), (hx, hy), 46)):
                cv.line([(p0[0] + 10, p0[1] + 20), (p1[0] + 10, p1[1] + 20)], rgba((0, 0, 0), .12 * aa), w1 + 10)
                cv.line([p0, p1], rgba(mix(PAL['dark'], (255, 255, 255), .1), aa), w1)
                cv.line([p0, p1], rgba(PAL['accent'], aa), 6)
            for (jx, jy, jr) in ((bx, by, 60), (ex, ey, 40), (hx, hy, 24)):
                fr.mat(circle_pts(jx, jy, jr), 'accent', shadow=.25, alpha=aa)
                cv.ellipse(jx, jy, jr * .38, fill=rgba(PAL['dark'], aa))
    for (a_, b_) in (((hx - 60, hy), (hx - 34, hy)), ((hx + 34, hy), (hx + 60, hy)), ((hx, hy - 60), (hx, hy - 34))):
        cv.line([a_, b_], rgba(tc, .8), 1)
    fr.text(f'X {hx:07.2f}   Y {hy:07.2f}', hx + 70, hy - 50, 15, tc, .9, key='r', anchor='l', track=.15, shadow=0)
    title = s.get('title', '')
    s0 = ease_out(lt / .25)
    fr.text(title, 110, 150, 112 if is_latin(title) else 96, tc, s0, key=kb(title), anchor='l', track=.1, shadow=0, mb=(1 - s0) * 80)
    fr.text(s.get('sub', ''), 116, 238, 30, tc, ease_out((lt - .2) / .4), key='b', anchor='l', track=.2, shadow=0)
    subs = s.get('subs', [])
    if subs:
        fr.text(subs[0 if lt < BAR or len(subs) < 2 else 1], 116, 980, 30, mix(tc, bg, .15), 1, key='r', anchor='l', track=.15,
                shadow=0)
    hud(fr, t, bg)
    return fr


def _ring_chars(R, text, key, size):
    """whole repetitions of text around the ring (never cut a word at the seam)"""
    if not text:
        return []
    f = font(key, size)
    advs = [f.getlength(ch) + size * .12 for ch in text]
    rep_len = sum(advs)
    circ = math.tau * R
    reps = max(1, int(circ // rep_len))
    scale = circ / (rep_len * reps)
    out, pos = [], 0.0
    for _ in range(reps):
        for ch, adv in zip(text, advs):
            out.append((ch, (pos + adv / 2) * scale / R))
            pos += adv
    return out


_rot_cache = {}


def rot_glyph(ch, key, size, deg):
    kq = (ch, key, size, int(round(deg / 2)) % 180)
    g = _rot_cache.get(kq)
    if g is None:
        g = text_mask(ch, key, size, 0).rotate(-(kq[3] * 2), expand=True, resample=Image.BICUBIC)
        if len(_rot_cache) > 6000:
            _rot_cache.clear()
        _rot_cache[kq] = g
    return g


_rings_cache = {}


def sec_words(s, t):
    lt = t - TL.b2(s['bar0'])
    B, BAR = TL.BEAT2, TL.BAR2
    bg = PAL['dark']
    fr = Frame(bg_for(bg, .3))
    lv = fr.lv()
    tl_, mu, ac = PAL['text_light'], PAL['muted'], PAL['accent']
    rows = s.get('rows', [])
    styles = [('b', 70, tl_, -1150, .06), ('enl', 36, mu, 850, .2), ('b', 54, ac, -950, .06), ('r', 34, mu, 700, .2),
              ('enl', 28, mix(mu, bg, .3), -600, .2)]
    if lt < BAR:
        ent = ease_out(lt / .3)

        def marquee(base, lt=lt, ent=ent):
            ys = np.linspace(540 - 60 * (len(rows) - 1), 540 + 60 * (len(rows) - 1), max(1, len(rows)))
            for i, txt in enumerate(rows):
                key, size, col, speed, tr = styles[i % len(styles)]
                if key == 'enl' and not is_latin(txt):
                    key = 'r'
                if key == 'b' and is_latin(txt):
                    key = 'en'
                m = text_mask(txt + '   ', key, size, tr)
                w, h = m.size
                off = (lt * speed + (1 - ent) * speed * .35) % w
                L = int((1 - ent) * 140)
                mm = hblur_mask(m, L) if L >= 2 else m
                ci = Image.new('RGB', mm.size, col)
                x = -off - (L / 2 if L >= 2 else 0)
                while x < W:
                    base.paste(ci, (int(x), int(ys[i] - h / 2)), mm)
                    x += w
        fr.post.append(marquee)
    else:
        l2 = lt - BAR
        ent = ease_out(l2 / .4)
        col_ = ease_in((l2 - B * 3.3) / (B * .7))
        scl = (1 + .45 * (1 - ent)) * (1 - col_)
        spin = (1 - ent) * 1.6 + l2 * .2 + col_ * 3
        rings = s.get('rings', [])[:3]
        cfgs = [(385, 'b', 40, tl_, .35), (300, 'r', 22, mu, -.5), (228, 'b', 28, mix(ac, (255, 255, 255), .25), .7)]
        key_id = id(s)
        if key_id not in _rings_cache:
            out = []
            for txt, (R, key, size, col, sp) in zip(rings, cfgs):
                key = ('en' if key == 'b' else 'enl') if is_latin(txt) else key
                out.append((R, key, size, col, sp, _ring_chars(R, txt + ' · ', key, size)))
            _rings_cache[key_id] = out
        rc = _rings_cache[key_id]

        def draw_rings(base, l2=l2, scl=scl, spin=spin):
            if scl <= .02:
                return
            for R, key, size, col, sp, chars in rc:
                sz = max(4, int(round(size * scl)))
                a0 = spin * (1 if sp > 0 else -1) + l2 * sp
                for ch, ang in chars:
                    if ch == ' ':
                        continue
                    th = a0 + ang - math.pi / 2
                    g = rot_glyph(ch, key, sz, math.degrees(th) + 90)
                    base.paste(Image.new('RGB', g.size, col), (int(960 + R * scl * math.cos(th) - g.size[0] / 2),
                                                               int(540 + R * scl * math.sin(th) - g.size[1] / 2)), g)
            d = ImageDraw.Draw(base, 'RGBA')
            for rr in (340, 262, 190):
                d.ellipse([960 - rr * scl, 540 - rr * scl, 960 + rr * scl, 540 + rr * scl], outline=rgba(mix(mu, bg, .5), .8), width=1)
        fr.post.append(draw_rings)
        fr.mat(circle_pts(960, 540, 16 * (1 + .5 * pulse(t, 10)) * (1 - col_ * .4), 48), 'accent', shadow=0)
        lv.ellipse(960, 540, 40, fill=rgba(ac, .5))
    hud(fr, t, bg)
    return fr


def sec_numbers(s, t):
    lt = t - TL.b2(s['bar0'])
    B = TL.BEAT2
    items = s.get('items', [])[:2] or [['', '']]
    second = len(items) > 1 and lt >= B * 2
    it = items[1] if second else items[0]
    l_ = lt - (B * 2 if second else 0)
    bg = PAL['accent'] if second else PAL['deep']
    fr = Frame(bg_for(bg, .4))
    tc = on_color(bg)
    hl = mix(PAL['accent'], (255, 255, 255), .3) if not second else tc
    sv = ease_out(l_ / .16)
    big = str(it[0])
    fr.text(big, 960, 470, (330 if len(big) <= 5 else 220) * (1 + .25 * (1 - sv)), tc, 1, key='enl' if is_latin(big) else 'l',
            anchor='m', shadow=0)
    if len(it) > 1:
        fr.text(it[1], 960, 730, 48, hl, ease_out((l_ - .12) / .25), key='b', anchor='m', track=.4, shadow=0)
    ra = ease_out((l_ - .05) / .3)
    fr.cv().line([(960 - 260 * ra, 650), (960 + 260 * ra, 650)], rgba(PAL['accent'] if not second else tc, .8), 1.5)
    hud(fr, t, bg)
    return fr


_wm = {}


def wordmark():
    if 'm' not in _wm:
        w = CFG.get('wordmark', {})
        a, b = w.get('text', CFG.get('company', '')), w.get('latin', '')
        m1 = text_mask(a, kb(a), 150 if not is_latin(a) else 130, .08 if not is_latin(a) else .02)
        parts = [m1]
        if b:
            parts.append(text_mask(b, 'en', 122, .02))
        gap = 44
        wd = sum(p.size[0] for p in parts) + gap * (len(parts) - 1)
        ht = max(p.size[1] for p in parts)
        c = Image.new('L', (wd, ht))
        x = 0
        for i, p in enumerate(parts):
            c.paste(p, (x, (ht - p.size[1]) // 2 + (8 if i else 0)))
            x += p.size[0] + gap
        _wm['m'] = c
    return _wm['m']


def sec_logo(s, t):
    lt = t - TL.b2(s['bar0'])
    B, BAR = TL.BEAT2, TL.BAR2
    bg = PAL['light']
    fr = Frame(bg_for(bg, .35))
    WM = wordmark()
    w, h = WM.size
    x0, y0 = 960 - w // 2 - 18, 470 - h // 2
    dot_x, dot_y = x0 + w + 30, y0 + h * .80
    rv = ease_io((lt - B * .9) / .75)
    trail = []
    for g in range(7):
        fq = ease_out((lt - g * .03) / (B * 1.4))
        trail.append(((1 - fq) ** 2 * -80 + 2 * (1 - fq) * fq * 500 + fq * fq * dot_x,
                      (1 - fq) ** 2 * 1150 + 2 * (1 - fq) * fq * 120 + fq * fq * dot_y))
    land = lt - B * 1.4
    squash = 1 + .35 * math.exp(-max(0, land) * 9) * math.sin(max(0, land) * 30) if land > 0 else 1
    brand = PAL['brand'] if abs(lum(PAL['brand']) - lum(bg)) > .25 else on_color(bg)

    def logo(base, rv=rv, trail=trail, squash=squash):
        if rv > 0:
            M = np.asarray(WM, np.float32) / 255
            M = M * np.clip((rv * (w + 120) - 60 - np.arange(w)[None, :]) / 60, 0, 1)
            region = np.asarray(base.crop((x0, y0, x0 + w, y0 + h)), np.float32)
            out = region * (1 - M[..., None]) + np.array(brand, np.float32) * M[..., None]
            base.paste(Image.fromarray(out.clip(0, 255).astype(np.uint8)), (x0, y0))
        d = ImageDraw.Draw(base, 'RGBA')
        for g, (px, py) in enumerate(trail[1:], 1):
            r = 13 * (1 - g / 8)
            d.ellipse([px - r, py - r, px + r, py + r], fill=rgba(PAL['accent'], .22 * (1 - g / 7)))
        px, py = trail[0]
        draw_material(base, [(px + 14 * squash * math.cos(a), py + 14 / squash * math.sin(a)) for a in np.linspace(0, math.tau, 48)],
                      'accent', -.9, .15, .25, 1)
    fr.post.append(logo)
    tc = on_color(bg)
    ra = ease_out((lt - B * 2.2) / .6)
    fr.cv().line([(960 - 300 * ra, 600), (960 + 300 * ra, 600)], rgba(PAL['accent'], .9), 1.5)
    sl = CFG.get('slogan', '')
    fr.text(sl, 960, 660, 34, mix(tc, bg, .25), sstep(B * 2.8, B * 3.6, lt), key=kb(sl), anchor='m', track=.45, shadow=0)
    tg = CFG.get('tagline', '')
    fr.text(tg, 960, 730, 22, mix(PAL['accent'], (0, 0, 0), .25), sstep(BAR + .1, BAR + .7, lt), key='r', anchor='m', track=.5,
            shadow=0)
    fr.text(f"{CFG.get('hud_name', CFG.get('company', '')).upper()}   ·   {CFG.get('years', '')}", 960, 1000, 15,
            mix(tc, bg, .45), sstep(BAR + .4, BAR + 1.0, lt), key='r', anchor='m', track=.4, shadow=0)
    return fr


PART2 = {'dots': sec_dots, 'slam': sec_slam, 'shapes': sec_shapes, 'grid': sec_grid, 'cloud': sec_cloud,
         'ribbon': sec_ribbon, 'words': sec_words, 'numbers': sec_numbers, 'logo': sec_logo, 'custom': sc_custom}
