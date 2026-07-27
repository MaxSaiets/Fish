import urllib.request, urllib.parse, json, re, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [('User-Agent','Mozilla/5.0')]

data = json.dumps({'login':'api_work','password':'Do183183Do'}).encode()
req = urllib.request.Request('http://shop647643.horoshop.ua/core-api/admin/security/login', data=data, headers={'Content-Type':'application/json'})
opener.open(req)
opener.open('http://shop647643.horoshop.ua/adminLegacy/')

# Try a save with minimal fields to see actual error text
params = urllib.parse.urlencode({
    'checkcode': 'yamete_kudasai',
    'id': '1237',
    'handler': '4',
    'handlertable': 'pages',
    'back': 'index.php',
    'names[parent]': '97',
    'names[name][slug]': 'volosin-ta-shnury',
    'names[name][parent]': '2',
    'names[name][forceUpdate]': '1',
    'names[i18n][3][title]': 'Волосінь та шнури',
    'names[inmenu]': '1',
    'names[insitemap]': '1',
}).encode()

req2 = urllib.request.Request(
    'http://shop647643.horoshop.ua/adminLegacy/save.php',
    data=params,
    headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'http://shop647643.horoshop.ua/adminLegacy/',
    }
)

try:
    resp = opener.open(req2)
    html = resp.read().decode('utf-8', 'replace')
    print(f"Status: {resp.status}")
    print(f"URL: {resp.url}")
    print(f"Len: {len(html)}")
    # Look for error messages
    errors = re.findall(r'(?:error|помилка|невоз|шаблон|template)[^<]{0,200}', html, re.I)
    print(f"Errors: {errors[:5]}")
    print(f"First 500: {html[:500]}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} {e.reason}")
    html = e.read().decode('utf-8', 'replace')
    print(f"Error body: {html[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Also try to find template IDs from the catalog section data
print("\n--- Looking for templates via widget ---")
params2 = urllib.parse.urlencode({
    'fields[title]': 'Волосінь та шнури',
    'param_id': '1',
    'record_id': '1237',
    'parent_id': '97',
}).encode()
req3 = urllib.request.Request(
    'http://shop647643.horoshop.ua/_widget/zteel_params_url_Param/updateUriAutomatically',
    data=params2,
    headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'}
)
resp3 = opener.open(req3)
wdata = json.loads(resp3.read())
print(f"Widget response: {json.dumps(wdata, ensure_ascii=False)}")
