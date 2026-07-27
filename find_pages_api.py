import urllib.request, re

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

base = 'http://shop647643.horoshop.ua/edit/dist/assets/'

# Chunks from dynamic imports
chunks = [
    'index-OMHbwWST.js',
    'index-BIZJko2X.js',
    'index-CndNMNyW.js',
    'index-HrWvV_2I.js',
    'index-BIitgkc_.js',
    'index-Bag2fEOi.js',
    'index-nQtPsabY.js',
    'index-enqRHiVm.js',
    'index-YTS83Att.js',
    'index-RGO5Lcod.js',
]

for chunk in chunks:
    url = base + chunk
    try:
        r = opener.open(url)
        js = r.read().decode('utf-8', 'replace')
        print(f'\n{"="*60}')
        print(f'CHUNK: {chunk} ({len(js)} chars)')

        # Search for API paths
        api_paths = re.findall(r'["\`](/[a-zA-Z0-9_/.-]{5,100})["\`]', js)
        api_paths = [p for p in api_paths if 'api' in p or 'page' in p or 'save' in p or 'section' in p]
        if api_paths:
            print('  API paths:', list(set(api_paths))[:20])

        # Search for seo/h1/meta fields
        seo_fields = re.findall(r'["\`]([^"\`]{0,30}(?:seo|h1|meta|title|description|keywords)[^"\`]{0,30})["\`]', js, re.IGNORECASE)
        if seo_fields:
            print('  SEO fields:', list(set(seo_fields))[:15])

        # Search for PUT/POST with URL template
        http_calls = re.findall(r'(?:put|post|patch)\s*\([`""][^`""]{0,200}[`""]\)', js, re.IGNORECASE)
        if http_calls:
            print('  HTTP calls:', http_calls[:10])

        # Has 'pages' or 'section' references?
        if 'pages' in js.lower() or 'section' in js.lower():
            print('  *** HAS pages/section references ***')
            page_ctx = re.findall(r'.{40}(?:pages|section).{40}', js, re.IGNORECASE)
            for ctx in page_ctx[:5]:
                print('   ctx:', ctx)

    except urllib.error.HTTPError as e:
        print(f'  {chunk}: HTTP {e.code}')
    except Exception as e:
        print(f'  {chunk}: {e}')
