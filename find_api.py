import urllib.request, urllib.parse, re, json, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

# Login
data = json.dumps({'login': 'api_work', 'password': 'Do183183Do'}).encode()
req = urllib.request.Request(
    'http://shop647643.horoshop.ua/core-api/admin/security/login',
    data=data, headers={'Content-Type': 'application/json'})
opener.open(req)

# Get /edit/ page to find JS bundle
resp = opener.open('http://shop647643.horoshop.ua/edit/')
html = resp.read().decode('utf-8', 'replace')

# Find all JS bundles
bundles = re.findall(r'src="(/edit/assets/[^"]+\.js)"', html)
print('JS bundles:', bundles)

# Download the main/largest bundle and search for API patterns
for b in bundles:
    url = 'http://shop647643.horoshop.ua' + b
    print(f'\nDownloading {b}...')
    try:
        r = opener.open(url)
        js = r.read().decode('utf-8', 'replace')
        print(f'  Size: {len(js)} chars')

        # Search for API endpoints related to pages/sections
        patterns = [
            r'core-api[^\'"]{0,100}page',
            r'core-api[^\'"]{0,100}section',
            r'core-api[^\'"]{0,100}categ',
            r'/core-api/[a-z/-]+',
            r'PUT.*pages',
            r'POST.*pages',
        ]
        for pat in patterns:
            matches = re.findall(pat, js, re.IGNORECASE)
            if matches:
                print(f'  Pattern "{pat}": {list(set(matches))[:5]}')
    except Exception as e:
        print(f'  Error: {e}')

# Also try known core-api endpoints
print('\n--- Testing core-api endpoints ---')
test_endpoints = [
    '/core-api/admin/pages/1098',
    '/core-api/website/pages/1098',
    '/core-api/admin/sections/1098',
    '/core-api/website/sections/1098',
    '/core-api/admin/catalog/1098',
]
for ep in test_endpoints:
    try:
        r = opener.open('http://shop647643.horoshop.ua' + ep)
        body = r.read().decode('utf-8', 'replace')
        print(f'  {ep}: {r.getcode()} -> {body[:200]}')
    except urllib.error.HTTPError as e:
        print(f'  {ep}: HTTP {e.code}')
    except Exception as e:
        print(f'  {ep}: {e}')
