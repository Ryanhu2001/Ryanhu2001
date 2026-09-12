#!/usr/bin/env python3
"""Publish an allowlisted Codex account summary. Python standard library only."""
import argparse
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
UTC = dt.timezone.utc
TZ = dt.timezone(dt.timedelta(hours=8))
PUBLIC_FILES = ('stats.json', 'codex.svg', 'codex-mobile.svg')


def read_account():
    binary = shutil.which('codex')
    if not binary:
        raise RuntimeError('Codex CLI is unavailable; existing public data was not changed.')
    proc = subprocess.Popen([binary, 'app-server', '--stdio'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    messages = queue.Queue()

    def reader():
        for line in proc.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                pass
        messages.put(None)

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
            reply = messages.get(timeout=max(0.1, deadline - time.monotonic()))
            if reply is None:
                raise RuntimeError('Codex app-server closed before returning usage.')
            if reply.get('id') == number:
                if 'error' in reply:
                    # Do not print upstream payloads, which may contain account information.
                    raise RuntimeError(f'{method} failed; check the local Codex login.')
                return reply['result']
        raise TimeoutError('Codex usage request timed out.')

    try:
        request(1, 'initialize', {'clientInfo': {'name': 'codex_profile_stats', 'version': '1.0'},
                                 'capabilities': {'experimentalApi': True}})
        send({'method': 'initialized'})
        usage = request(2, 'account/usage/read')
        limits = request(3, 'account/rateLimits/read')
        buckets = limits.get('rateLimitsByLimitId') or {}
        quota = buckets.get('codex') or limits.get('rateLimits') or {}
        return usage, quota
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def sanitize(usage, quota, now=None):
    now = now or dt.datetime.now(UTC)
    source = usage.get('summary') or {}
    summary = {}
    for key in ('lifetimeTokens', 'peakDailyTokens', 'currentStreakDays', 'longestStreakDays'):
        value = source.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('Invalid account summary; refusing to publish.')
        summary[key] = value
    if summary['lifetimeTokens'] is None:
        raise ValueError('Account usage is unavailable; keeping the existing public card.')
    daily = {}
    for item in usage.get('dailyUsageBuckets') or []:
        date = dt.date.fromisoformat(item['startDate'])
        tokens = item.get('tokens')
        if date > now.astimezone(TZ).date() or type(tokens) is not int or tokens < 0:
            raise ValueError('Invalid daily usage bucket.')
        if date.isoformat() in daily:
            raise ValueError('Duplicate daily usage bucket.')
        daily[date.isoformat()] = tokens
    if not daily:
        raise ValueError('Daily usage is unavailable; keeping the existing public card.')
    windows = []
    for key in ('primary', 'secondary'):
        window = quota.get(key)
        if not window:
            continue
        used, mins, reset = (window.get(k) for k in ('usedPercent', 'windowDurationMins', 'resetsAt'))
        if valid_number(used) and valid_number(mins) and mins > 0 and valid_number(reset):
            if reset > now.timestamp():
                windows.append({'usedPercent': used, 'windowDurationMins': mins, 'resetsAt': reset})
    # Prefer the weekly quota, but never assume a five-hour window exists.
    selected = next((w for w in windows if w['windowDurationMins'] == 10080), None)
    selected = selected or (windows[0] if windows else None)
    return {'schemaVersion': 1, 'source': 'Codex account usage',
            'updatedAt': now.replace(microsecond=0).isoformat(), 'summary': summary,
            'dailyUsageBuckets': [{'startDate': d, 'tokens': daily[d]} for d in sorted(daily)],
            'quota': selected}


def compact(value):
    if value is None:
        return '—'
    for size, suffix in ((1e12, 'T'), (1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
        if value >= size:
            return f'{value / size:.2f}'.rstrip('0').rstrip('.') + suffix
    return str(value)


def recent_total(data):
    end = dt.date.fromisoformat(data['dailyUsageBuckets'][-1]['startDate'])
    start = end - dt.timedelta(days=6)
    total = sum(x['tokens'] for x in data['dailyUsageBuckets']
                if start <= dt.date.fromisoformat(x['startDate']) <= end)
    return total, start, end


def render(data, mobile=False):
    width, height = (480, 650) if mobile else (900, 602)
    pad = 26 if mobile else 40
    right = width - pad
    accent, muted, white = '#80d9ee', '#8b98a7', '#edf4fa'
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
                '<title id="title">Ryan · Building with Codex</title>']
    total, start, end = recent_total(data)
    summary = data['summary']
    elements += [f'<desc id="desc">{summary["lifetimeTokens"]:,} lifetime tokens; {summary["currentStreakDays"]} consecutive days; {total:,} tokens from {start} through {end}. Account usage snapshot, not live.</desc>',
                 '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#101a26"/><stop offset="1" stop-color="#090e16"/></linearGradient>',
                 '<linearGradient id="bar"><stop stop-color="#4299bc"/><stop offset="1" stop-color="#9af1ef"/></linearGradient></defs>',
                 f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="20" fill="url(#bg)" stroke="#283544"/>']

    def text(x, y, content, size=12, color=muted, weight=400, anchor='start', spacing=None, mono=False):
        family = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' if mono else '-apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif'
        space = f' letter-spacing="{spacing}"' if spacing is not None else ''
        elements.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" font-family="{family}"{space}>{html.escape(str(content))}</text>')

    def line(y):
        elements.append(f'<path d="M{pad} {y}H{right}" stroke="#25313f"/>')

    text(pad, 39, 'RYAN / BUILD LOG', 11, accent, 500, spacing=2, mono=True)
    text(right, 39, 'CODEX', 11, muted, 500, 'end', spacing=2, mono=True)
    text(pad, 96 if mobile else 103, 'Building with Codex.', 33 if mobile else 43, white, 600, spacing=-1.4)
    text(pad, 123 if mobile else 133, 'Small steps. Long sessions.', 13 if mobile else 15)
    if not mobile:
        elements.append('<g transform="translate(793 103)" fill="none" stroke="#80d9ee"><circle r="35" opacity=".12"/><ellipse rx="41" ry="16" transform="rotate(-35)" opacity=".4"/><circle cx="30" cy="-22" r="3" fill="#80d9ee" stroke="none"/></g>')
        text(793, 111, '>_', 24, accent, 500, 'middle', mono=True)
    stat_label, stat_value, stat_sub = (177, 219, 242) if mobile else (188, 236, 261)
    step = (width - pad * 2) / 3
    stats = [('TOTAL TOKENS', compact(summary['lifetimeTokens']), 'all time'),
             ('DAY STREAK', str(summary['currentStreakDays']) if summary['currentStreakDays'] is not None else '—', 'consecutive days'),
             ('7-DAY TOKENS', compact(total), f'through {end:%b %d}')]
    for i, (label, value, caption) in enumerate(stats):
        x = pad + step * i
        text(x, stat_label, label, 9 if mobile else 10, muted, spacing=1, mono=True)
        text(x, stat_value, value, 31 if mobile else 40, accent if i == 1 else white, 550, spacing=-1, mono=True)
        text(x, stat_sub, caption, 10 if mobile else 12)
    line(271 if mobile else 288)
    text(pad, 304 if mobile else 320, 'TOKEN ACTIVITY', 11, white, 500, spacing=1.5, mono=True)
    weeks = 13 if mobile else 26
    text(right, 304 if mobile else 320, f'{weeks} WEEKS', 10, muted, anchor='end', mono=True)
    # Align columns to Sunday. Dates beyond the latest returned bucket are unknown.
    sunday = end - dt.timedelta(days=(end.weekday() + 1) % 7)
    first = sunday - dt.timedelta(weeks=weeks-1)
    daily = {dt.date.fromisoformat(d['startDate']): d['tokens'] for d in data['dailyUsageBuckets']}
    earliest = min(daily)
    maxval = max(daily.values()) or 1
    x0 = pad + 30
    pitch = (width - pad * 2 - 30) / weeks
    cell = min(19 if mobile else 21, pitch - 6)
    y0 = 347 if mobile else 361
    ypitch = 22 if mobile else 17
    cell_h = 16 if mobile else 12
    for row, label in ((1, 'M'), (3, 'W'), (5, 'F')):
        text(pad, y0 + row * ypitch + cell_h - 2, label, 9, mono=True)
    previous_month = None
    for week in range(weeks):
        week_date = first + dt.timedelta(weeks=week)
        x = x0 + week * pitch
        if week_date.month != previous_month:
            text(x, y0 - 13, week_date.strftime('%b'), 10)
        previous_month = week_date.month
        for row in range(7):
            date = week_date + dt.timedelta(days=row)
            count = daily.get(date)
            color = '#14202d'
            label = f'{date}: no recorded usage'
            if date < earliest or date > end:
                color, label = '#101822', f'{date}: data unavailable'
            elif count:
                ratio = count / maxval
                level = 0 if ratio < .04 else 1 if ratio < .15 else 2 if ratio < .4 else 3
                color = ['#22546b', '#3687a2', '#60b9ce', '#a0e6ef'][level]
                label = f'{date}: {count:,} tokens'
            elements.append(f'<rect x="{x:.2f}" y="{y0 + row*ypitch}" width="{cell:.2f}" height="{cell_h}" rx="3" fill="{color}"><title>{label}</title></rect>')
    legend_y = 512 if mobile else 497
    text(pad, legend_y, f'DAILY DATA THROUGH {end:%b %d, %Y}'.upper(), 9, muted, mono=True)
    text(right, legend_y, 'LOW → HIGH', 9, accent, anchor='end', mono=True)
    quota_y = 548 if mobile else 532
    quota = data.get('quota')
    if quota:
        minutes = quota['windowDurationMins']
        label = 'WEEKLY ALLOWANCE' if minutes == 10080 else f'{minutes/60:g}H ALLOWANCE'
        used = quota['usedPercent']
        text(pad, quota_y, label, 10, muted, mono=True)
        text(right, quota_y, f'{used:g}% USED', 10, accent, anchor='end', mono=True)
        bar_y = quota_y + 12
        elements.append(f'<rect x="{pad}" y="{bar_y}" width="{right-pad}" height="5" rx="2.5" fill="#24313e"/>')
        filled = (right-pad) * min(100, used) / 100
        if filled:
            elements.append(f'<rect x="{pad}" y="{bar_y}" width="{filled:.2f}" height="5" rx="2.5" fill="url(#bar)"/>')
        reset = dt.datetime.fromtimestamp(quota['resetsAt'], TZ)
        text(pad, quota_y + 37, f'Resets {reset:%b %d, %H:%M} UTC+8', 9)
    else:
        text(pad, quota_y, 'ALLOWANCE DATA UNAVAILABLE', 10, muted, mono=True)
    timestamp = dt.datetime.fromisoformat(data['updatedAt']).astimezone(TZ)
    text(right, height - 22, f'UPDATED {timestamp:%m.%d %H:%M} UTC+8', 9, muted, anchor='end', mono=True)
    elements.append('</svg>')
    svg = '\n'.join(elements) + '\n'
    ET.fromstring(svg)
    return svg


def gh_api(endpoint, payload=None, method=None):
    command = ['gh', 'api', endpoint]
    if method:
        command += ['--method', method]
    if payload is not None:
        command += ['--input', '-']
    proc = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                          text=True, capture_output=True, timeout=45)
    if proc.returncode:
        raise RuntimeError(f'GitHub API request failed ({endpoint}); no credentials were logged.')
    return json.loads(proc.stdout) if proc.stdout else {}


def publish(directory):
    if gh_api('user')['login'].lower() != REPO.split('/')[0].lower():
        raise RuntimeError('The active GitHub account does not match the configured profile.')
    prefix = f'repos/{REPO}'
    branch = gh_api(prefix)['default_branch']
    files = {f'.github/profile/{name}': (directory/name).read_text() for name in PUBLIC_FILES}
    ref = gh_api(f'{prefix}/git/ref/heads/{branch}')
    parent = ref['object']['sha']
    commit = gh_api(f'{prefix}/git/commits/{parent}')
    tree = gh_api(f'{prefix}/git/trees', {'base_tree': commit['tree']['sha'],
                  'tree': [{'path': path, 'mode': '100644', 'type': 'blob', 'content': content}
                           for path, content in files.items()]})
    if tree['sha'] == commit['tree']['sha']:
        return 'unchanged'
    new_commit = gh_api(f'{prefix}/git/commits', {'message': 'Refresh Codex usage card [skip deploy]',
                        'tree': tree['sha'], 'parents': [parent]})
    # Non-forced update rejects concurrent changes; never overwrite newer commits.
    gh_api(f'{prefix}/git/refs/heads/{branch}', {'sha': new_commit['sha'], 'force': False}, 'PATCH')
    verified = gh_api(f'{prefix}/contents/.github/profile/stats.json', method='GET')
    import base64
    if base64.b64decode(verified['content']).decode() != files['.github/profile/stats.json']:
        raise RuntimeError('Published content verification failed; inspect the latest commit before retrying.')
    return new_commit['sha']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=pathlib.Path, default=pathlib.Path(__file__).parent)
    parser.add_argument('--publish', action='store_true', help='Update only the three allowlisted public stats files')
    args = parser.parse_args()
    usage, quota = read_account()
    data = sanitize(usage, quota)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'stats.json').write_text(json.dumps(data, indent=2) + '\n')
    (args.output_dir/'codex.svg').write_text(render(data))
    (args.output_dir/'codex-mobile.svg').write_text(render(data, mobile=True))
    print(f'Generated Codex card; daily data through {data["dailyUsageBuckets"][-1]["startDate"]}.')
    if args.publish:
        print(f'Published: {publish(args.output_dir)}')


if __name__ == '__main__':
    main()
