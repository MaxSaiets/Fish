import urllib.request, re

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

print('Downloading JS bundle...')
r = opener.open('http://shop647643.horoshop.ua/edit/dist/assets/index-DulHNInW.js')
js = r.read().decode('utf-8', 'replace')
print(f'Bundle size: {len(js)} chars')

# Search for core-api patterns
print('\n=== core-api patterns ===')
patterns = re.findall(r'["\`]([^"\`]*core-api[^"\`]{0,120})["\`]', js)
seen = set()
for p in patterns:
    if p not in seen:
        seen.add(p)
        print(' ', p)

# Search for page-related PUT/POST endpoints
print('\n=== PUT/POST page patterns ===')
put_patterns = re.findall(r'(put|post|patch)\([^\)]{0,200}page[^\)]{0,100}\)', js, re.IGNORECASE)
for p in put_patterns[:20]:
    print(' ', p[:200])

# Search for "website" endpoints
print('\n=== website endpoints ===')
web_patterns = re.findall(r'["\`]([^"\`]*website[^"\`]{0,80})["\`]', js)
seen2 = set()
for p in web_patterns:
    if p not in seen2:
        seen2.add(p)
        print(' ', p)

# Search for seo-related fields
print('\n=== seo fields ===')
seo_patterns = re.findall(r'["\`]([^"\`]*seo[_-][^"\`]{0,60})["\`]', js, re.IGNORECASE)
seen3 = set()
for p in seo_patterns[:30]:
    if p not in seen3:
        seen3.add(p)
        print(' ', p)

# Look for sections/pages save pattern
print('\n=== save / update patterns ===')
save_patterns = re.findall(r'(save|update|edit)[^;]{0,300}core-api', js, re.IGNORECASE)
for p in save_patterns[:10]:
    print(' ', p[:300])
