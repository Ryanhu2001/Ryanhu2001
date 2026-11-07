#!/usr/bin/env python3
"""Render the Codex NightView from Token Monitor's automatic JSON export."""
import argparse
import base64
import datetime as dt
import html
import json
import math
import pathlib
import subprocess
import xml.etree.ElementTree as ET

REPO = 'Ryanhu2001/Ryanhu2001'
FILES = ('codex-city.json', 'codex-city.svg', 'codex-city-mobile.svg')
UTC = dt.timezone.utc
SHANGHAI = dt.timezone(dt.timedelta(hours=8))
SETTINGS = pathlib.Path.home() / 'Library/Application Support/Token Monitor/settings.json'


def read_usage(export_path=None):
    if export_path is None:
        settings = json.loads(SETTINGS.read_text())
        directory = settings.get('exportDir')
        if settings.get('exportAutoEnabled') is not True or not isinstance(directory, str) or not directory:
            raise ValueError('Enable Token Monitor automatic export before updating the city.')
        export_path = pathlib.Path(directory).expanduser() / 'token-monitor-export.json'
    return json.loads(pathlib.Path(export_path).read_text())


def sanitize(usage, now=None):
    now = now or dt.datetime.now(UTC)
    if not isinstance(usage, dict) or usage.get('app', {}).get('name') != 'token-monitor':
        raise ValueError('Expected a Token Monitor JSON export; no other source is accepted.')
    generated = dt.datetime.fromisoformat(str(usage.get('generatedAt', '')).replace('Z', '+00:00'))
    if generated.tzinfo is None:
        raise ValueError('Token Monitor export timestamp must include a timezone.')
    if generated > now + dt.timedelta(minutes=5):
        raise ValueError('Token Monitor export timestamp is in the future.')
    if now - generated > dt.timedelta(hours=48):
        raise ValueError('Token Monitor export is older than 48 hours; the published city was preserved.')
    today = now.astimezone(SHANGHAI).date()
    buckets = usage.get('daily')
    if not isinstance(buckets, list) or not buckets:
        raise ValueError('Token Monitor daily history is unavailable; the published city was preserved.')
    daily = {}
    seen = set()
    for bucket in buckets:
        date = dt.date.fromisoformat(bucket['date'])
        if date.isoformat() != bucket['date'] or date > today:
            raise ValueError('Invalid or future Token Monitor date.')
        if date in seen:
            raise ValueError('Duplicate daily date; refusing to double count.')
        seen.add(date)
        clients = bucket.get('perClient')
        if not isinstance(clients, dict):
            raise ValueError('Token Monitor daily perClient breakdown is unavailable.')
        codex = clients.get('codex')
        # An absent Codex entry is unknown, not a measured zero.
        if codex is None:
            continue
        if not isinstance(codex, dict):
            raise ValueError('Invalid Codex daily record.')
        tokens = codex.get('tokens')
        if type(tokens) is not int or tokens < 0 or tokens > 10**15:
            raise ValueError('Invalid token count.')
        # These are already included in `tokens`; never add them again.
        known_components = [codex.get(key, 0) for key in
                            ('cacheReadTokens', 'cacheWriteTokens', 'outputTokens', 'unclassifiedTokens')]
        if any(type(value) is not int or value < 0 for value in known_components) or sum(known_components) > tokens:
            raise ValueError('Codex token components do not fit the exported total.')
        # Daily publishing uses completed dates, so today's changing total is excluded.
        if date == today:
            continue
        daily[date] = tokens
    if not daily:
        raise ValueError('No completed Codex daily records in the Token Monitor export.')
    first, last = min(daily), max(daily)
    if (today - last).days > 3:
        raise ValueError('Token Monitor Codex daily history is stale; the published city was preserved.')
    missing = [(first + dt.timedelta(days=i)).isoformat()
               for i in range((last - first).days + 1)
               if first + dt.timedelta(days=i) not in daily]
    return {
        'schemaVersion': 2,
        'source': 'Token Monitor automatic export: daily.perClient.codex.tokens',
        'sourceUpdatedAt': generated.astimezone(UTC).replace(microsecond=0).isoformat(),
        'updatedAt': now.replace(microsecond=0).isoformat(),
        'metric': 'Codex exported total; cache and reasoning are already included, never added again',
        'dateBasis': 'Token Monitor exported dates without conversion; current Asia/Shanghai date excluded',
        'coverage': {'firstReturnedDate': first.isoformat(), 'through': last.isoformat(),
                     'returnedDays': len(daily), 'missingDates': missing,
                     'allDevicesComplete': 'not established'},
        'recordedTokens': sum(daily.values()),
        'dailyUsageBuckets': [{'startDate': date.isoformat(), 'tokens': tokens}
                             for date, tokens in sorted(daily.items())],
    }


def compact(value):
    for scale, suffix in ((10**12, 'T'), (10**9, 'B'), (10**6, 'M'), (10**3, 'K')):
        if value >= scale:
            return f'{value / scale:.2f}'.rstrip('0').rstrip('.') + suffix
    return str(value)


def render(data, mobile=False):
    """Adapt the upstream NightView calendar projection to recorded Codex tokens.

    Geometry, logarithmic columns and face shading follow
    yoshi389111/github-profile-3d-contrib v0.9.3 (MIT); see codex-city-NOTICE.md.
    GitHub-specific language/repository charts are replaced with token metrics.
    """
    daily = {dt.date.fromisoformat(b['startDate']): b['tokens'] for b in data['dailyUsageBuckets']}
    first, end = min(daily), max(daily)
    weeks = 13 if mobile else 53
    start = end - dt.timedelta(days=(end.weekday()+1) % 7, weeks=weeks-1)
    visible = {date: count for date, count in daily.items() if start <= date <= end}
    total = sum(daily.values())
    active = sum(value > 0 for value in daily.values())
    peak = max(daily.values())
    recent_dates = [end-dt.timedelta(days=6-i) for i in range(7)]
    recent_values = [daily.get(date) for date in recent_dates]
    recent = sum(value or 0 for value in recent_values)
    recent_days = sum(value is not None for value in recent_values)
    width, height = (480, 610) if mobile else (1280, 890)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           '<title id="title">Ryan — Codex NightView, mint edition</title>',
           f'<desc id="desc">{total:,} Codex tokens from Token Monitor across {len(daily)} completed dates, {first} to {end}. Cache and reasoning are included once in the exported total. A {weeks}-week isometric calendar adapted from GitHub Profile 3D Contrib NightView. Heights are logarithmic. Missing dates are unknown, not zero. All-device coverage is not established.</desc>',
           '<style>text{font-family:Ubuntu,Helvetica,Arial,sans-serif}.tower{transform-box:fill-box;transform-origin:center bottom;animation:grow 2.2s ease-out both}@keyframes grow{from{transform:scaleY(.025)}to{transform:scaleY(1)}}@media(prefers-reduced-motion:reduce){.tower{animation:none}}</style>',
           f'<rect width="{width}" height="{height}" fill="#00000f"/>']
    mint, fg, weak = '#a6e3df', '#eeeeff', '#9199aa'

    def text(x, y, value, size=16, color=weak, weight=400, anchor='start', extra=''):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{html.escape(str(value))}</text>')

    def polygon(points, fill, extra=''):
        coords = ' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
        out.append(f'<polygon points="{coords}" fill="{fill}" {extra}/>')

    def darken(color, amount):
        rgb = [int(color[i:i+2],16) for i in (1,3,5)]
        return '#' + ''.join(f'{round(v * .7**amount):02x}' for v in rgb)

    if mobile:
        text(22,32,'CODEX · NIGHT VIEW',15,mint,600,extra='letter-spacing="1"')
        text(22,55,f'{first:%b %d} — {end:%b %d, %Y}',12)
        text(22,101,compact(total),33,mint,600)
        text(22,122,'recorded tokens',12,fg)
        text(270,101,compact(recent),33,fg,600)
        text(270,122,'last 7 days' if recent_days == 7 else f'7 days / {recent_days} returned',12)
        text(22,159,f'{active} active days · peak {compact(peak)} tokens',12)
        text(22,181,'LATEST 13 WEEKS',10,weak,extra='letter-spacing="1"')
        out.append('<g transform="translate(0 107)">')
        dx = width/24
        plot_height = 400
        height_factor = .55
    else:
        text(35,43,'CODEX · NIGHT VIEW',23,mint,600,extra='letter-spacing="1.5"')
        text(width-25,29,f'{first:%Y-%m-%d} / {end:%Y-%m-%d}',16,anchor='end')
        text(35,73,f'Token Monitor · {len(daily)} completed dates · {len(data["coverage"]["missingDates"])} missing',15)
        out.append('<g>')
        dx = width/64
        plot_height = 850
        height_factor = 1
    # Match the upstream 30-degree, Sunday-first, long diagonal calendar.
    dy = dx*math.tan(math.pi/6)
    dxx, dyy = dx*.9, dy*.9
    offset_x, offset_y = dx*7, plot_height-(weeks+7)*dy
    palette = ['#112333','#235369','#367b8c','#64afb6','#a6e3df']
    for offset in range(weeks*7):
        date = start+dt.timedelta(days=offset)
        week, weekday = divmod(offset,7)
        x = offset_x+(week-weekday)*dx
        y = offset_y+(week+weekday)*dy
        count = visible.get(date)
        points = [(x,y),(x+dxx,y-dyy),(x+2*dxx,y),(x+dxx,y+dyy)]
        if count is None:
            label = 'not yet returned' if date > end else 'no returned record'
            out.append(f'<g data-date="{date}" data-state="missing"><title>{date}: {label}</title>')
            polygon(points,'#081322','stroke="#1e3349" stroke-width=".55" stroke-dasharray="1.7 2"')
            out.append('</g>')
            continue
        level = 0 if count == 0 else min(4, 1+int(math.sqrt(count/max(1,peak))*3.999))
        raw_peak = math.log10(peak/1_000_000/20+1)*144+3
        # A shared fit factor preserves the logarithmic ordering at larger future peaks.
        h = (math.log10(count/1_000_000/20+1)*144+3)*height_factor*min(1,310/raw_peak)
        roof = palette[level]
        state = 'zero' if count == 0 else 'recorded'
        out.append(f'<g class="{"tower" if count else "base"}" data-date="{date}" data-state="{state}"><title>{date}: {count:,} recorded tokens</title>')
        polygon([(x,y-h),(x+dxx,y+dyy-h),(x+dxx,y+dyy),(x,y)],darken(roof,.5))
        polygon([(x+dxx,y+dyy-h),(x+2*dxx,y-h),(x+2*dxx,y),(x+dxx,y+dyy)],darken(roof,1))
        polygon([(x,y-h),(x+dxx,y-dyy-h),(x+2*dxx,y-h),(x+dxx,y+dyy-h)],roof)
        out.append('</g>')
    out.append('</g>')

    if not mobile:
        # NightView's upper-right radar position, now showing actual daily tokens.
        cx, cy, radius = 974, 272, 153
        text(cx,66,'DAILY TOKENS · LAST 7 DAYS',15,mint,600,'middle',extra='letter-spacing="1"')
        maximum = max((v or 0) for v in recent_values)
        tick = max(1, math.ceil(maximum/4/1_000_000))*1_000_000
        scale = tick*4

        def radial(i, amount):
            angle = -math.pi/2+i*2*math.pi/7
            return cx+math.cos(angle)*radius*amount, cy+math.sin(angle)*radius*amount

        for step in range(1,5):
            polygon([radial(i,step/4) for i in range(7)],'none',
                    'stroke="#777d8a" stroke-width=".7" stroke-dasharray="4 5"')
            text(cx+7,cy-radius*step/4+4,compact(tick*step),11)
        for i,date in enumerate(recent_dates):
            px,py = radial(i,1)
            out.append(f'<path d="M{cx} {cy}L{px:.2f} {py:.2f}" stroke="#5b6476" stroke-width=".7" stroke-dasharray="4 5"/>')
            lx,ly = radial(i,1.18)
            text(lx,ly+5,date.strftime('%b %d'),15,fg,anchor='middle')
        if recent_days == 7:
            polygon([radial(i,(value or 0)/scale) for i,value in enumerate(recent_values)],mint,
                    f'fill-opacity=".38" stroke="{mint}" stroke-width="3"')
        else:
            for i,value in enumerate(recent_values):
                if value is not None:
                    px,py = radial(i,value/scale)
                    out.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="{mint}"/>')

        # NightView's lower-left donut: a real partition of the returned history.
        cx, cy, radius = 190, 658, 101
        share = recent/total if total else 0
        circumference = 2*math.pi*radius
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#173345" stroke-width="29"/>')
        if share:
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{mint}" stroke-width="29" stroke-dasharray="{share*circumference:.3f} {circumference:.3f}" transform="rotate(-90 {cx} {cy})"/>')
        text(cx,cy-4,compact(recent),29,mint,600,'middle')
        text(cx,cy+24,'last 7 days' if recent_days == 7 else f'{recent_days}/7 dates returned',14,fg,anchor='middle')
        text(335,640,f'{share*100:.1f}% recent',18,mint)
        text(335,671,f'{(1-share)*100:.1f}% earlier',18,'#6e98a8')
        text(335,703,'of recorded tokens',14)
        text(380,833,compact(total),32,mint,600,'end')
        text(391,833,'tokens',24,fg)
        text(602,833,str(active),29,mint,600,'end')
        text(614,833,'active days',21,fg)
        text(810,833,'peak '+compact(peak),19,fg)
        text(24,866,'NightView · mint  /  token heights: logarithmic  /  outlined tiles: no returned record',13)
    else:
        text(22,552,'LOG HEIGHT · MINT NIGHT VIEW',10,weak,extra='letter-spacing=".6"')
        text(22,575,'Outlined tiles: no returned record',11)
        text(22,594,'Token Monitor · Codex · completed dates',10)
    svg = '\n'.join(out)+'\n</svg>\n'
    ET.fromstring(svg)
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
    parser.add_argument('--monitor-export', '--input-json', dest='monitor_export', type=pathlib.Path,
                        help='Token Monitor JSON export (default: read its configured automatic export directory)')
    parser.add_argument('--publish', action='store_true', help='Publish only the three allowlisted city assets')
    args = parser.parse_args()
    usage = read_usage(args.monitor_export)
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
