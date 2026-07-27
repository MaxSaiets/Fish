import urllib.request, re

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

r = opener.open('http://shop647643.horoshop.ua/edit/dist/assets/index-DulHNInW.js')
js = r.read().decode('utf-8', 'replace')

print('=== iframe references ===')
iframe_ctx = re.findall(r'.{100}iframe.{100}', js, re.IGNORECASE)
for i in iframe_ctx[:10]:
    print(' ', i)

print('\n=== "url" query param handling ===')
url_query = re.findall(r'.{60}["\']url["\'].{60}', js)
for u in url_query[:10]:
    print(' ', u)

# Find the Ba and Mr components
print('\n=== Ba component (website route) ===')
ba_ctx = re.findall(r'Ba=.{0,300}', js)
for b in ba_ctx[:3]:
    print(' ', b[:300])

print('\n=== Mr component (child route) ===')
mr_ctx = re.findall(r'Mr=.{0,300}', js)
for m in mr_ctx[:3]:
    print(' ', m[:300])

# Check if it uses postMessage
print('\n=== postMessage refs ===')
pm_ctx = re.findall(r'.{50}postMessage.{50}', js)
for p in pm_ctx[:5]:
    print(' ', p)

# Check for window.location or redirect
print('\n=== location/redirect ===')
loc_ctx = re.findall(r'.{30}(?:location\.href|window\.open|redirect).{30}', js)
for l in loc_ctx[:5]:
    print(' ', l)
