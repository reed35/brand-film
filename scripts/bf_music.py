"""Original score synthesized with numpy, arranged from the Timeline.
Moods change the orchestration: warm | luxury | tech | playful | epic."""
import wave

import numpy as np

SR = 44100
TAU = 2 * np.pi
rng = np.random.default_rng(7)
N = 0
dry = padbus = send = None


def init(dur):
    global N, dry, padbus, send
    N = int(SR * dur)
    dry = np.zeros((2, N))
    padbus = np.zeros((2, N))
    send = np.zeros((2, N))


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def place(bus, sig, t0, gain=1.0, pan=0.0, rev=0.2):
    if sig.ndim == 1:
        sig = np.stack([sig, sig])
    i = int(round(t0 * SR))
    if i >= N or i < 0:
        return
    n = min(sig.shape[1], N - i)
    a = (pan + 1) * np.pi / 4
    g = np.array([np.cos(a), np.sin(a)])[:, None] * gain * 1.414
    bus[:, i:i + n] += sig[:, :n] * g
    send[:, i:i + n] += sig[:, :n] * g * rev


def tarr(sec):
    return np.arange(max(1, int(sec * SR))) / SR


def adsr(n, a, r_start, r):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4))
    rel = t > r_start
    e[rel] *= np.exp(-(t[rel] - r_start) / max(r, 1e-4))
    return e


def fft_filter(x, lo=None, hi=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    Hf = np.ones_like(f)
    if lo:
        Hf *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        Hf *= 1 / np.sqrt(1 + (f / hi) ** 4)
    return np.fft.irfft(X * Hf, len(x))


# ---------------- instruments
def piano(m, dur, vel=1.0):
    f = mtof(m)
    t = tarr(dur + 1.8)
    out = np.zeros_like(t)
    for k in range(1, 10):
        fk = f * k * np.sqrt(1 + 0.0004 * k * k)
        if fk > 12000:
            break
        out += np.sin(TAU * fk * t + rng.uniform(0, 1)) / k ** 1.1 * np.exp(-t * (0.9 + 0.55 * k) * (0.6 + f / 800))
    out += 0.3 * rng.standard_normal(len(t)) * np.exp(-t * 120) * vel
    return out * adsr(len(t), .003, dur, .25) * vel * 0.35


def musicbox(m, dur=1):
    f = mtof(m)
    t = tarr(2.5)
    out = (np.sin(TAU * f * t) * np.exp(-t * 2.2) + .35 * np.sin(TAU * 3.0 * f * t) * np.exp(-t * 5)
           + .18 * np.sin(TAU * 5.4 * f * t) * np.exp(-t * 9) + .10 * np.sin(TAU * 8.9 * f * t) * np.exp(-t * 14))
    return out * np.minimum(1, t / .002) * 0.3


def saw_voice(f, t, bright=1.0, vib=0.0, vr=5.2, rolloff=1.0, hmax=7000):
    ph = TAU * f * t
    if vib:
        ph -= f * vib / vr * np.cos(TAU * vr * t)
    out = np.zeros_like(t)
    nh = int(max(1, min(40, hmax * bright / f)))
    p0 = rng.uniform(0, TAU)
    for k in range(1, nh + 1):
        out += np.sin(k * (ph + p0)) / k ** rolloff
    return out


def pad(notes, dur, bright=0.5, attack=.9, release=1.6):
    t = tarr(dur + release * 2.5)
    L = np.zeros_like(t)
    R = np.zeros_like(t)
    for m in notes:
        f = mtof(m)
        for dc, (gl, gr) in ((-9, (1, .3)), (0, (.7, .7)), (9, (.3, 1))):
            v = saw_voice(f * 2 ** (dc / 1200), t, bright=bright, hmax=3000, rolloff=1.4)
            L += v * gl
            R += v * gr
    return np.stack([L, R]) * adsr(len(t), attack, dur, release) * 0.05


def strings(notes, dur, bright=1.0, attack=.35, release=.9):
    t = tarr(dur + release * 3)
    L = np.zeros_like(t)
    R = np.zeros_like(t)
    for m in notes:
        f = mtof(m)
        for dc, (gl, gr) in ((-7, (1, .2)), (6, (.2, 1)), (0, (.6, .6))):
            v = saw_voice(f * 2 ** (dc / 1200), t, bright=bright, vib=.006, vr=5 + rng.uniform(-.4, .4), hmax=6000)
            L += v * gl
            R += v * gr
    return np.stack([L, R]) * adsr(len(t), attack, dur, release) * 0.045


def brass(m, dur, amt=1.0):
    f = mtof(m)
    t = tarr(dur + .6)
    fc = 600 + 3200 * amt * np.exp(-t * 3.5) + 900 * amt
    out = np.zeros_like(t)
    ph = TAU * f * t + rng.uniform(0, TAU)
    for k in range(1, int(min(30, 9000 / f)) + 1):
        out += np.sin(k * ph) / k * np.exp(-(k * f) / fc)
    return np.tanh(out * 1.4) * adsr(len(t), .025, dur, .18) * 0.16


def pluck(m, dur=.4):
    f = mtof(m)
    t = tarr(dur + .5)
    out = np.zeros_like(t)
    for k in range(1, int(min(24, 9000 / f)) + 1):
        out += np.sin(TAU * f * k * t) / k * np.exp(-t * (5 + 2.2 * k))
    return out * np.minimum(1, t / .002) * 0.22


def bell(m, dur=1):
    f = mtof(m)
    t = tarr(3.0)
    out = (np.sin(TAU * f * t) * np.exp(-t * 1.2) + .5 * np.sin(TAU * 2.76 * f * t) * np.exp(-t * 2.5)
           + .25 * np.sin(TAU * 5.4 * f * t) * np.exp(-t * 5))
    return out * np.minimum(1, t / .003) * .22


def bass(m, dur, drive=1.5):
    f = mtof(m)
    t = tarr(dur + .3)
    x = np.sin(TAU * f * t) + .35 * np.sin(TAU * 2 * f * t) + .12 * np.sin(TAU * 3 * f * t)
    return np.tanh(x * drive) / np.tanh(drive) * adsr(len(t), .008, dur * .92, .08) * 0.42


def sub(m, dur):
    t = tarr(dur + .05)
    return np.sin(TAU * mtof(m) * t) * adsr(len(t), .004, dur, .03) * .5


def kick(g=1.0):
    t = tarr(.6)
    f = 44 + 120 * np.exp(-t * 32)
    x = np.sin(np.cumsum(TAU * f / SR)) * np.exp(-t * 5.5) + .25 * rng.standard_normal(len(t)) * np.exp(-t * 350)
    return np.tanh(x * 1.6) * g * 0.8


def clap(g=1.0):
    t = tarr(.45)
    nz = fft_filter(rng.standard_normal(len(t)), lo=900, hi=7000)
    env = np.zeros_like(t)
    for d in (0, .011, .022):
        env += np.where(t >= d, np.exp(-(t - d) * 45), 0) * .6
    env += np.exp(-t * 11) * .5
    return (nz / (np.abs(nz).max() + 1e-9) * env + np.sin(TAU * 185 * t) * np.exp(-t * 28) * .5) * g * 0.45


HAT_C = fft_filter(rng.standard_normal(int(.12 * SR)), lo=7500)
HAT_O = fft_filter(rng.standard_normal(int(.5 * SR)), lo=6500)


def hat(g=1.0, kind='c'):
    base = HAT_C if kind == 'c' else HAT_O
    t = np.arange(len(base)) / SR
    return base / np.abs(base).max() * np.exp(-t * (70 if kind == 'c' else 10)) * g * 0.35


def crash(g=1.0, sec=3.5):
    t = tarr(sec)
    nz = fft_filter(rng.standard_normal(len(t)), lo=3500)
    return nz / np.abs(nz).max() * np.exp(-t * 1.3) * np.minimum(1, t / .003) * g * 0.35


def boom(g=1.0):
    t = tarr(3.0)
    f = 38 + 50 * np.exp(-t * 6)
    x = np.sin(np.cumsum(TAU * f / SR)) * np.exp(-t * 1.4)
    x += fft_filter(rng.standard_normal(len(t)), hi=400) * np.exp(-t * 8) * .5
    return np.tanh(x * 1.3) * g * 0.7


def riser(t0, t1, g):
    t = tarr(t1 - t0)
    s = t / t[-1]
    nz = rng.standard_normal(len(t))
    out = np.zeros_like(t)
    chunk = int(.1 * SR)
    for i in range(0, len(t), chunk):
        seg = nz[i:i + chunk * 2]
        c = 400 + 9000 * (i / len(t)) ** 2
        fseg = fft_filter(seg, lo=c * .6, hi=c * 1.6) * np.hanning(len(seg))
        out[i:i + len(fseg)] += fseg[:len(out) - i]
    out /= np.abs(out).max() + 1e-9
    sweep = np.sin(np.cumsum(TAU * (200 + 1400 * s ** 2) / SR)) * .25
    return (out + sweep) * s ** 2.2 * g * 0.4


def whoosh(g=1.0):
    t = tarr(.5)
    nz = fft_filter(rng.standard_normal(len(t)), lo=500, hi=6000)
    return nz / np.abs(nz).max() * np.sin(np.pi * np.clip(t / .5, 0, 1)) ** 2 * g * .25


def ping(m, g=1.0):
    t = tarr(1.2)
    f = mtof(m)
    x = np.sin(TAU * f * t) * np.exp(-t * 7) + .3 * np.sin(TAU * 2 * f * t) * np.exp(-t * 14)
    return x * np.minimum(1, t / .002) * g * .3


# lead instrument per energy level (0..3) and intro texture per mood
MOODS = {
    'warm':    {'lead': ['musicbox', 'piano', 'strings', 'brass+strings'], 'crackle': True, 'stab': 'brass'},
    'luxury':  {'lead': ['piano', 'piano', 'strings', 'strings+piano'], 'crackle': False, 'stab': 'strings'},
    'tech':    {'lead': ['bell', 'pluck', 'strings', 'brass+strings'], 'crackle': False, 'stab': 'brass'},
    'playful': {'lead': ['musicbox', 'pluck', 'pluck+strings', 'brass+strings'], 'crackle': False, 'stab': 'pluck'},
    'epic':    {'lead': ['piano', 'strings', 'brass+strings', 'brass+strings'], 'crackle': False, 'stab': 'brass'},
}


def play_lead(kind, m, d, t0, gain=1.0, octave=0):
    m = m + octave
    for part in kind.split('+'):
        if part == 'musicbox':
            place(dry, musicbox(m + 12, d), t0, gain=.55 * gain, pan=.15, rev=.6)
        elif part == 'bell':
            place(dry, bell(m + 12, d), t0, gain=.7 * gain, pan=.1, rev=.6)
        elif part == 'piano':
            place(dry, piano(m, d, .9), t0, gain=1.0 * gain, pan=.1, rev=.45)
        elif part == 'pluck':
            place(dry, pluck(m + 12, d), t0, gain=.9 * gain, pan=.1, rev=.35)
        elif part == 'strings':
            place(dry, strings([m], d, bright=1.1, attack=.08, release=.5), t0, gain=2.2 * gain, pan=.05, rev=.45)
        elif part == 'brass':
            place(dry, brass(m, d, .95), t0, gain=1.1 * gain, rev=.4)


def build(tl, out_path, nostalgia=True):
    init(tl.DUR)
    mood = MOODS.get(tl.mood, MOODS['warm'])
    B1, B2 = tl.BEAT1, tl.BEAT2
    k = tl.key
    # ======== part 1
    for b, e in enumerate(tl.energy):
        t0 = tl.b1(b)
        ch = tl.chord1(b)
        notes = tl.notes_of(ch)
        root = 48 + ch[0]
        if e == 'bridge':
            continue
        place(padbus, pad(notes, tl.BAR1 + .05, bright=.35 + .15 * e, attack=1.0 if e == 0 else .4, release=1.0), t0,
              gain=(.6 + .15 * e) * (min(1, t0 / 3 + .2) if b < 2 else 1), rev=.5)
        if e >= 2:
            place(padbus, strings(notes + [notes[0] + 12], tl.BAR1, bright=.8 + .15 * e, release=.8), t0,
                  gain=.5 + .12 * e, rev=.45)
        if e == 0:
            for i, m in enumerate([root, notes[1], notes[2], notes[1] + 12 - (12 if notes[1] + 12 > 76 else 0)]):
                place(dry, piano(m, B1 * 1.6, .55), tl.b1(b, i), gain=.8, pan=-.2 + i * .12, rev=.45)
        else:
            pat = [root, notes[0] + 12 - 12 * (notes[0] >= 60), notes[1], notes[2], notes[1] + 12, notes[2], notes[1],
                   notes[0]]
            for i, m in enumerate(pat):
                place(dry, piano(m, B1 * .6, .45), tl.b1(b, i * .5), gain=.7, pan=-.3 + (i % 4) * .2, rev=.35)
        bm = 36 + ch[0]
        if e == 1:
            place(dry, bass(bm, tl.BAR1 * .95, 1.2), t0, gain=.8, rev=.05)
        elif e == 2:
            for x, d in ((0, 1.9), (2, .45), (2.5, 1.4)):
                place(dry, bass(bm, B1 * d), tl.b1(b, x), gain=.9, rev=.05)
        elif e == 3:
            for i in range(8):
                place(dry, bass(bm + (12 if i % 2 else 0), B1 * .45, 2.0), tl.b1(b, i * .5), gain=.85, rev=.05)
        if e >= 2 or (tl.mood == 'tech' and e >= 1):
            arp = [notes[0] + 12, notes[1] + 12, notes[2] + 12, notes[1] + 24]
            for i in range(16):
                place(dry, pluck(arp[i % 4], .18), tl.b1(b, i * .25), gain=(.28 + .06 * e) * (1.2 if i % 4 == 0 else 1),
                      pan=np.sin(i * .9) * .6, rev=.3)
        if e == 3 and mood['stab'] == 'brass':
            for m in notes + [notes[0] + 12]:
                place(dry, brass(m, B1 * 1.2, .7), t0, gain=.42, pan=rng.uniform(-.3, .3), rev=.35)
        # melody: continuous theme, instrument grows with energy
        for tt, m, d in tl.theme_bar((b + 2) % 8, t0, B1, semis=k):
            play_lead(mood['lead'][e], m, d, tt, gain=.9 if e == 0 else 1.0)
    # bridge: breath then dominant swell
    bb = tl.n1 - 2
    ch = tl.chord1(bb - 1) if bb > 0 else (k, 'M')
    place(padbus, pad(tl.notes_of(ch) + [53 + k % 12], tl.BAR1 * 1.02, bright=.5, attack=.05, release=2.5), tl.b1(bb),
          gain=1.0, rev=.7)
    for m in tl.notes_of(ch, 41) + tl.notes_of(ch, 60):
        place(dry, piano(m, 2.2, .7), tl.b1(bb), gain=.5, rev=.7)
    for tt, m, d in tl.theme_bar(0, tl.b1(bb), B1, semis=k):
        place(dry, (musicbox if tl.mood in ('warm', 'playful') else bell)(m + 12, d), tt, gain=.5, pan=.2, rev=.8)
    vn = tl.notes_of(tl.chord1(bb + 1))
    place(padbus, strings(vn + [vn[0] + 12], tl.BAR1 - .3, bright=.9, attack=1.8, release=.15), tl.b1(bb + 1),
          gain=.8, rev=.5)

    # ======== part 2
    groove = [s for s in tl.p2 if s['type'] not in ('dots', 'numbers', 'logo')]
    for s in tl.p2:
        for j in range(s['bars']):
            b = s['bar0'] + j
            t0 = tl.b2(b)
            ch = tl.chord2(b)
            notes = tl.notes_of(ch, 57)
            r = ch[0]
            ty = s['type']
            final = ty == 'logo'
            if final and j > 0:
                continue
            dur = tl.BAR2 * (2 if final else 1)
            intro = ty == 'dots'
            place(padbus, pad(notes, dur + .02, bright=.3 if intro else .8, attack=.6 if intro else .05,
                              release=3.0 if final else .4), t0, gain=.7 if intro else 1.0, rev=.5)
            if not intro:
                place(padbus, strings(notes + [notes[0] + 12, notes[1] + 12], dur, bright=1.2, attack=.1 if not final else .02,
                                      release=3.0 if final else .5), t0, gain=1.3 if final else 1.0, rev=.5)
            if ty not in ('dots', 'numbers', 'logo'):
                for x in (.5, 1.5, 2.5, 3.5):
                    for m in notes + [notes[0] + 12]:
                        if mood['stab'] == 'strings':
                            place(padbus, strings([m], B2 * .35, bright=1.2, attack=.01, release=.1), tl.b2(b, x), gain=.9,
                                  rev=.3)
                        elif mood['stab'] == 'pluck':
                            place(padbus, pluck(m + 12, .2), tl.b2(b, x), gain=.6, pan=rng.uniform(-.4, .4), rev=.3)
                        else:
                            place(padbus, brass(m, B2 * .35, .9), tl.b2(b, x), gain=.42, pan=rng.uniform(-.4, .4), rev=.3)
                half = ty == 'grid' and j == 0
                for i in range(16):
                    if i % 4 == 0 and not half:
                        continue
                    place(dry, bass(38 + r + (12 if i % 2 else 0), B2 * .2, 2.4), tl.b2(b, i * .25), gain=.75, rev=.02)
                for x in range(4):
                    place(dry, sub(26 + r + 12, B2 * .9), tl.b2(b, x), gain=.9, rev=0)
                arp = [notes[0] + 12, notes[2] + 12, notes[1] + 24, notes[2] + 12]
                for i in range(16):
                    place(dry, pluck(arp[i % 4], .12), tl.b2(b, i * .25), gain=.3 * (1.3 if i % 4 == 0 else 1),
                          pan=np.sin(i * 1.3) * .7, rev=.25)
            if ty == 'numbers':
                for x in (0, 2):
                    for m in notes + [notes[0] + 12, notes[0] - 12]:
                        place(dry, brass(m, B2 * 1.6, 1.0), tl.b2(b, x), gain=.6, rev=.4)
            if final:
                for m in [26 + r + 12, 38 + r] + notes + [n + 12 for n in notes]:
                    place(dry, piano(m, 3.5, .8), t0, gain=.6, rev=.6)
                place(dry, bass(38 + r, 3.0, 1.4), t0, gain=1.0, rev=.1)
                for tt, m, d in tl.theme_bar(0, tl.b2(b, 1), B2 * 1.5, semis=k + 2):
                    place(dry, (musicbox if tl.mood in ('warm', 'playful') else bell)(m + 12, d), tt, gain=.55, pan=.2,
                          rev=.8)
    # hook: the same motif, fast
    gb = [b for s in groove for b in range(s['bar0'], s['bar0'] + s['bars'])]
    for i, b in enumerate(gb):
        up = 12 if i >= 8 else 0
        for tt, m, d in tl.theme_bar(i % 8, tl.b2(b), B2, semis=k + 2):
            place(dry, brass(m + up, d, 1.0), tt, gain=1.0 if not up else .8, rev=.35)
            place(dry, pluck(m + 12 + up, d), tt, gain=.8, pan=.15, rev=.35)
            if up:
                place(dry, strings([m, m + 12], d, bright=1.3, attack=.03, release=.3), tt, gain=1.8, rev=.45)
    for t, i in tl.blips:
        place(dry, ping(74 + k + [0, 4, 7, 12, 16, 19, 24, 28][i], .8), t, gain=1.0, pan=(-1) ** i * .4, rev=.5)

    # ======== drums & fx
    for t, g in tl.kicks:
        place(dry, kick(g), t, rev=.03)
    for t, g in tl.claps:
        place(dry, clap(g), t, pan=.05, rev=.25)
    for t, g, kd in tl.hats:
        place(dry, hat(g, kd), t, pan=.25 if kd == 'c' else -.2, rev=.1)
    for t, g in tl.crashes:
        place(dry, crash(g, 4.0 if g >= 1 else 2.5), t, pan=-.1, rev=.4)
    for t, g in tl.booms:
        place(dry, boom(g), t, rev=.35)
    for t0, t1, g in tl.risers:
        place(dry, riser(t0, t1, g), t0, rev=.4)
    for t in tl.revcym:
        c = crash(.6, 2.0)[::-1] * np.linspace(0, 1, int(2.0 * SR)) ** 2
        place(dry, c, t - 2.0, rev=.3)
    for t in tl.whooshes:
        place(dry, whoosh(.9), t - .35, rev=.2)
    if nostalgia and mood['crackle']:
        L = min(17.0, tl.T2 * .3)
        t = tarr(L)
        cr = np.zeros_like(t)
        idx = rng.choice(len(t), int(40 * L), replace=False)
        cr[idx] = rng.uniform(-1, 1, len(idx))
        cr = fft_filter(cr, lo=1500) * 1.2 + fft_filter(rng.standard_normal(len(t)), lo=2000, hi=6000) * .01
        cr *= np.clip((L - t) / 3, 0, 1) * np.clip(t, 0, 1)
        place(dry, cr, 0, gain=.35, rev=0)

    # ======== mix
    duck = np.ones(N)
    first_groove = tl.b1(next((i for i, e in enumerate(tl.energy) if e != 'bridge' and e >= 2), tl.n1))
    for kt, g in tl.kicks:
        if kt < first_groove:
            continue
        i = int(kt * SR)
        n = min(int(.4 * SR), N - i)
        d = 1 - (.55 if kt >= tl.T2 else .4) * min(1, g) * np.exp(-np.arange(n) / SR / .1)
        duck[i:i + n] = np.minimum(duck[i:i + n], d)
    padbus_ = padbus * duck
    g0, g1 = int((tl.T2 - .12) * SR), int(tl.T2 * SR)
    ir_len = int(3.2 * SR)
    ti = np.arange(ir_len) / SR
    wet = np.zeros_like(dry)
    nfft = 1 << int(np.ceil(np.log2(N + ir_len)))
    for c in range(2):
        ir = fft_filter(rng.standard_normal(ir_len), hi=5500) * np.exp(-ti * 6.9 / 2.8)
        ir[:int(.012 * SR)] = 0
        ir /= np.sqrt((ir ** 2).sum())
        wet[c] = np.fft.irfft(np.fft.rfft(send[c], nfft) * np.fft.rfft(ir, nfft), nfft)[:N]
    mix = dry + padbus_ + wet * 0.5
    for c in range(2):
        mix[c] = fft_filter(mix[c], lo=30)
    mix[:, g0:g1] *= np.linspace(1, .05, max(1, g1 - g0))
    fade = int(1.2 * SR)
    mix[:, -fade:] *= np.linspace(1, 0, fade) ** 1.5
    mix = mix / (np.percentile(np.abs(mix), 99.95) + 1e-9) * 0.85
    mix = np.tanh(mix * 1.2) / np.tanh(1.2) * 0.95
    report = []
    marks = sorted(set([0.0, tl.b1(tl.n1 - 2), tl.T2] + [tl.b2(s['bar0']) for s in tl.p2] + [tl.DUR]))
    for a, b_ in zip(marks, marks[1:]):
        seg = mix[:, int(a * SR):int(b_ * SR)]
        if seg.size:
            report.append(f'{a:6.2f}-{b_:6.2f}s  rms {20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9):6.1f} dB')
    pcm = (np.clip(mix.T, -1, 1) * 32767).astype('<i2')
    with wave.open(out_path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return report
