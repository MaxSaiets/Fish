import xml.etree.ElementTree as ET, sys
sys.stdout.reconfigure(encoding='utf-8')
tree = ET.parse('D:/FISH/fish-sync/public/horoshop.xml')
root = tree.getroot()
shop = root.find('shop')
cats = shop.find('categories')
cat_dict = {}
for c in cats.findall('category'):
    cid = c.get('id')
    pid = c.get('parentId','')
    cat_dict[cid] = {'name': c.text.strip(), 'parent': pid}

offers = shop.find('offers')
offer_list = offers.findall('offer')

# Check missing cats
used_cats = set(o.findtext('categoryId','') for o in offer_list)
missing = used_cats - set(cat_dict.keys())
print('TOTAL OFFERS:', len(offer_list))
print('MISSING CATS:', missing if missing else 'NONE')
print()
print('=== XML CATEGORY TREE ===')
top = {k:v for k,v in cat_dict.items() if not v['parent']}
for tid,tv in sorted(top.items(), key=lambda x: int(x[0])):
    cnt_top = sum(1 for o in offer_list if o.findtext('categoryId')==tid)
    print('  %s: %s (%d)' % (tid, tv['name'], cnt_top))
    children = {k:v for k,v in cat_dict.items() if v['parent']==tid}
    for cid,cv in sorted(children.items(), key=lambda x: int(x[0])):
        cnt = sum(1 for o in offer_list if o.findtext('categoryId')==cid)
        print('    %s: %s (%d)' % (cid, cv['name'], cnt))

print()
print('=== SAMPLE OFFER ===')
o = offer_list[0]
for child in o:
    if child.tag == 'param':
        print('  param name=%s: %s' % (child.get('name'), child.text))
    elif child.text and child.text.strip():
        print('  %s: %s' % (child.tag, child.text.strip()[:80]))

# Перевірка: чи є parentId в категоріях XML (критично для Horoshop)
print()
print('=== PARENTID CHECK IN XML CATEGORIES ===')
cats_with_parent = [(c.get('id'), c.get('parentId'), c.text.strip())
                     for c in cats.findall('category') if c.get('parentId')]
print('Categories WITH parentId: %d' % len(cats_with_parent))
print('(If parentId present - Horoshop may fail to find by path)')
for cid, pid, name in cats_with_parent[:5]:
    print('  id=%s parentId=%s name=%s' % (cid, pid, name))
print('  ...(first 5 shown)')
