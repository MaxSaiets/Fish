import urllib.request, re

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

r = opener.open('http://shop647643.horoshop.ua/edit/dist/assets/index-DulHNInW.js')
js = r.read().decode('utf-8', 'replace')
print(f'Bundle size: {len(js)} chars')

# More aggressive search - find all URL-like strings
print('\n=== All API paths (starts with /) ===')
paths = re.findall(r'["\`](/[a-zA-Z0-9_/-]{5,80})["\`]', js)
seen = set()
for p in sorted(set(paths)):
    if 'admin' in p or 'page' in p or 'section' in p or 'catalog' in p or 'save' in p:
        print(' ', p)

# Search for fetch/axios calls
print('\n=== fetch calls ===')
fetch_calls = re.findall(r'fetch\([^)]{0,200}\)', js)
for f in fetch_calls[:30]:
    print(' ', f[:200])

# Search for axios/http calls
print('\n=== axios/http calls ===')
axios_calls = re.findall(r'axios\.[a-z]+\([^)]{0,200}\)', js)
for a in axios_calls[:20]:
    print(' ', a[:200])

# Search for 'adminLegacy'
print('\n=== adminLegacy refs ===')
leg = re.findall(r'.{50}adminLegacy.{50}', js)
for l in leg[:10]:
    print(' ', l)

# Search for 'save.php'
print('\n=== save.php refs ===')
save = re.findall(r'.{50}save\.php.{50}', js)
for s in save[:10]:
    print(' ', s)

# Search for handler=4
print('\n=== handler=4 refs ===')
h4 = re.findall(r'.{50}handler.{30}4.{30}', js)
for h in h4[:5]:
    print(' ', h)
