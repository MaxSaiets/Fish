import urllib.request, urllib.parse, json, re, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [('User-Agent','Mozilla/5.0')]

data = json.dumps({'login':'api_work','password':'Do183183Do'}).encode()
req = urllib.request.Request('http://shop647643.horoshop.ua/core-api/admin/security/login', data=data, headers={'Content-Type':'application/json'})
opener.open(req)
opener.open('http://shop647643.horoshop.ua/adminLegacy/')

urls = [
    'http://shop647643.horoshop.ua/adminLegacy/index.php?handler=4&id=1237',
    'http://shop647643.horoshop.ua/adminLegacy/index.php?handler=4&action=edit&id=1237',
    'http://shop647643.horoshop.ua/adminLegacy/data.php?handler=4&id=1237',
    'http://shop647643.horoshop.ua/adminLegacy/index.php?handler=4&pageid=1237',
]

for url in urls:
    try:
        resp = opener.open(url)
        html = resp.read().decode('utf-8', 'replace')
        title_m = re.search(r'<title>([^<]+)</title>', html)
        name_fields = re.findall(r'name="([^"]+)"', html)
        name_fields = list(set(name_fields))
        tmpl = [f for f in name_fields if 'template' in f.lower()]
        names_fields = [f for f in name_fields if 'names[' in f]
        print(f"URL: {url.split('?')[1]}")
        print(f"  Title: {title_m.group(1) if title_m else 'none'}")
        print(f"  Len: {len(html)}")
        print(f"  Template fields: {tmpl}")
        print(f"  names[] fields: {names_fields[:15]}")
        # Show template select options
        tmpl_select = re.search(r'<select[^>]*template[^>]*>(.*?)</select>', html, re.DOTALL | re.I)
        if tmpl_select:
            opts = re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)', tmpl_select.group(1))
            print(f"  Template options: {opts}")
        print()
    except Exception as e:
        print(f"URL: {url} ERROR: {e}")
        print()
