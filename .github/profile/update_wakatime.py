#!/usr/bin/env python3
"""Publish only aggregate WakaTime activity; secrets stay in local config."""
import argparse, base64, configparser, datetime as dt, html, json, math, pathlib, subprocess
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
REPO = 'Ryanhu2001/Ryanhu2001'
TZ = dt.timezone(dt.timedelta(hours=8))
PUBLIC_FILES = ('wakatime.json', 'wakatime.svg', 'wakatime-mobile.svg')

def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Missing or invalid WakaTime duration; keeping existing card.')
    return round(value, 3)

def sanitize(raw, start, end):
    daily, languages = {}, {}
    for day in raw.get('data', []):
        date = dt.date.fromisoformat(day['range']['date'])
        if not start <= date <= end or str(date) in daily:
            raise ValueError('Unexpected or duplicate WakaTime date.')
        daily[str(date)] = number(day['grand_total'].get('total_seconds'))
        for item in day.get('languages', []):
            name = item.get('name')
            if not isinstance(name, str) or len(name) > 60 or any(ord(c) < 32 for c in name):
                raise ValueError('Invalid language name.')
            languages[name] = languages.get(name, 0) + number(item.get('total_seconds'))
    expected = {(start + dt.timedelta(days=i)).isoformat() for i in range(7)}
    if set(daily) != expected:
        raise ValueError('Incomplete WakaTime week; keeping existing card.')
    total = round(sum(daily.values()), 3)
    language_total = sum(languages.values())
    return {'schemaVersion': 1, 'source': 'WakaTime', 'timezone': 'Asia/Shanghai',
            'updatedAt': dt.datetime.now(TZ).replace(microsecond=0).isoformat(),
            'start': str(start), 'end': str(end), 'totalSeconds': total,
            'dailyAverageSeconds': round(total/7, 3),
            'activeDays': sum(v > 0 for v in daily.values()),
            'daily': [{'date': k, 'seconds': v} for k, v in sorted(daily.items())],
            'languages': [{'name': k, 'seconds': round(v, 3), 'percent': round(v/language_total*100, 2)}
                          for k, v in sorted(languages.items(), key=lambda x: -x[1]) if v > 0]}

def fetch():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(pathlib.Path.home()/'.wakatime.cfg')
    key = cfg.get('settings', 'api_key').strip()
    if not key: raise RuntimeError('WakaTime key is missing.')
    end = dt.datetime.now(TZ).date() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=6)
    query = urllib.parse.urlencode({'start': str(start), 'end': str(end), 'timezone': 'Asia/Shanghai'})
    req = urllib.request.Request('https://api.wakatime.com/api/v1/users/current/summaries?'+query,
        headers={'Authorization': 'Basic '+base64.b64encode(key.encode()).decode(), 'User-Agent': 'RyanProfile/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        if response.status != 200: raise RuntimeError('WakaTime data is still processing.')
        raw = json.load(response)
    return sanitize(raw, start, end)

def duration(seconds):
    minutes = int(seconds//60)
    return f'{minutes//60}h {minutes%60:02d}m' if minutes >= 60 else f'{minutes}m'

def render(data, mobile=False):
    w, h, p = (480, 638, 28) if mobile else (900, 425, 40)
    a, white, muted = '#84dfe4', '#edf3f8', '#899ba9'
    e = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">',
        '<title id="title">Ryan · WakaTime</title>',
        f'<desc id="desc">Coding activity from {data["start"]} through {data["end"]}: {duration(data["totalSeconds"])}; {data["activeDays"]} active days. Updated daily.</desc>',
        '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#111e29"/><stop offset="1" stop-color="#090e16"/></linearGradient><linearGradient id="bar" x2="0" y2="1"><stop stop-color="#92ecea"/><stop offset="1" stop-color="#367688"/></linearGradient></defs>',
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="20" fill="url(#bg)" stroke="#293744"/>']
    def text(x,y,value,size=11,color=muted,weight=400,anchor='start'):
        e.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" font-family="SFMono-Regular, Menlo, Consolas, monospace">{html.escape(str(value))}</text>')
    def rect(x,y,width,height,color,rx=3):
        e.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" rx="{rx}" fill="{color}"/>')
    text(p,37,'RYAN',12,white,600)
    text(w-p,37,'WAKATIME',10,a,anchor='end')
    columns=(w-2*p)/3
    stats=[('LAST 7 DAYS',duration(data['totalSeconds'])),('DAILY AVG',duration(data['dailyAverageSeconds'])),('ACTIVE DAYS',str(data['activeDays'])+' / 7')]
    for i,(label,value) in enumerate(stats):
        text(p+i*columns,80,label,9)
        text(p+i*columns,122,value,25 if mobile else 35,a if i==0 else white,500)
    rect(p,150,w-2*p,1,'#293744',0)
    text(p,183,'DAILY ACTIVITY',10,white)
    chartw=w-2*p if mobile else 422
    base=318
    peak=max(x['seconds'] for x in data['daily']) or 1
    slot=chartw/7
    for i,d in enumerate(data['daily']):
        x=p+i*slot+slot/2
        barh=d['seconds']/peak*84
        rect(x-10,base-max(2,barh),20,max(2,barh),'url(#bar)' if d['seconds'] else '#253540',4)
        text(x,base-barh-12,duration(d['seconds']),8,anchor='middle')
        text(x,base+23,dt.date.fromisoformat(d['date']).strftime('%a'),9,anchor='middle')
    lx,ly,lw=(p,393,w-2*p) if mobile else (520,183,340)
    text(lx,ly,'LANGUAGES',10,white)
    colors=['#8ae3e3','#82b9ee','#b09cde','#d5b887','#81929d']
    rows=data['languages'][:4]
    rest=sum(x['percent'] for x in data['languages'][4:])
    if rest: rows=rows+[{'name':'Remaining','percent':rest}]
    for i,row in enumerate(rows):
        y=ly+29+i*32
        text(lx,y,row['name'][:22],11,white)
        text(lx+lw,y,f'{row["percent"]:.1f}%',10,muted,anchor='end')
        rect(lx,y+8,lw,3,'#253340',1.5)
        rect(lx,y+8,lw*row['percent']/100,3,colors[i],1.5)
    if not rows: text(lx,ly+35,'No language activity recorded',10)
    rect(p,h-52,w-2*p,1,'#293744',0)
    text(p,h-26,data['start'][5:].replace('-','.')+' — '+data['end'][5:].replace('-','.'),9)
    stamp=dt.datetime.fromisoformat(data['updatedAt'])
    text(w-p,h-26,f'UPDATED {stamp:%m.%d} · UTC+8',9,anchor='end')
    e.append('</svg>')
    svg='\n'.join(e)+'\n'
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
    new_commit = gh_api(f'{prefix}/git/commits', {'message': 'Refresh WakaTime activity card [skip deploy]',
                        'tree': tree['sha'], 'parents': [parent]})
    # Non-forced update rejects concurrent changes; never overwrite newer commits.
    gh_api(f'{prefix}/git/refs/heads/{branch}', {'sha': new_commit['sha'], 'force': False}, 'PATCH')
    verified = gh_api(f'{prefix}/contents/.github/profile/wakatime.json', method='GET')
    import base64
    if base64.b64decode(verified['content']).decode() != files['.github/profile/wakatime.json']:
        raise RuntimeError('Published content verification failed; inspect the latest commit before retrying.')
    return new_commit['sha']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=pathlib.Path, default=pathlib.Path(__file__).parent)
    parser.add_argument('--publish', action='store_true')
    args=parser.parse_args()
    data=fetch()
    rendered={'wakatime.json':json.dumps(data, indent=2)+'\n', 'wakatime.svg':render(data), 'wakatime-mobile.svg':render(data,True)}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name,content in rendered.items(): (args.output_dir/name).write_text(content)
    print(f'Generated WakaTime card: {duration(data["totalSeconds"])} through {data["end"]}.')
    if args.publish: print('Published: '+publish(args.output_dir))

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        # Do not log upstream payloads or configuration containing secrets.
        raise SystemExit('WakaTime update failed ('+type(exc).__name__+'); existing public card was preserved unless GitHub publishing had already started. Check API access and remote state.') from None
