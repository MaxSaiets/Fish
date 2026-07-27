import urllib.request, re, json

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

# Get /edit/ page HTML
resp = opener.open('http://shop647643.horoshop.ua/edit/')
html = resp.read().decode('utf-8', 'replace')

print('HTML length:', len(html))
print('First 3000 chars:')
print(html[:3000])

# Find scripts in various formats
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
print('\nAll script srcs:', scripts)
