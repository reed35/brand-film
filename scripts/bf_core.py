"""brand-film core: config, palette, fonts, drawing primitives, text, materials, compositing helpers.
All drawing happens in a virtual 1920x1080 space; the sharp layer is supersampled 2x."""
import glob
import json
import math
import os
import platform
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 30
SS = 2        # supersampling of the sharp layer (set by set_resolution)
OUT_W, OUT_H = 1920, 1080   # encoded video size (layout is always designed in 1920x1080)
RESOLUTIONS = {'720p': (1280, 720, 1), '1080p': (1920, 1080, 2)}
LK = 0.5      # scale of the glow layer

CFG = {}      # loaded film.json (filled by load_config)
PAL = {}      # palette roles -> RGB tuples
FONTS = {}    # key -> font path


# ---------------------------------------------------------------- math / easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def sstep(a, b, x):
    x = clamp((x - a) / (b - a)) if b != a else float(x >= a)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp(x)
    return x * x * x


def ease_io(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out_back(x, c1=1.70158):
    x = clamp(x)
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def lerp(a, b, s):
    return a + (b - a) * s


def lerpc(c1, c2, s):
    return tuple(int(round(lerp(a, b, s))) for a, b in zip(c1, c2))


def rgba(c, a):
    return (int(c[0]), int(c[1]), int(c[2]), int(clamp(a) * 255))


def win(t, t0, t1, fin=.6, fout=.6):
    return sstep(t0, t0 + fin, t) * (1 - sstep(t1 - fout, t1, t))


def rnd(seed):
    return np.random.default_rng(seed)


def hex2rgb(h):
    h = h.strip().lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(c):
    r, g, b = [v / 255 for v in c]
    return .2126 * r + .7152 * g + .0722 * b


def mix(c1, c2, s):
    return lerpc(c1, c2, s)


def on_color(bg):
    """readable text color for a background"""
    return PAL['text_dark'] if lum(bg) > .45 else PAL['text_light']


# ---------------------------------------------------------------- config
DEFAULT_PALETTE = {
    'dark': '#0C0D0F', 'dark2': '#1C1E22', 'light': '#ECE9E3', 'deep': '#0C285C',
    'accent': '#C9A36A', 'brand': '#0058A8', 'metal': '#C4C8CE', 'warm': '#FFB058',
    'text_dark': '#0C0D0F', 'text_light': '#ECE9E3', 'muted': '#8C9198',
}


def _find(cands):
    for c in cands:
        for p in glob.glob(c):
            if os.path.exists(p):
                return p
    return None


def detect_fonts():
    sysname = platform.system()
    if sysname == 'Windows':
        F = r'C:\Windows\Fonts'
        d = {'b': [F + r'\msyhbd.ttc', F + r'\simhei.ttf'], 'r': [F + r'\msyh.ttc', F + r'\simhei.ttf'],
             'l': [F + r'\msyhl.ttc', F + r'\msyh.ttc'], 'en': [F + r'\segoeuib.ttf', F + r'\arialbd.ttf'],
             'enl': [F + r'\segoeuil.ttf', F + r'\arial.ttf']}
    elif sysname == 'Darwin':
        d = {'b': ['/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Medium.ttc',
                   '/System/Library/Fonts/Hiragino Sans GB.ttc'],
             'r': ['/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Light.ttc'],
             'l': ['/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Light.ttc'],
             'en': ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/System/Library/Fonts/Helvetica.ttc'],
             'enl': ['/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc']}
    else:
        n = '/usr/share/fonts/**/'
        d = {'b': [n + 'NotoSansCJK*Bold*', n + 'SourceHanSans*Bold*', n + 'wqy-zenhei*', n + 'DejaVuSans-Bold.ttf'],
             'r': [n + 'NotoSansCJK*Regular*', n + 'SourceHanSans*Regular*', n + 'wqy-zenhei*', n + 'DejaVuSans.ttf'],
             'l': [n + 'NotoSansCJK*Light*', n + 'NotoSansCJK*DemiLight*', n + 'NotoSansCJK*Regular*', n + 'DejaVuSans.ttf'],
             'en': [n + 'DejaVuSans-Bold.ttf', n + 'LiberationSans-Bold.ttf'],
             'enl': [n + 'DejaVuSans-ExtraLight.ttf', n + 'DejaVuSans.ttf', n + 'LiberationSans-Regular.ttf']}
        d = {k: v for k, v in d.items()}
        for k in d:
            found = None
            for pat in d[k]:
                hits = glob.glob(pat, recursive=True)
                if hits:
                    found = hits[0]
                    break
            d[k] = [found] if found else []
    out = {}
    for k, cands in d.items():
        p = _find(cands)
        if p:
            out[k] = p
    return out


def set_resolution(name):
    """1080p: draw at 4K, reduce to 1920x1080 (sharpest, default).
    720p: draw at 1080 without supersampling, downscale to 1280x720 (about 2x faster)."""
    global SS, OUT_W, OUT_H
    name = str(name).lower().replace('p', '') + 'p'
    if name not in RESOLUTIONS:
        raise ValueError(f'resolution must be one of {list(RESOLUTIONS)}')
    OUT_W, OUT_H, SS = RESOLUTIONS[name]
    return name


def to_output(arr):
    """uint8 HxWx3 frame at 1920x1080 -> encoded size"""
    if (OUT_W, OUT_H) == (W, H):
        return arr
    return np.asarray(Image.fromarray(arr).resize((OUT_W, OUT_H), Image.LANCZOS))


def load_config(path):
    global CFG
    with open(path, encoding='utf-8') as f:
        CFG.clear()
        CFG.update(json.load(f))
    CFG['_dir'] = os.path.dirname(os.path.abspath(path))
    pal = dict(DEFAULT_PALETTE)
    pal.update(CFG.get('palette', {}))
    PAL.clear()
    PAL.update({k: hex2rgb(v) for k, v in pal.items()})
    FONTS.clear()
    FONTS.update(detect_fonts())
    FONTS.update(CFG.get('fonts', {}))
    for k in ('b', 'r', 'l', 'en', 'enl'):
        if k not in FONTS:
            FONTS[k] = FONTS.get('r') or FONTS.get('b')
    make_materials()
    set_resolution(CFG.get('resolution', '1080p'))
    text_mask.cache_clear()
    return CFG


# ---------------------------------------------------------------- fonts / text
@lru_cache(maxsize=None)
def font(key, px):
    return ImageFont.truetype(FONTS[key], max(4, int(px)))


@lru_cache(maxsize=1024)
def text_mask(s, key, size, track=0.0):
    f = font(key, int(round(size)))
    if not s:
        return Image.new('L', (2, 2))
    l, t, r, b = f.getbbox(s)
    if track == 0:
        m = Image.new('L', (r - l + 4, b - t + 4), 0)
        ImageDraw.Draw(m).text((2 - l, 2 - t), s, font=f, fill=255)
        return m
    widths = [f.getlength(ch) for ch in s]
    tr = track * size
    total = int(sum(widths) + tr * (len(s) - 1)) + 8
    m = Image.new('L', (max(total, 4), b - t + 6), 0)
    d = ImageDraw.Draw(m)
    x = 2
    for ch, w in zip(s, widths):
        d.text((x, 2 - t), ch, font=f, fill=255)
        x += w + tr
    return m


@lru_cache(maxsize=256)
def shadow_mask(s, key, size, track):
    m = text_mask(s, key, size, track)
    pad = 24
    big = Image.new('L', (m.size[0] + pad * 2, m.size[1] + pad * 2))
    big.paste(m, (pad, pad))
    return big.filter(ImageFilter.GaussianBlur(max(4, size * .18))), pad


_LUTS = {}


def alpha_lut(a):
    q = int(clamp(a) * 64)
    if q not in _LUTS:
        _LUTS[q] = [int(v * q / 64) for v in range(256)]
    return _LUTS[q]


def hblur_mask(m, L):
    a = np.pad(np.asarray(m, np.float32), ((0, 0), (L, L)))
    c = np.pad(np.cumsum(a, axis=1), ((0, 0), (1, 0)))
    return Image.fromarray(np.clip((c[:, L:] - c[:, :-L]) / L, 0, 255).astype(np.uint8))


def put_text(img, s, x, y, size, color, alpha=1.0, key='r', anchor='m', track=0, shadow=.6, mb=0):
    """screen-space text at output resolution. anchor l/m/r, vertically centered."""
    if alpha <= 0.01 or size < 4 or not s:
        return
    size = int(round(size))
    m = text_mask(s, key, size, track)
    w, h = m.size
    px = x - (0 if anchor == 'l' else w / 2 if anchor == 'm' else w)
    py = y - h / 2
    if mb >= 2:
        L = int(mb)
        m = hblur_mask(m, L)
        px -= L / 2
    elif shadow > 0:
        sm, pad = shadow_mask(s, key, size, track)
        img.paste(Image.new('RGB', sm.size, (0, 4, 12)), (int(px) - pad, int(py) - pad + 3),
                  sm.point(alpha_lut(alpha * shadow * 1.6)))
    img.paste(Image.new('RGB', m.size, tuple(color)), (int(px), int(py)), m.point(alpha_lut(alpha)))


def text_width(s, size, key='r', track=0):
    return text_mask(s, key, int(round(size)), track).size[0]


# ---------------------------------------------------------------- canvas / frame
class Cv:
    """draw in virtual 1920x1080 space with a camera (zoom z around cx,cy, offset ox,oy)"""

    def __init__(s, img, k, z=1.0, cx=960, cy=540, ox=0, oy=0):
        s.im, s.k, s.z, s.cx, s.cy, s.ox, s.oy = img, k, z, cx, cy, ox, oy
        s.d = ImageDraw.Draw(img, 'RGBA')

    def X(s, x):
        return ((x - s.cx) * s.z + 960 + s.ox) * s.k

    def Y(s, y):
        return ((y - s.cy) * s.z + 540 + s.oy) * s.k

    def S(s, v):
        return v * s.z * s.k

    def sp(s, x, y):
        return s.X(x) / s.k, s.Y(y) / s.k

    def pts(s, p):
        return [(s.X(x), s.Y(y)) for x, y in p]

    def _w(s, width):
        return max(1, int(round(s.S(width))))

    def ellipse(s, cx, cy, rx, ry=None, fill=None, outline=None, width=1):
        ry = rx if ry is None else ry
        x0, x1 = s.X(cx) - s.S(rx), s.X(cx) + s.S(rx)
        y0, y1 = s.Y(cy) - s.S(ry), s.Y(cy) + s.S(ry)
        if x1 - x0 < .5 or y1 - y0 < .5 or x1 < -9000 or x0 > 99999:
            return
        s.d.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=s._w(width))

    def line(s, p, fill, width=1.0):
        if len(p) >= 2:
            s.d.line(s.pts(p), fill=fill, width=s._w(width), joint='curve')

    def poly(s, p, fill=None, outline=None, width=1):
        if len(p) >= 3:
            s.d.polygon(s.pts(p), fill=fill, outline=outline, width=s._w(width))

    def rect(s, x0, y0, x1, y1, fill=None, outline=None, width=1, r=0):
        a, b, c, d = s.X(x0), s.Y(y0), s.X(x1), s.Y(y1)
        if c - a < .5 or d - b < .5:
            return
        if r:
            s.d.rounded_rectangle([a, b, c, d], radius=max(0, s.S(r)), fill=fill, outline=outline, width=s._w(width))
        else:
            s.d.rectangle([a, b, c, d], fill=fill, outline=outline, width=s._w(width) if outline else 0)


class Frame:
    def __init__(s, bg):
        s.base = bg
        s.light = Image.new('RGB', (int(W * LK), int(H * LK)))
        s.texts, s.mats, s.post = [], [], []
        s.accent = None

    def cv(s, **cam):
        return Cv(s.base, SS, **cam)

    def lv(s, **cam):
        return Cv(s.light, LK, **cam)

    def text(s, txt, x, y, size, color, alpha=1.0, **kw):
        s.texts.append(((txt, x, y, size, color, alpha), kw))

    def mat(s, pts, kind, ang=-.9, sheen=.25, shadow=.35, alpha=1.0):
        s.mats.append((pts, kind, ang, sheen, shadow, alpha))


@lru_cache(maxsize=96)
def _grad(top, bot, glows):
    h, w = 135, 240
    y = np.linspace(0, 1, h)[:, None, None]
    img = np.array(top, float)[None, None] * (1 - y) + np.array(bot, float)[None, None] * y
    img = np.repeat(img, w, axis=1)
    if glows:
        yy, xx = np.mgrid[0:h, 0:w]
        for gx, gy, r, c, st in glows:
            d2 = ((xx - gx / 8) ** 2 + (yy - gy / 8) ** 2) / (r / 8) ** 2
            img += np.exp(-d2 * 2.2)[..., None] * np.array(c, float)[None, None] * st
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def grad_bg(top, bot, glows=()):
    q = lambda c: tuple(int(v) // 2 * 2 for v in c)
    g = tuple((int(a) // 6 * 6, int(b) // 6 * 6, int(r) // 6 * 6, q(c), round(st, 2)) for a, b, r, c, st in glows)
    return _grad(q(top), q(bot), g).resize((W * SS, H * SS), Image.BILINEAR)


def bg_for(c, glow=.35):
    """soft studio background from one color"""
    top = mix(c, (255, 255, 255), .06) if lum(c) < .5 else mix(c, (255, 255, 255), .25)
    bot = mix(c, (0, 0, 0), .45) if lum(c) < .5 else mix(c, (0, 0, 0), .12)
    gl = mix(c, (255, 255, 255), .5)
    return grad_bg(top, bot, ((820, 360, 1000, tuple(v * .25 for v in gl), glow),))


# ---------------------------------------------------------------- materials
MATS = {}


def _mat_from(c, spec=None):
    c = tuple(c)
    return (mix(c, (0, 0, 0), .55), c, mix(c, (255, 255, 255), .55), spec or mix(c, (255, 255, 255), .88))


def make_materials():
    MATS.clear()
    MATS['accent'] = _mat_from(PAL['accent'])
    MATS['brand'] = _mat_from(PAL['brand'])
    MATS['deep'] = _mat_from(mix(PAL['deep'], (255, 255, 255), .12))
    MATS['metal'] = _mat_from(PAL['metal'])
    MATS['light'] = ((mix(PAL['light'], (0, 0, 0), .22)), PAL['light'], mix(PAL['light'], (255, 255, 255), .7), (255, 255, 255))
    MATS['dark'] = ((5, 5, 7), mix(PAL['dark'], (255, 255, 255), .08), mix(PAL['dark'], (255, 255, 255), .3),
                    (160, 165, 175))
    MATS['gold'] = ((92, 66, 34), (192, 154, 98), (246, 224, 180), (255, 246, 226))
    MATS['silver'] = ((66, 70, 76), (168, 173, 180), (234, 236, 240), (255, 255, 255))


_r = np.random.default_rng(5)
_n = _r.standard_normal((540, W + 240)).astype(np.float32)
_c = np.cumsum(_n, axis=1)
_n = (_c[:, 240:] - _c[:, :-240]) / 240 ** .5 + _r.standard_normal((540, W)).astype(np.float32) * .35
BRUSH = np.repeat(_n / _n.std(), 2, axis=0)
_g = np.random.default_rng(99)
GRAIN = [_g.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = np.clip(1 - .45 * (((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2), 0, 1)[..., None]
del _r, _n, _c, _g, _yy, _xx


def draw_material(base, pts, kind, ang=-.9, sheen=.25, shadow=.35, alpha=1.0):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(math.floor(min(xs))) - 2, int(math.floor(min(ys))) - 2
    x1, y1 = int(math.ceil(max(xs))) + 2, int(math.ceil(max(ys))) + 2
    w, h = x1 - x0, y1 - y0
    if w < 3 or h < 3 or x1 < 0 or y1 < 0 or x0 > W or y0 > H or w > 5000 or h > 5000:
        return
    m = Image.new('L', (w * 2, h * 2))
    ImageDraw.Draw(m).polygon([((x - x0) * 2, (y - y0) * 2) for x, y in pts], fill=255)
    m = m.reduce(2)
    if shadow > 0:
        sm = m.filter(ImageFilter.GaussianBlur(max(3, min(w, h) * .05)))
        base.paste(Image.new('RGB', m.size, (0, 0, 0)), (x0, y0 + int(h * .05)), sm.point(alpha_lut(shadow * alpha)))
    c0, c1, c2, cs = (np.array(c, np.float32) for c in MATS.get(kind, MATS['accent']))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = ((xx - w / 2) * math.cos(ang) + (yy - h / 2) * math.sin(ang)) / (.5 * math.hypot(w, h))
    s_ = np.clip((u + 1) / 2, 0, 1)[..., None]
    col = np.where(s_ < .5, c0 + (c1 - c0) * (s_ * 2), c1 + (c2 - c1) * (s_ * 2 - 1))
    spec = np.exp(-((u - sheen) / .13) ** 2)[..., None] * .55
    col = col + (cs - col) * spec
    bx, by = max(0, x0) % 1900, max(0, y0) % 1000
    br = BRUSH[by:by + h, bx:bx + w]
    if br.shape == (h, w):
        col = col + br[..., None] * 4
    base.paste(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)), (x0, y0), m.point(alpha_lut(alpha)))


def circle_pts(cx, cy, r, n=96):
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(0, math.tau, n, endpoint=False)]


# ---------------------------------------------------------------- typography helpers
def caption(fr, t, t0, t1, year, lines, x=150, y=760, align='l', ycol=None, lcol=(255, 255, 255), big=118, shadow=.6):
    """cinematic lower-third: year (thin, large) + up to two lines, staggered reveal"""
    a0 = win(t, t0, t1, .7, .6)
    if a0 <= 0:
        return
    rise = (1 - ease_out((t - t0) / 1.0)) * 26
    ycol = ycol or lcol
    yy = y
    if year:
        fr.text(year, x, yy + rise, big, ycol, a0, key='l', anchor=align, track=.02, shadow=shadow)
        yy += big * .78
        fr.accent = (x, yy - 6, 120 * ease_out((t - t0 - .2) / .8), align, a0, ycol)
    for i, ln in enumerate(lines[:3]):
        ai = win(t, t0 + .25 + i * .3, t1, .7, .6)
        r2 = (1 - ease_out((t - t0 - .25 - i * .3) / 1.0)) * 22
        fr.text(ln, x, yy + 38 + r2 + i * 64, 50 if i == 0 else 36, lcol, ai * (1 if i == 0 else .85),
                key='b' if i == 0 else 'r', anchor=align, track=.06, shadow=shadow)


def center_title(fr, t, t0, t1, s, y=540, size=84, col=(255, 255, 255), key='b', track=.12, shadow=.6):
    a = win(t, t0, t1, .8, .7)
    if a > 0:
        fr.text(s, 960, y + (1 - ease_out((t - t0) / 1.2)) * 20, size, col, a, key=key, anchor='m',
                track=track + .06 * (1 - ease_out((t - t0) / 2.2)), shadow=shadow)


# ---------------------------------------------------------------- frame rendering
def render_frame(fr):
    base = fr.base.reduce(SS) if SS > 1 else fr.base
    for m in fr.mats:
        draw_material(base, *m)
    for f in fr.post:
        f(base)
    for (a, kw) in fr.texts:
        put_text(base, *a, **kw)
    if fr.accent:
        x, y, L, align, al, col = fr.accent
        x0 = x if align == 'l' else x - L
        ImageDraw.Draw(base, 'RGBA').rectangle([x0, y, x0 + L, y + 3], fill=rgba(col, al))
    g1 = fr.light.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
    g2 = fr.light.resize((240, 135), Image.BILINEAR).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    return (np.asarray(base, np.float32) + np.asarray(g1, np.float32) * .8 + np.asarray(g2, np.float32) * .7)


def hblur_img(img, L):
    L = int(L)
    if L < 2:
        return img
    c = np.cumsum(np.pad(img, ((0, 0), (L, L), (0, 0)), mode='edge'), axis=1, dtype=np.float32)
    c = np.pad(c, ((0, 0), (1, 0), (0, 0)))
    o = L // 2
    return ((c[:, L:] - c[:, :-L]) / L)[:, o:o + W]
