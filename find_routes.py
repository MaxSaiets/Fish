import urllib.request, re

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

r = opener.open('http://shop647643.horoshop.ua/edit/dist/assets/index-DulHNInW.js')
js = r.read().decode('utf-8', 'replace')

# Find route definitions
print('=== Route/path definitions ===')
routes = re.findall(r'path:["\`]([^"\`]+)["\`]', js)
for route in sorted(set(routes)):
    print(' ', route)

print('\n=== import() with component names ===')
# Find lazy imports with their associated route names
lazy_routes = re.findall(r'component:.{0,20}import\(.{0,100}\)', js)
for lr in lazy_routes[:20]:
    print(' ', lr[:200])

print('\n=== All dynamic import targets ===')
imports = re.findall(r'import\("[^"]+"\)', js)
for i in set(imports):
    print(' ', i)

# Search for 'website' in context
print('\n=== website route context ===')
web_ctx = re.findall(r'.{80}website.{80}', js)
for w in web_ctx[:10]:
    print(' ', w)
