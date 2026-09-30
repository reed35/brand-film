"""Timeline builder: turns film.json into bars, chords, drum events and visual cue points.
Music and picture both read this, so every cut lands on the beat."""

KEYS = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
        'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}

PART2_BARS = {'dots': 2, 'slam': 2, 'shapes': 2, 'grid': 2, 'cloud': 2, 'ribbon': 2, 'words': 2, 'numbers': 1,
              'logo': 2}
PART1_TYPES = {'origin', 'milestone', 'city', 'network', 'bridge', 'custom'}
PROG = [(0, 'M'), (7, 'M'), (9, 'm'), (5, 'M')]      # I V vi IV (relative)
TAIL = 0.6
MAX_DUR = 90.0

# 8-bar motifs (bar, beat, midi around C5, dur_beats); every motif fits I-V-vi-IV
THEMES = {
    'uplift': [(0, 0, 76, 1.5), (0, 1.5, 74, .5), (0, 2, 72, 1), (0, 3, 67, 1), (1, 0, 74, 1.5), (1, 1.5, 76, .5),
               (1, 2, 74, 1), (1, 3, 71, 1), (2, 0, 72, 1), (2, 1, 76, 1), (2, 2, 81, 1.5), (2, 3.5, 79, .5),
               (3, 0, 77, 1), (3, 1, 76, 1), (3, 2, 72, 2), (4, 0, 76, 1.5), (4, 1.5, 74, .5), (4, 2, 72, 1),
               (4, 3, 79, 1), (5, 0, 79, 1.5), (5, 1.5, 81, .5), (5, 2, 79, 1), (5, 3, 74, 1), (6, 0, 76, 1),
               (6, 1, 81, 1), (6, 2, 84, 1.5), (6, 3.5, 83, .5), (7, 0, 81, 1), (7, 1, 79, 1), (7, 2, 79, 2)],
    'noble': [(0, 0, 72, 2), (0, 2, 76, 2), (1, 0, 74, 3), (1, 3, 71, 1), (2, 0, 72, 2), (2, 2, 69, 2),
              (3, 0, 72, 1), (3, 1, 74, 1), (3, 2, 77, 2), (4, 0, 79, 2), (4, 2, 76, 2), (5, 0, 74, 3),
              (5, 3, 79, 1), (6, 0, 81, 2), (6, 2, 76, 1), (6, 3, 72, 1), (7, 0, 77, 2), (7, 2, 74, 2)],
    'bright': [(0, 0, 72, .5), (0, .5, 76, .5), (0, 1, 79, 1), (0, 2, 84, 1), (0, 3, 79, 1), (1, 0, 79, .5),
               (1, .5, 83, .5), (1, 1, 86, 1), (1, 2, 83, 1), (1, 3, 79, 1), (2, 0, 81, .5), (2, .5, 84, .5),
               (2, 1, 88, 1), (2, 2, 84, 1.5), (2, 3.5, 81, .5), (3, 0, 81, 1), (3, 1, 77, 1), (3, 2, 72, 2),
               (4, 0, 72, .5), (4, .5, 76, .5), (4, 1, 79, 1), (4, 2, 84, 1), (4, 3, 88, 1), (5, 0, 86, 1.5),
               (5, 1.5, 83, .5), (5, 2, 79, 2), (6, 0, 81, 1), (6, 1, 84, 1), (6, 2, 88, 1), (6, 3, 86, 1),
               (7, 0, 84, 1), (7, 1, 81, 1), (7, 2, 79, 2)],
}


class Timeline:
    def __init__(self, cfg):
        m = cfg.get('music', {})
        k = m.get('key', 'C')
        self.key = KEYS.get(k, k) if isinstance(k, str) else int(k)
        self.bpm1 = float(m.get('bpm1', 96))
        self.bpm2 = float(m.get('bpm2', 128))
        self.mood = m.get('mood', 'warm')
        self.theme = THEMES[m.get('theme', 'uplift')]
        self.BEAT1 = 60 / self.bpm1
        self.BAR1 = 4 * self.BEAT1
        self.BEAT2 = 60 / self.bpm2
        self.BAR2 = 4 * self.BEAT2

        self.p1 = [dict(s) for s in cfg['part1']['scenes']]
        if not self.p1 or self.p1[-1]['type'] != 'bridge':
            self.p1.append({'type': 'bridge', 'text': cfg.get('bridge_text', '')})
        self.p1[-1]['bars'] = 2
        bar = 0
        for s in self.p1:
            s['bars'] = int(s.get('bars', 3))
            s['bar0'] = bar
            bar += s['bars']
        self.n1 = bar
        self.T2 = self.n1 * self.BAR1

        self.p2 = [dict(s) for s in cfg['part2']['sections']]
        bar = 0
        for s in self.p2:
            s['bars'] = int(s.get('bars', PART2_BARS.get(s['type'], 2))) if s['type'] == 'custom' else PART2_BARS[s['type']]
            s['bar0'] = bar
            bar += s['bars']
        self.n2 = bar
        self.DUR = self.T2 + self.n2 * self.BAR2 + TAIL

        nb = self.n1 - 2
        self.energy = []
        for s in self.p1:
            for j in range(s['bars']):
                b = s['bar0'] + j
                if s['type'] == 'bridge':
                    e = 'bridge'
                elif 'energy' in s:
                    e = int(s['energy'])
                else:
                    f = b / max(1, nb)
                    e = 0 if f < .25 else 1 if f < .5 else 2 if f < .75 else 3
                self.energy.append(e)
        self._drums()

    # ---- time helpers
    def b1(self, bar, beat=0.0):
        return bar * self.BAR1 + beat * self.BEAT1

    def b2(self, bar, beat=0.0):
        return self.T2 + bar * self.BAR2 + beat * self.BEAT2

    def scene1_window(self, i):
        s = self.p1[i]
        a, b = self.b1(s['bar0']), self.b1(s['bar0'] + s['bars'])
        return (0.0 if i == 0 else a - .4), (self.T2 if i == len(self.p1) - 1 else b + .4), a, b

    def section2_at(self, t):
        bar = int((t - self.T2) // self.BAR2)
        for s in self.p2:
            if s['bar0'] <= bar < s['bar0'] + s['bars']:
                return s
        return self.p2[-1]

    # ---- harmony (relative to key)
    def chord1(self, bar):
        if bar == self.n1 - 1:
            return ((9 + self.key) % 12, 'M')           # V of part-2 key
        r, q = PROG[(bar + 2) % 4]
        return ((r + self.key) % 12, q)

    def chord2(self, bar):
        k2 = self.key + 2
        s = None
        for x in self.p2:
            if x['bar0'] <= bar < x['bar0'] + x['bars']:
                s = x
        nxt = [x for x in self.p2 if x['bar0'] == bar + 1]
        if s and s['type'] == 'logo':
            return (k2 % 12, 'M')
        if s and s['type'] == 'numbers':
            return ((k2 + 7) % 12, 'M')
        if nxt and nxt[0]['type'] in ('numbers', 'logo'):
            return ((k2 + 5) % 12, 'M')
        r, q = PROG[bar % 4]
        return ((r + k2) % 12, q)

    @staticmethod
    def notes_of(ch, low=55):
        r, q = ch
        pcs = [r, (r + (4 if q == 'M' else 3)) % 12, (r + 7) % 12]
        return sorted(low + ((pc - low) % 12) for pc in pcs)

    def theme_bar(self, theme_bar_idx, start, beat, semis=0):
        return [(start + bb * beat, m + semis, d * beat) for b, bb, m, d in self.theme if b == theme_bar_idx]

    # ---- drums & cues
    def _drums(self):
        K, C, Hh, Cr, Bo, Ri, Rv, Wh, Bl = [], [], [], [], [], [], [], [], []
        b1, b2 = self.b1, self.b2
        prev = None
        for b, e in enumerate(self.energy):
            if e == 'bridge':
                continue
            if e >= 1 and e != prev and prev is not None:
                Cr.append((b1(b), .3 + .15 * e))
            if e == 3 and prev != 3:
                Bo.append((b1(b), .6))
            if e == 1:
                for x in (0, 2):
                    K.append((b1(b, x), .55))
                for i in range(8):
                    Hh.append((b1(b, i * .5), .10 if i % 2 == 0 else .16, 'c'))
            elif e >= 2:
                full = e == 3
                for x in ((0, 1, 2, 3) if full else (0, 2, 2.5)):
                    K.append((b1(b, x), .85 if full else .8))
                for x in (1, 3):
                    C.append((b1(b, x), .6))
                st = .25 if full else .5
                for i in range(int(4 / st)):
                    Hh.append((b1(b, i * st), (.12 if full else .14) + (.08 if i % 2 else 0), 'c'))
            prev = e
        last = self.n1 - 3
        if last >= 0 and self.energy[last] != 'bridge' and self.energy[last] >= 2:
            for i in range(4):
                C.append((b1(last, 3 + i * .25), .3 + i * .1))
        Bo.append((b1(self.n1 - 2), .45))
        Ri.append((b1(self.n1 - 1), b1(self.n1) - .15, .55))
        Rv.append(self.T2)

        self.drop = None
        self.whips, self.shakes, self.flashes2 = [], [], []
        types = [s['type'] for s in self.p2]
        for idx, s in enumerate(self.p2):
            sb, ty = s['bar0'], s['type']
            prevt = types[idx - 1] if idx else None
            if ty == 'dots':
                for i in range(8):
                    Bl.append((b2(sb, i * .5), i))
                for x in range(4):
                    K.append((b2(sb + 1, x), .45))
                for i in range(12):
                    C.append((b2(sb + 1, 1 + i * .25), .15 + .5 * i / 11))
                Ri.append((b2(sb), b2(sb + 1, 3.6), .5))
                continue
            if ty == 'logo':
                Bo.append((b2(sb), 1.2))
                Cr.append((b2(sb), 1.0))
                K.append((b2(sb), 1.2))
                Wh.append(b2(sb))
                self.shakes.append((b2(sb), 8))
                continue
            if ty == 'numbers':
                for x in range(4):
                    K.append((b2(sb, x), 1.1))
                for x in (0, 2):
                    Bo.append((b2(sb, x), 1.0))
                    Cr.append((b2(sb, x), .85))
                    self.shakes.append((b2(sb, x), 13))
                Wh.append(b2(sb, 2))
                if prevt not in ('dots',):
                    self.whips.append(b2(sb))
                continue
            if self.drop is None:
                self.drop = b2(sb)
                Bo.append((b2(sb), 1.0))
                self.shakes.append((b2(sb), 12))
                self.flashes2.append((b2(sb), .35, 9))
            elif prevt != 'dots':
                self.whips.append(b2(sb))
            if ty == 'cloud':
                Bo.append((b2(sb), 1.0))
                self.shakes.append((b2(sb), 10))
                self.flashes2.append((b2(sb), .2, 9))
            Cr.append((b2(sb), .8 if b2(sb) == self.drop else .55))
            Wh.append(b2(sb))
            for j in range(s['bars']):
                bb = sb + j
                half = ty == 'grid' and j == 0
                for x in ((0, 2.5) if half else range(4)):
                    K.append((b2(bb, x), 1.0))
                if not half:
                    for x in (1, 3):
                        C.append((b2(bb, x), .75))
                for i in range(16):
                    Hh.append((b2(bb, i * .25), .10 + (.08 if i % 2 else 0), 'c'))
                for x in (.5, 1.5, 2.5, 3.5):
                    Hh.append((b2(bb, x), .12, 'o'))
            nxt = types[idx + 1] if idx + 1 < len(types) else None
            if nxt in ('numbers', 'logo') and s['bars'] >= 2:
                lb = sb + s['bars'] - 1
                for i in range(16):
                    C.append((b2(lb, i * .25), .2 + .6 * i / 15))
                Ri.append((b2(lb - 1, 2), b2(lb + 1) - .05, .7))
        self.kicks, self.claps, self.hats, self.crashes, self.booms = K, C, Hh, Cr, Bo
        self.risers, self.revcym, self.whooshes, self.blips = Ri, Rv, Wh, Bl
        self.kick_times = sorted(t for t, _ in K)

    def summary(self):
        rows = [f'Part 1  {self.bpm1:.0f} BPM  bar={self.BAR1:.3f}s  key offset {self.key}']
        for s in self.p1:
            rows.append(f'  {self.b1(s["bar0"]):6.2f}-{self.b1(s["bar0"] + s["bars"]):6.2f}s  {s["type"]:9s} '
                        f'{s.get("title") or (s.get("items") or [{}])[0].get("title") or s.get("text") or ""}')
        rows.append(f'Part 2  {self.bpm2:.0f} BPM  bar={self.BAR2:.3f}s  starts {self.T2:.2f}s')
        for s in self.p2:
            rows.append(f'  {self.b2(s["bar0"]):6.2f}-{self.b2(s["bar0"] + s["bars"]):6.2f}s  {s["type"]:9s} '
                        f'{s.get("title") or s.get("line1") or ""}')
        rows.append(f'TOTAL {self.DUR:.2f}s  (limit {MAX_DUR:.0f}s)')
        return '\n'.join(rows)

    def validate(self):
        errs = []
        if self.DUR > MAX_DUR + 1e-6:
            errs.append(f'duration {self.DUR:.2f}s exceeds {MAX_DUR}s: remove part-1 bars or part-2 sections')
        if self.DUR < 45:
            errs.append(f'duration {self.DUR:.2f}s is short (<45s); add scenes')
        for s in self.p1:
            if s['type'] not in PART1_TYPES:
                errs.append(f'unknown part1 type {s["type"]}')
        types = [s['type'] for s in self.p2]
        for ty in types:
            if ty not in PART2_BARS and ty != 'custom':
                errs.append(f'unknown part2 type {ty}')
        if types and types[0] != 'dots':
            errs.append('part2 must start with "dots" (it continues the bridge dot)')
        if types and types[-1] != 'logo':
            errs.append('part2 must end with "logo"')
        return errs
