#!/usr/bin/env python3
"""Render a private-data-safe Codex token city from account-reported daily buckets."""
import argparse
import base64
import datetime as dt
import html
import json
import math
import pathlib
import queue
import shutil
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

REPO = 'Ryanhu2001/Ryanhu2001'
FILES = ('codex-city.json', 'codex-city.svg', 'codex-city-mobile.svg')
UTC = dt.timezone.utc


def read_usage():
    binary = shutil.which('codex')
    if not binary:
        raise RuntimeError('Codex CLI is unavailable; the published city was preserved.')
    proc = subprocess.Popen([binary, 'app-server', '--stdio'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    inbox = queue.Queue()

    def reader():
        for line in proc.stdout:
            try:
                inbox.put(json.loads(line))
            except ValueError:
                pass
        inbox.put(None)

    threading.Thread(target=reader, daemon=True).start()

    def send(message):
        proc.stdin.write(json.dumps(message) + '\n')
        proc.stdin.flush()

    def request(number, method, params=None):
        message = {'id': number, 'method': method}
        if params is not None:
            message['params'] = params
        send(message)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                reply = inbox.get(timeout=max(0.1, deadline - time.monotonic()))
            except queue.Empty:
                raise TimeoutError('Codex account usage timed out.') from None
            if reply is None:
                raise RuntimeError('Codex closed before returning account usage.')
            if reply.get('id') == number:
                if 'error' in reply:
                    raise RuntimeError('Codex account usage failed; check the local login.')
                return reply['result']
        raise TimeoutError('Codex account usage timed out.')

    try:
        request(1, 'initialize', {'clientInfo': {'name': 'codex_token_city', 'version': '1.0'},
                                 'capabilities': {'experimentalApi': True}})
        send({'method': 'initialized'})
        return request(2, 'account/usage/read')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def sanitize(usage, now=None):
    now = now or dt.datetime.now(UTC)
    buckets = usage.get('dailyUsageBuckets')
    if not isinstance(buckets, list) or not buckets:
        raise ValueError('Daily Codex buckets are unavailable; the published city was preserved.')
    daily = {}
    for bucket in buckets:
        date = dt.date.fromisoformat(bucket['startDate'])
        tokens = bucket.get('tokens')
        if type(tokens) is not int or tokens < 0 or tokens > 10**15:
            raise ValueError('Invalid token count.')
        if date > (now + dt.timedelta(hours=14)).date():
            raise ValueError('A returned bucket is in the future.')
        if date in daily:
            raise ValueError('Duplicate daily bucket; refusing to double count.')
        daily[date] = tokens
    first, last = min(daily), max(daily)
    if (now.date() - last).days > 3:
        raise ValueError('The daily buckets are stale; the published city was preserved.')
    missing = [(first + dt.timedelta(days=i)).isoformat()
               for i in range((last - first).days + 1)
               if first + dt.timedelta(days=i) not in daily]
    account_total = (usage.get('summary') or {}).get('lifetimeTokens')
    if account_total is not None and (type(account_total) is not int or account_total < 0):
        raise ValueError('Invalid account total.')
    # A sum match is only an internal consistency check, not proof of all-device coverage.
    return {
        'schemaVersion': 1,
        'source': 'Codex account/usage/read dailyUsageBuckets',
        'updatedAt': now.replace(microsecond=0).isoformat(),
        'metric': 'service-reported tokens; no input/output/cache breakdown provided',
        'dateBasis': 'service startDate values, without timezone conversion',
        'coverage': {'firstReturnedDate': first.isoformat(), 'through': last.isoformat(),
                     'returnedDays': len(daily), 'missingDates': missing,
                     'allDevicesComplete': 'not established'},
        'recordedTokens': sum(daily.values()),
        'matchesAccountSummary': None if account_total is None else sum(daily.values()) == account_total,
        'dailyUsageBuckets': [{'startDate': date.isoformat(), 'tokens': tokens}
                             for date, tokens in sorted(daily.items())],
    }


def compact(value):
    for scale, suffix in ((10**12, 'T'), (10**9, 'B'), (10**6, 'M'), (10**3, 'K')):
        if value >= scale:
            return f'{value / scale:.2f}'.rstrip('0').rstrip('.') + suffix
    return str(value)


def render(data, mobile=False):
    daily = {dt.date.fromisoformat(b['startDate']): b['tokens'] for b in data['dailyUsageBuckets']}
    end = max(daily)
    start = end - dt.timedelta(days=end.weekday(), weeks=12)
    visible = {date: tokens for date, tokens in daily.items() if start <= date <= end}
    peak = max(visible.values())
    peak_date = max(visible, key=visible.get)
    total = sum(visible.values())
    active = sum(tokens > 0 for tokens in visible.values())
    recent_start = end - dt.timedelta(days=6)
    recent = sum(tokens for date, tokens in visible.items() if date >= recent_start)
    recent_days = sum(recent_start <= date <= end for date in visible)
    first_visible = min(visible)
    gap_count = sum(first_visible <= dt.date.fromisoformat(d) <= end
                    for d in data['coverage']['missingDates'])
    width, height = (480, 580) if mobile else (900, 680)
    pad = 26 if mobile else 38
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           '<title id="title">Ryan — Codex token city</title>',
           f'<desc id="desc">Daily account-reported Codex tokens. {total:,} recorded tokens in the displayed 13-week calendar ending {end}; {len(visible)} returned days, {gap_count} missing dates within returned history. Building height uses a square-root scale. Missing dates are outlined, never assumed to be zero. All-device completeness is not established.</desc>',
           '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#131e29"/><stop offset="1" stop-color="#090e15"/></linearGradient><radialGradient id="halo"><stop stop-color="#74d9d3" stop-opacity=".09"/><stop offset="1" stop-color="#74d9d3" stop-opacity="0"/></radialGradient></defs>',
           '<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.tower{transform-box:fill-box;transform-origin:center bottom;animation:rise .8s cubic-bezier(.2,.7,.2,1) both}@keyframes rise{from{transform:scaleY(.04);opacity:.15}to{transform:scaleY(1);opacity:1}}@media(prefers-reduced-motion:reduce){.tower{animation:none}}</style>',
           f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="22" fill="url(#bg)" stroke="#2a3641"/>']

    def text(x, y, value, size=11, color='#8c9ba8', weight=400, anchor='start', extra=''):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{html.escape(str(value))}</text>')

    def polygon(points, fill, extra=''):
        coords = ' '.join(f'{x:.2f},{y:.2f}' for x, y in points)
        out.append(f'<polygon points="{coords}" fill="{fill}" {extra}/>')

    text(pad, 37, 'CODEX / TOKEN CITY', 12, '#a6e3df', 600, extra='letter-spacing="1.1"')
    text(width-pad, 37, 'RYAN', 10, anchor='end', extra='letter-spacing="1.5"')
    text(pad, 60, f'{first_visible:%b %d} — {end:%b %d, %Y}', 11)
    if not mobile:
        text(width-pad, 60, '13-WEEK CALENDAR', 10, anchor='end')
    stats = [('RECORDED TOKENS', compact(total)),
             ('LAST 7 DAYS' if recent_days == 7 else f'7 DAYS / {recent_days} RECORDED', compact(recent)),
             ('ACTIVE DAYS', str(active)), ('PEAK DAY', compact(peak))]
    for i, (label, value) in enumerate(stats):
        x = pad + (i % 2) * 222 if mobile else pad + i * 211
        y = 91 + (i // 2) * 63 if mobile else 100
        text(x, y, label, 9, extra='letter-spacing=".8"')
        text(x, y+33, value, 29 if mobile else 33, '#a6e3df' if i == 0 else '#e9f1f6', 600)
    divider = 207 if mobile else 165
    out.append(f'<path d="M{pad} {divider}H{width-pad}" stroke="#2a3641"/>')
    text(pad, divider+24, 'ONE BUILDING / ONE DAY', 9 if mobile else 10, '#b2c3ce', extra='letter-spacing=".8"')
    if not mobile:
        text(width-pad, divider+24, f'PEAK {peak_date:%b %d} · {compact(peak)}', 10, anchor='end')

    # Draw back-to-front so each daily column occludes the correct neighbors.
    out.append('<g transform="translate(-28 107) scale(.60)">' if mobile else '<g>')
    out.append('<ellipse cx="450" cy="456" rx="340" ry="180" fill="url(#halo)"/>')
    ox, oy, dx, dy = 348, 317, 31, 14

    def point(week, weekday):
        return ox+(week-weekday)*dx, oy+(week+weekday)*dy

    polygon([point(-.75, -.75), point(12.75, -.75), point(12.75, 6.75), point(-.75, 6.75)],
            '#101c27', 'stroke="#2a414e" stroke-width="1"')
    for week, weekday in sorted(((w, d) for w in range(13) for d in range(7)), key=lambda p:(sum(p), p[0])):
        date = start + dt.timedelta(days=week*7+weekday)
        count = visible.get(date)
        cx, cy = point(week, weekday)
        a, b = 26.5, 11.9
        footprint = [(cx-a, cy), (cx, cy-b), (cx+a, cy), (cx, cy+b)]
        if count is None:
            label = 'not yet returned' if date > end else 'no returned record'
            out.append(f'<g data-date="{date}" data-state="missing"><title>{date}: {label}</title>')
            polygon(footprint, '#101a24', 'stroke="#30414d" stroke-width=".8" stroke-dasharray="2 3"')
            out.append('</g>')
            continue
        if count == 0:
            out.append(f'<g data-date="{date}" data-state="zero"><title>{date}: 0 recorded tokens</title>')
            polygon(footprint, '#233b47', 'stroke="#345260" stroke-width=".7"')
            out.append('</g>')
            continue
        ratio = math.sqrt(count/peak)
        h = 4 + ratio*124
        palette = [('#294754','#416978','#648f9b'), ('#355f69','#568791','#82b2ba'),
                   ('#487b80','#6fa7aa','#a7d6d7'), ('#5c9495','#8fc9c7','#d2fff1')]
        left, right, roof = palette[min(3, int(ratio*4))]
        out.append(f'<g class="tower" data-date="{date}" data-state="recorded" style="animation-delay:{week*.03+weekday*.014:.3f}s"><title>{date}: {count:,} recorded tokens</title>')
        polygon([(cx-a,cy-h),(cx,cy+b-h),(cx,cy+b),(cx-a,cy)], left,
                'stroke="#8dd1cc" stroke-opacity=".12" stroke-width=".6"')
        polygon([(cx,cy+b-h),(cx+a,cy-h),(cx+a,cy),(cx,cy+b)], right,
                'stroke="#d2fff1" stroke-opacity=".13" stroke-width=".6"')
        for level in range(18, int(h)-8, 18):
            out.append(f'<path d="M{cx+4:.2f} {cy+b-h+level:.2f}L{cx+a-4:.2f} {cy-h+level+2:.2f}" stroke="#ddfff7" stroke-width="1.6" opacity=".18"/>')
        polygon([(cx-a,cy-h),(cx,cy-b-h),(cx+a,cy-h),(cx,cy+b-h)], roof,
                'stroke="#e0fff9" stroke-opacity=".24" stroke-width=".8"')
        out.append('</g>')
    for week in range(0, 13, 3):
        cx, cy = point(week, 6)
        label = start + dt.timedelta(weeks=week)
        text(cx-5, cy+35, label.strftime('%b %d'), 10, anchor='middle')
    out.append('</g>')
    legend_y = 505 if mobile else 628
    text(pad, legend_y, 'LOW', 9)
    for i, fill in enumerate(('#648f9b','#82b2ba','#a7d6d7','#d2fff1')):
        out.append(f'<rect x="{pad+32+i*16}" y="{legend_y-9}" width="11" height="11" rx="2" fill="{fill}"/>')
    text(pad+102, legend_y, 'HIGH', 9)
    out.append(f'<rect x="{pad+157}" y="{legend_y-9}" width="11" height="11" rx="2" fill="none" stroke="#687e8c" stroke-dasharray="2 2"/>')
    text(pad+176, legend_y, 'NO RECORD', 9)
    text(width-pad, legend_y, 'SQRT HEIGHT', 9, anchor='end')
    text(pad, legend_y+24, f'{len(visible)} recorded days · {gap_count} '+('gap' if gap_count == 1 else 'gaps')+' in returned history', 9)
    text(pad, legend_y+42, 'Account-reported tokens · dates as returned' if mobile else
         'Account-reported tokens · dates as returned · missing records are not zero', 8 if mobile else 9)
    svg = '\n'.join(out) + '\n</svg>\n'
    root = ET.fromstring(svg)
    assert root.tag == '{http://www.w3.org/2000/svg}svg'
    assert 'NaN' not in svg and 'Infinity' not in svg
    return svg


def gh_api(endpoint, payload=None, method=None):
    command = ['gh', 'api', endpoint]
    if method:
        command += ['--method', method]
    if payload is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError('GitHub request failed; inspect the remote state before retrying.')
    return json.loads(result.stdout) if result.stdout else {}


def publish(directory):
    if gh_api('user')['login'].lower() != REPO.split('/')[0].lower():
        raise RuntimeError('The active GitHub user does not match the configured profile.')
    prefix = f'repos/{REPO}'
    branch = gh_api(prefix)['default_branch']
    parent = gh_api(f'{prefix}/git/ref/heads/{branch}')['object']['sha']
    commit = gh_api(f'{prefix}/git/commits/{parent}')
    files = {f'.github/profile/{name}': (directory/name).read_text() for name in FILES}
    tree = gh_api(f'{prefix}/git/trees', {'base_tree':commit['tree']['sha'], 'tree':[
        {'path': path, 'mode':'100644', 'type':'blob', 'content':content} for path, content in files.items()]})
    if tree['sha'] == commit['tree']['sha']:
        return 'unchanged'
    new_commit = gh_api(f'{prefix}/git/commits', {'message':'Refresh Codex token city [skip deploy]',
        'tree':tree['sha'], 'parents':[parent]})
    gh_api(f'{prefix}/git/refs/heads/{branch}', {'sha':new_commit['sha'], 'force':False}, 'PATCH')
    for path, content in files.items():
        remote = gh_api(f'{prefix}/contents/{path}', method='GET')
        if base64.b64decode(remote['content']).decode() != content:
            raise RuntimeError('Published image read-back differs; do not blindly retry.')
    return new_commit['sha']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=pathlib.Path, default=pathlib.Path(__file__).parent)
    parser.add_argument('--input-json', type=pathlib.Path, help='Render a previously captured account response offline')
    parser.add_argument('--publish', action='store_true', help='Publish only the three allowlisted city assets')
    args = parser.parse_args()
    usage = json.loads(args.input_json.read_text()) if args.input_json else read_usage()
    data = sanitize(usage)
    assets = {'codex-city.json':json.dumps(data, indent=2)+'\n',
              'codex-city.svg':render(data), 'codex-city-mobile.svg':render(data, mobile=True)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in assets.items():
        (args.output_dir/name).write_text(content)
    print(f'Generated Codex city: {data["coverage"]["returnedDays"]} returned days through {data["coverage"]["through"]}.')
    if args.publish:
        print('Published:', publish(args.output_dir))


if __name__ == '__main__':
    main()
