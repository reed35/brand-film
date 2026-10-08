"""bf_tts -- voice-over for the brand films with Gemini TTS (gemini-3.8-flash-tts), plus a music ducker.

Docs (2026-10): https://ai.google.dev/gemini-api/docs/speech-generation
  POST https://generativelanguage.googleapis.com/v1beta/interactions   (header x-goog-api-key)
  text = verbatim transcript; delivery/pace go in speech_metadata.style; inline <pause>-style tags for momentary events.
  Unary output = WAV (RIFF), 24 kHz mono s16le.

API keys come from two slots: "primary" = $GEMINI_API_KEY and "backup" = $GEMINI_API_KEY_2. Key values are only ever
sent in a request header. They are never printed, logged, written to disk, or put in a URL; error text is scrubbed of both.
Key fallback: when the active slot gets HTTP 429 (rate limit / daily quota) or 402 (prepay credits depleted), the request is
re-sent right away with the other slot, and that slot stays active for the rest of the run. This works in both directions.
A slot that got a short "retry in Ns" hint can be used again once the hint has passed; a daily quota or a 402 blocks it for
the whole run. The manifest records the slot name (never the value) behind every item.
$BF_TTS_FORCE_KEY=primary|backup pins one slot and turns fallback off (for testing); empty/auto = primary first, then fallback.

CLI
  python bf_tts.py say  --text "..." --voice Charon --style "cinematic documentary narrator, measured" --out vo.wav
  python bf_tts.py say  --text-file line.txt ... [--model gemini-3.8-flash-tts] [--dry-run]
  python bf_tts.py models [--require gemini-3.8-flash-tts]   # TTS models visible to this key
  python bf_tts.py batch --spec job.json --outdir tts_out     # many lines -> WAVs + manifest.json
     job.json = {"model": "...", "style": "default style", "voice": "Charon", "rpm": 3, "retries": 6,
                 "lines": [{"text": "...", "voice": "Sulafat", "style": "...", "out": "zh_sulafat"}, ...]}
  python bf_tts.py voices [--lang zh-CN]        # Extended Voice Library
  python bf_tts.py duck --music mix.wav --vo vo.wav --at 12.5 [--vo vo2.wav --at 40] --out mix_vo.wav [--depth -9]
Python
  from bf_tts import synth, duck
  synth("朱雀三号遥二……", "Charon", "沉稳的纪录片旁白", "vo_zh.wav")
  duck("out/mix.wav", [("vo_zh.wav", 12.5)], "out/mix_vo.wav")
"""
import os, sys, io, json, base64, wave, time, argparse, urllib.request, urllib.error, urllib.parse
import numpy as np

API = 'https://generativelanguage.googleapis.com/v1beta'
MODEL = 'gemini-3.8-flash-tts'
VOICES = ['Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', 'Leda', 'Orus', 'Aoede', 'Callirrhoe', 'Autonoe', 'Enceladus', 'Iapetus',
          'Umbriel', 'Algieba', 'Despina', 'Erinome', 'Algenib', 'Rasalgethi', 'Laomedeia', 'Achernar', 'Alnilam', 'Schedar', 'Gacrux',
          'Pulcherrima', 'Achird', 'Zubenelgenubi', 'Vindemiatrix', 'Sadachbia', 'Sadaltager', 'Sulafat']
DOC_STYLE = 'cinematic documentary narrator: calm, measured, warm authority, unhurried pace'


class TTSError(RuntimeError):
    pass


EVENTS = []          # HTTP error events (429 quota details etc.), scrubbed; run_batch stores them per line
RETRIES = 6


def _quota_details(err):
    """Pull QuotaFailure / RetryInfo out of a Google API error body."""
    out = {}
    for d in err.get('details', []) or []:
        t = d.get('@type', '')
        if t.endswith('QuotaFailure'):
            out['violations'] = [{k: v.get(k) for k in ('quotaMetric', 'quotaId', 'quotaDimensions', 'quotaValue')}
                                 for v in d.get('violations', [])]
        elif t.endswith('RetryInfo'):
            out['retryDelay'] = d.get('retryDelay')
        elif t.endswith('ErrorInfo'):
            out['reason'], out['metadata'] = d.get('reason'), d.get('metadata')
    return out


KEY_SLOTS = (('primary', 'GEMINI_API_KEY'), ('backup', 'GEMINI_API_KEY_2'))
ACTIVE = None        # active slot name; picked lazily, then sticky for the rest of the run
BLOCKED = {}         # slot -> time.time() until which it is blocked (float('inf') = for the rest of this run)
LAST_SLOT = None     # slot that produced the most recent successful response
SWITCHES = []        # key-slot switches, e.g. {'t', 'from', 'to', 'code'}


def _slot_key(slot):
    return os.environ.get(dict(KEY_SLOTS)[slot], '')


def _forced():
    f = os.environ.get('BF_TTS_FORCE_KEY', '').strip().lower()
    if f in ('', 'auto'):
        return None
    if f not in dict(KEY_SLOTS):
        raise TTSError(f'BF_TTS_FORCE_KEY must be auto, primary or backup (got {f!r})')
    return f


def _slots():
    """Slots allowed in this run, in preference order (only the configured ones)."""
    f = _forced()
    names = [f] if f else [n for n, _ in KEY_SLOTS]
    have = [n for n in names if _slot_key(n)]
    if not have:
        raise TTSError(('the forced key slot %r has no key' % f) if f else 'neither GEMINI_API_KEY nor GEMINI_API_KEY_2 is set')
    return have


def _active():
    global ACTIVE
    if ACTIVE not in _slots():
        ACTIVE = _slots()[0]
    return ACTIVE


def _key():
    return _slot_key(_active())


def _scrub(s):
    for _, env in KEY_SLOTS:
        k = os.environ.get(env, '')
        if k:
            s = s.replace(k, '***')
    return s


def _retry_wait(msg, err_details, attempt):
    """Seconds the server wants us to wait (hint in message or RetryInfo), else exponential backoff."""
    import re
    hint = re.search(r'retry in ((?:\d+h)?(?:\d+m)?(?:[0-9.]+s)?)', msg)
    rd = (err_details or {}).get('retryDelay')
    src = hint.group(1) if hint and hint.group(1) else (rd if isinstance(rd, str) else '')
    if src:
        hms = dict((u, float(v)) for v, u in re.findall(r'([0-9.]+)([hms])', src))
        return hms.get('h', 0) * 3600 + hms.get('m', 0) * 60 + hms.get('s', 0) + 1.5, True
    return min(60, 4 * 2 ** attempt), False


def _call(method, path, body=None, query=None, timeout=180, retries=None):
    """One API call with key-slot fallback. Retries (429/500/503 waits, network) are limited to `retries`;
    an immediate switch to the other key slot does not use up a retry."""
    global ACTIVE, LAST_SLOT
    retries = retries or RETRIES
    url = f'{API}/{path}' + ('?' + urllib.parse.urlencode(query, doseq=True) if query else '')
    data = json.dumps(body).encode() if body is not None else None
    attempt, switches = 0, 0
    while True:
        slot = _active()
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={'x-goog-api-key': _key(), 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read())
            LAST_SLOT = slot
            return out
        except urllib.error.HTTPError as e:
            txt = e.read().decode('utf-8', 'replace')
            err = {}
            try:
                body_ = json.loads(txt)
                err = (body_[0] if isinstance(body_, list) and body_ else body_).get('error', {})   # 402 prepay returns a list
                msg = f"HTTP {e.code} {err.get('status', '')}: {err.get('message', '')}"
            except Exception:
                msg = f'HTTP {e.code}: {txt[:300]}'
            qd = _quota_details(err)
            ev = json.loads(_scrub(json.dumps({'t': time.strftime('%H:%M:%S'), 'key_slot': slot, 'code': e.code,
                                               'status': err.get('status'), 'message': err.get('message'), **qd})))
            EVENTS.append(ev)
            print('  HTTP event: ' + json.dumps(ev, ensure_ascii=False), file=sys.stderr, flush=True)
            if e.code in (429, 402):
                wait, hinted = _retry_wait(msg, qd, attempt)
                # 402 (no credits) or a long / daily-quota 429: this slot is done for the run. Short hint: blocked until it passes.
                daily = 'per day' in msg.lower() or any('PerDay' in str(v.get('quotaId', '')) for v in qd.get('violations', []))
                BLOCKED[slot] = float('inf') if (e.code == 402 or wait > 120 or daily) else time.time() + wait
                now = time.time()
                others = [s_ for s_ in _slots() if s_ != slot and BLOCKED.get(s_, 0) <= now]
                if others and switches < 2 * len(KEY_SLOTS):
                    ACTIVE = others[0]
                    switches += 1
                    SWITCHES.append({'t': time.strftime('%H:%M:%S'), 'from': slot, 'to': ACTIVE, 'code': e.code})
                    print(f'  {e.code} on {slot} key -> switching to {ACTIVE} key now', file=sys.stderr, flush=True)
                    continue
                # every allowed slot is blocked: wait for the soonest one if that is short, else give up
                soon = min(_slots(), key=lambda s_: BLOCKED.get(s_, 0))
                wait = BLOCKED.get(soon, 0) - now
                if e.code == 429 and wait <= 120 and attempt < retries - 1:
                    attempt += 1
                    print(f'  429, all key slots limited; retrying on {soon} in {max(wait, 0):.0f}s', file=sys.stderr, flush=True)
                    time.sleep(max(wait, 0))
                    if soon != slot:
                        SWITCHES.append({'t': time.strftime('%H:%M:%S'), 'from': slot, 'to': soon, 'code': e.code,
                                         'waited_s': round(max(wait, 0), 1)})
                    ACTIVE = soon
                    continue
                raise TTSError(_scrub(msg) + f' [key slot: {slot}; no other key slot available]') from None
            if e.code in (500, 503) and attempt < retries - 1:
                wait, _ = _retry_wait(msg, qd, attempt)
                wait = min(wait, 60)
                attempt += 1
                print(f'  {e.code}, retrying in {wait:.0f}s', file=sys.stderr, flush=True)
                time.sleep(wait)
                continue
            raise TTSError(_scrub(msg) + f' [key slot: {slot}]') from None
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                attempt += 1
                time.sleep(2)
                continue
            raise TTSError(_scrub(f'network error: {e.reason}')) from None


def build_request(text, voice='Charon', style=DOC_STYLE, model=MODEL, sample_rate=None):
    """Interactions-API body for one single-speaker turn (text read verbatim; style = sustained delivery)."""
    item = {'type': 'text', 'text': text}
    if style:
        item['annotations'] = [{'type': 'speech_metadata', 'style': style}]
    rf = {'type': 'audio'}
    if sample_rate:
        rf['sample_rate'] = int(sample_rate)
    return {'model': model, 'input': [{'type': 'user_input', 'content': [item]}], 'response_format': rf,
            'generation_config': {'speech_config': [{'voice': voice}]}}


def build_dialogue(turns, speakers, model=MODEL):
    """turns = [(speaker, text, style)], speakers = {speaker: voice} (max 2 prebuilt voices per request)."""
    content = [{'type': 'text', 'text': t, 'annotations': [dict({'type': 'speech_metadata', 'speaker': sp}, **({'style': st} if st else {}))]}
               for sp, t, st in turns]
    return {'model': model, 'input': [{'type': 'user_input', 'content': content}], 'response_format': {'type': 'audio'},
            'generation_config': {'speech_config': {'speakers': [{'speaker': s, 'voice': v} for s, v in speakers.items()]}}}


def _audio_bytes(resp):
    blocks = [c for st in resp.get('steps', []) if st.get('type') == 'model_output'
              for c in st.get('content', []) if c.get('type') == 'audio' and c.get('data')]
    if not blocks:                                   # SDK-style convenience field, if present
        oa = resp.get('output_audio') or {}
        if oa.get('data'):
            blocks = [oa]
    if not blocks:
        raise TTSError('no audio in response: ' + _scrub(json.dumps(resp)[:300]))
    return base64.b64decode(blocks[-1]['data']), blocks[-1].get('mime_type', 'audio/wav')


def _to_wav(raw, mime, out_path, sr=24000):
    if raw[:4] == b'RIFF':
        open(out_path, 'wb').write(raw)
        return
    with wave.open(out_path, 'wb') as w:                # headerless L16 (stream / mime_type audio/l16)
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(raw)


def synth(text, voice='Charon', style=DOC_STYLE, out_path='vo.wav', model=MODEL, trim=True):
    """text -> WAV file (24 kHz mono). Returns (out_path, seconds)."""
    resp = _call('POST', 'interactions', build_request(text, voice, style, model))
    raw, mime = _audio_bytes(resp)
    _to_wav(raw, mime, out_path)
    if trim:
        trim_silence(out_path)
    with wave.open(out_path) as w:
        return out_path, w.getnframes() / w.getframerate()


def dialogue(turns, speakers, out_path, model=MODEL):
    resp = _call('POST', 'interactions', build_dialogue(turns, speakers, model))
    raw, mime = _audio_bytes(resp)
    _to_wav(raw, mime, out_path)
    return out_path


def list_models():
    out, tok = [], None
    while True:
        d = _call('GET', 'models', query=dict(pageSize=1000, **({'pageToken': tok} if tok else {})))
        out += d.get('models', [])
        tok = d.get('nextPageToken')
        if not tok:
            return out


def list_voices(**filters):
    return _call('GET', 'voices', query={k: v for k, v in filters.items() if v}).get('voices', [])


# ------------------------------------------------------------------ audio utilities (no API needed)
def read_wav(p):
    with wave.open(p) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, ch), sr


def write_wav(p, a, sr):
    a = np.atleast_2d(a.T).T if a.ndim == 1 else a
    with wave.open(p, 'wb') as w:
        w.setnchannels(a.shape[1]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype('<i2').tobytes())


def trim_silence(p, thresh_db=-50, pad=.06):
    a, sr = read_wav(p)
    e = np.abs(a).max(1)
    idx = np.nonzero(e > 10 ** (thresh_db / 20))[0]
    if len(idx):
        i0, i1 = max(0, idx[0] - int(pad * sr)), min(len(a), idx[-1] + int(pad * sr))
        write_wav(p, a[i0:i1], sr)


def _resample(x, sr0, sr1):
    if sr0 == sr1:
        return x
    from scipy.signal import resample_poly
    from math import gcd
    g = gcd(sr0, sr1)
    return resample_poly(x, sr1 // g, sr0 // g, axis=0)


def duck(music_path, vo_items, out_path, depth_db=-9.0, attack=.08, release=.45, lookahead=.12, hold=.6, vo_gain_db=0.0,
         vo_hp=90.0, ceiling=.89, return_gain=False):
    """Mix voice-over over music and duck the music under it (sidechain from the VO envelope).
    vo_items = [(vo_wav, start_seconds), ...]. depth_db = music gain while the voice speaks; the duck starts
    `lookahead` s before each phrase (attack), holds through pauses shorter than `hold` s, and recovers with `release`. Peak ceiling ~ -1 dBFS (sample peak)."""
    from scipy.signal import butter, sosfilt
    from scipy.ndimage import uniform_filter1d, maximum_filter1d, minimum_filter1d
    music, sr = read_wav(music_path)
    if music.shape[1] == 1:
        music = np.repeat(music, 2, 1)
    N = len(music)
    vo_bus = np.zeros((N, 2), np.float32)
    for path, t0 in vo_items:
        v, vsr = read_wav(path)
        v = _resample(v.mean(1), vsr, sr)
        if vo_hp:
            v = sosfilt(butter(2, vo_hp, 'high', fs=sr, output='sos'), v)
        i0 = int(round(t0 * sr))
        n = min(len(v), N - i0)
        if n > 0:
            vo_bus[i0:i0 + n] += (v[:n] * 10 ** (vo_gain_db / 20))[:, None]
    env = uniform_filter1d(np.abs(vo_bus[:, 0]), int(.03 * sr))
    speaking = (env > 10 ** (-45 / 20)).astype(np.float32)
    speaking = maximum_filter1d(speaking, int(hold * sr), origin=(int(hold * sr) - 1) // 2)  # hold through pauses < `hold` s
    la = int(lookahead * sr)
    speaking = np.concatenate([speaking[la:], np.zeros(la, np.float32)]) if la else speaking
    g_low = 10 ** (depth_db / 20)
    target = 1 - (1 - g_low) * speaking
    g = np.empty(N, np.float32)
    ka, kr = 1 - np.exp(-1 / (attack * sr)), 1 - np.exp(-1 / (release * sr))
    cur = 1.0
    for i0 in range(0, N, 64):                                           # block-wise one-pole smoothing
        tgt = target[i0:i0 + 64].min()
        k = ka if tgt < cur else kr
        cur += (tgt - cur) * (1 - (1 - k) ** 64)
        g[i0:i0 + 64] = cur
    mix = music * g[:, None] + vo_bus
    w = int(.005 * sr)                                                   # 5 ms look-around peak limiter
    lim = np.minimum(1, ceiling / np.maximum(np.abs(mix).max(1), 1e-6))
    lim = uniform_filter1d(minimum_filter1d(lim, 2 * w + 1), w)
    mix *= lim[:, None]
    write_wav(out_path, mix, sr)
    info = dict(min_music_gain_db=float(20 * np.log10(g.min() + 1e-9)), peak=float(np.abs(mix).max()))
    if return_gain:
        info['gain'], info['sr'] = g, sr
    return info


def run_batch(spec, outdir, sleep=None):
    """spec dict -> WAVs in outdir + manifest.json. Keeps going on per-line errors; returns the manifest.
    spec["rpm"] paces requests (free tier = 3/min -> use 3); 429s are retried after the server's hint anyway."""
    global RETRIES
    sleep = sleep if sleep is not None else (60.0 / spec['rpm'] if spec.get('rpm') else 1.0)
    RETRIES = int(spec.get('retries', RETRIES))
    os.makedirs(outdir, exist_ok=True)
    model, dstyle, dvoice = spec.get('model', MODEL), spec.get('style', DOC_STYLE), spec.get('voice', 'Charon')
    man = {'model': model, 'force_key': _forced() or 'auto', 'key_slots_allowed': _slots(), 'items': []}
    for i, ln in enumerate(spec['lines']):
        name = os.path.basename(ln.get('out') or f'line_{i:02d}')
        name = name if name.endswith('.wav') else name + '.wav'
        it = {'out': name, 'voice': ln.get('voice', dvoice), 'style': ln.get('style', dstyle), 'text': ln['text']}
        t0 = time.time()
        n_ev = len(EVENTS)
        it['started'] = time.strftime('%H:%M:%S')
        try:
            _, sec = synth(ln['text'], it['voice'], it['style'], os.path.join(outdir, name), ln.get('model', model))
            it.update(ok=True, seconds=round(sec, 3), key_slot=LAST_SLOT)      # slot NAME only, never the key
        except Exception as e:
            it.update(ok=False, error=_scrub(str(e)), key_slot=None, last_tried_slot=ACTIVE)
        it['wall_s'] = round(time.time() - t0, 2)
        if len(EVENTS) > n_ev:
            it['http_events'] = EVENTS[n_ev:]
        wait = sleep - (time.time() - t0)
        print(('OK  ' if it['ok'] else 'ERR ') + f"{name} voice={it['voice']} key={it['key_slot'] or '-'} "
              + (f"{it.get('seconds')}s" if it['ok'] else it['error']), flush=True)
        man['items'].append(it)
        if i < len(spec['lines']) - 1 and wait > 0:
            time.sleep(wait)
    man['key_switches'] = SWITCHES
    man['key_slot_counts'] = {n: sum(1 for x in man['items'] if x.get('key_slot') == n) for n, _ in KEY_SLOTS}
    json.dump(man, open(os.path.join(outdir, 'manifest.json'), 'w'), ensure_ascii=False, indent=1)
    return man


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('say'); s.add_argument('--text'); s.add_argument('--text-file'); s.add_argument('--voice', default='Charon')
    s.add_argument('--style', default=DOC_STYLE); s.add_argument('--out', default='vo.wav'); s.add_argument('--model', default=MODEL)
    s.add_argument('--dry-run', action='store_true')
    mo = sp.add_parser('models'); mo.add_argument('--require'); mo.add_argument('--all', action='store_true')
    bt = sp.add_parser('batch'); bt.add_argument('--spec', required=True); bt.add_argument('--outdir', default='tts_out')
    v = sp.add_parser('voices'); v.add_argument('--lang'); v.add_argument('--gender'); v.add_argument('--search')
    d = sp.add_parser('duck'); d.add_argument('--music', required=True); d.add_argument('--vo', action='append', required=True)
    d.add_argument('--at', action='append', type=float, required=True); d.add_argument('--out', required=True)
    d.add_argument('--depth', type=float, default=-9.0)
    a = ap.parse_args()
    try:
        if a.cmd == 'say':
            text = a.text if a.text is not None else open(a.text_file, encoding='utf-8').read().strip()
            if a.dry_run:
                print(json.dumps(build_request(text, a.voice, a.style, a.model), ensure_ascii=False, indent=1))
                return
            p, sec = synth(text, a.voice, a.style, a.out, a.model)
            print(f'wrote {p} ({sec:.2f} s) with the {LAST_SLOT} key')
        elif a.cmd == 'models':
            global ACTIVE
            slots = _slots()
            print('key slots configured: ' + ', '.join(n + ('=set' if _slot_key(n) else '=unset') for n, _ in KEY_SLOTS)
                  + f"; force_key={_forced() or 'auto'}")
            for sl in slots[1:]:                               # quick GET per extra slot (no TTS cost, no fallback)
                ACTIVE = sl
                saved = BLOCKED.copy(); BLOCKED.update({o: float('inf') for o in slots if o != sl})
                try:
                    ok_ = any(m['name'] in (a.require or MODEL, 'models/' + (a.require or MODEL)) for m in list_models())
                    print(f"slot {sl}: key accepted, {a.require or MODEL} {'FOUND' if ok_ else 'MISSING'}")
                except TTSError as e:
                    print(f'slot {sl}: ERROR {e}')
                BLOCKED.clear(); BLOCKED.update(saved)
            ACTIVE = slots[0]
            ms = list_models()
            print(f'slot {LAST_SLOT}: {len(ms)} models visible to this key; TTS models:')
            for m in ms:
                if a.all or 'tts' in m['name'] or 'speech' in m.get('displayName', '').lower():
                    print(' ', m['name'], '|', m.get('displayName', ''), '|', ','.join(m.get('supportedGenerationMethods', [])),
                          '| in', m.get('inputTokenLimit'), 'out', m.get('outputTokenLimit'))
            if a.require:
                ok = any(m['name'] in (a.require, 'models/' + a.require) for m in ms)
                print(f"REQUIRE {a.require}: {'FOUND' if ok else 'MISSING'}")
                if not ok:
                    sys.exit(3)
        elif a.cmd == 'batch':
            man = run_batch(json.load(open(a.spec, encoding='utf-8')), a.outdir)
            bad = [i for i in man['items'] if not i['ok']]
            print(f"{len(man['items']) - len(bad)}/{len(man['items'])} lines OK")
            if bad:
                sys.exit(4)
        elif a.cmd == 'voices':
            for x in list_voices(language_code=a.lang, gender=a.gender, search=a.search):
                print(x.get('id') or x.get('name'), '|', x.get('display_name') or x.get('displayName'), '|', x.get('language_code'),
                      '|', x.get('description', '')[:80])
        elif a.cmd == 'duck':
            if len(a.vo) != len(a.at):
                ap.error('give one --at per --vo')
            print(duck(a.music, list(zip(a.vo, a.at)), a.out, a.depth))
    except TTSError as e:
        print(f'bf_tts error: {e}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
