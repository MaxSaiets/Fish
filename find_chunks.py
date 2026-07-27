import urllib.request, re

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

r = opener.open('http://shop647643.horoshop.ua/edit/dist/assets/index-DulHNInW.js')
js = r.read().decode('utf-8', 'replace')
print(f'Main bundle: {len(js)} chars')

# Find chunk references in the bundle
chunks = re.findall(r'["\`]([A-Za-z0-9_-]{5,30}-[A-Za-z0-9_-]{6,12}\.js)["\`]', js)
print(f'Found {len(chunks)} potential chunks: {chunks[:20]}')

# Also find pattern like assets/ChunkName-Hash
asset_chunks = re.findall(r'assets/([A-Za-z0-9_-]+-[A-Za-z0-9]{8})', js)
print(f'Asset refs: {list(set(asset_chunks))[:20]}')

# Look for dynamic import patterns
dyn_imports = re.findall(r'import\([^)]{0,100}\)', js)
print(f'\nDynamic imports: {dyn_imports[:10]}')

# Look for the chunk map (usually something like {1: "ChunkHash", 2: "OtherHash"})
chunk_maps = re.findall(r'\{[^{}]{20,500}\}', js)
for cm in chunk_maps:
    if '.js' in cm and ('pages' in cm.lower() or 'website' in cm.lower() or 'admin' in cm.lower()):
        print('\nChunk map with pages/website/admin:', cm[:500])

# Search for "pages" in the bundle to understand routing
print('\n=== pages routing ===')
page_refs = re.findall(r'.{0,50}["\`]pages["\`].{0,50}', js)
for p in page_refs[:15]:
    print(' ', p)
