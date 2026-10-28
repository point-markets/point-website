#!/usr/bin/env python3
"""
Point Market static site builder.

  content/posts/*.md   -> one article each (YAML front matter + HTML or Markdown body)
  static/              -> homepage, assets, .htaccess template (copied as-is)

Outputs:
  public/   live site (status: published only)      -> pointmarkets.sa
  preview/  published + drafts, noindex             -> test.pointmarkets.sa

Run:  python3 tools/build.py
"""
import os, re, sys, json, html, shutil, datetime
from urllib.parse import quote, unquote

import yaml
try:
    import markdown as md
except ImportError:
    md = None

sys.path.insert(0, os.path.dirname(__file__))
from theme import SITE, ar_date, icon, page  # noqa: E402
import legal  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONTENT = os.path.join(ROOT, 'content', 'posts')
STATIC = os.path.join(ROOT, 'static')
REQUIRED = ['title', 'slug', 'status', 'date', 'description', 'cover']


# ---------- helpers ----------
def plain(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def trunc(t, n=155):
    if len(t) <= n:
        return t
    return t[:n].rsplit(' ', 1)[0].rstrip('،,.:؛') + '…'


def load_posts():
    posts, errors = [], []
    for fn in sorted(os.listdir(CONTENT)):
        if not fn.endswith(('.md', '.html')) or fn.startswith('_'):
            continue
        raw = open(os.path.join(CONTENT, fn), encoding='utf-8').read()
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', raw, re.S)
        if not m:
            errors.append(f'{fn}: missing front matter'); continue
        fm = yaml.safe_load(m.group(1)) or {}
        body = m.group(2).strip()
        is_draft = str(fm.get('status', '')).strip().lower() == 'draft'
        miss = [k for k in REQUIRED if not fm.get(k) and not (k == 'cover' and is_draft)]
        if miss:
            errors.append(f'{fn}: missing {", ".join(miss)}'); continue
        fm['status'] = str(fm['status']).strip().lower()
        if is_draft:
            fm.setdefault('cover', '/assets/img/hero.jpg')
        if fm['status'] not in ('draft', 'published'):
            errors.append(f'{fn}: status must be draft or published'); continue
        fm['slug'] = re.sub(r'[^a-z0-9-]+', '-', str(fm['slug']).lower()).strip('-')
        fm['date'] = str(fm['date'])
        fm['modified'] = str(fm.get('modified') or fm['date'])
        if not body.lstrip().startswith('<'):
            if md is None:
                errors.append(f'{fn}: Markdown body but python-markdown not installed'); continue
            body = md.markdown(body, extensions=['tables', 'sane_lists'])
        fm['body_raw'] = body
        posts.append(fm)
    slugs = [p['slug'] for p in posts]
    for s in set(slugs):
        if slugs.count(s) > 1:
            errors.append(f'duplicate slug: {s}')
    return posts, errors


JAHEZ = 'https://jahez.go.link/1YlM4'
JAHEZ_IMG = r'%D8%AC%D8%A7%D9%87%D8%B2'  # "جاهز" in the banner file name


def process(body):
    toc = []

    def h2id(m):
        i = len(toc) + 1
        toc.append((f's{i}', plain(m.group(2))))
        return f'<h2{m.group(1)} id="s{i}">{m.group(2)}</h2>'
    body = re.sub(r'<h2([^>]*)>(.*?)</h2>', h2id, body, flags=re.S)
    body = re.sub(r'(<table.*?</table>)', r'<div class="table-scroll">\1</div>', body, flags=re.S)
    # Jahez order banner: make the banner image (and the "تطبيق جاهز" mention next to it) link to the Jahez app
    body = re.sub(r'(?<!<a href="' + re.escape(JAHEZ) + r'" target="_blank" rel="noopener">)(<img [^>]*' + JAHEZ_IMG + r'[^>]*>)',
                  r'<a href="' + JAHEZ + r'" target="_blank" rel="noopener">\1</a>', body)
    body = re.sub(r'(<img [^>]*' + JAHEZ_IMG + r'[^>]*>\s*</a>\s*<p[^>]*>(?:(?!</p>).)*?)تطبيق جاهز',
                  r'\1<a href="' + JAHEZ + r'" target="_blank" rel="noopener">تطبيق جاهز</a>', body, count=1, flags=re.S)
    body = re.sub(r'<img (?![^>]*loading=)', '<img loading="lazy" ', body)
    body = re.sub(r'<a href="(https?://(?!(www\.)?pointmarkets\.sa)[^"]+)"(?![^>]*target=)',
                  r'<a href="\1" target="_blank" rel="noopener"', body)
    return body, toc


def faq_from(body):
    m = re.search(r'<h2[^>]*>[^<]*(?:الأسئلة الشائعة|أسئلة شائعة)[^<]*</h2>(.*?)(?=<h2 |$)', body, re.S)
    if not m:
        return []
    qa = re.findall(r'<h3[^>]*>(.*?)</h3>\s*(.*?)(?=<h3|$)', m.group(1), re.S)
    return [(plain(q), plain(a)) for q, a in qa if plain(a)]


ORG = {'@type': 'Organization', '@id': SITE + '/#org', 'name': 'بوينت ماركت', 'url': SITE + '/',
       'logo': {'@type': 'ImageObject', 'url': SITE + '/assets/img/logo.png'}}

DRAFT_BANNER = ('<div style="position:fixed;bottom:16px;left:16px;z-index:99;background:#f5c400;color:#053947;'
                'font-weight:800;padding:10px 16px;border-radius:12px;box-shadow:0 10px 30px #0003;font-size:14px">'
                'مسودة — غير منشورة على الموقع</div>')


def enrich(p):
    body, toc = process(p['body_raw'])
    text = plain(body)
    words = len(text.split())
    p.update(body=body, toc=toc, words=words, faq=faq_from(body),
             mins=int(p.get('reading_minutes') or max(2, round(words / 200))),
             excerpt=trunc(p.get('excerpt') or p['description'], 140),
             cat=p.get('category') or 'نصائح وأدلة تسوق',
             cover_alt=p.get('cover_alt') or p['title'],
             cover_abs=p['cover'] if str(p['cover']).startswith('http') else SITE + '/' + str(p['cover']).lstrip('/'))
    return p


def card(p, featured=False):
    badge = ('<span class="tag" style="background:#e6f6f8"><i></i>مجدولة ' + ar_date(p['date']) + '</span>') if p.get('scheduled') else \
            ('<span class="tag" style="background:#fff7d1"><i></i>مسودة</span>' if p['status'] == 'draft' else '')
    return (f'<a class="post-card{" featured" if featured else ""}" href="/blog/{p["slug"]}/">'
            f'<div class="thumb"><img src="{p["cover"]}" alt="{html.escape(p["cover_alt"])}" loading="{"eager" if featured else "lazy"}"></div>'
            f'<div class="body"><span class="tag"><i></i>{html.escape(p["cat"])}</span>{badge}<h2>{html.escape(p["title"])}</h2>'
            f'<p>{html.escape(p["excerpt"])}</p><div class="foot"><span>{ar_date(p["date"])} · {p["mins"]} دقائق قراءة</span>'
            f'<span class="more">اقرأ المقال {icon("arrow", 15)}</span></div></div></a>')


def iso(d):
    return d.replace(' ', 'T') + ('+03:00' if len(d) > 10 else '')


def unlink_missing(body, slugs):
    """Links to blog posts that aren't in this build (drafts / scheduled) become plain text,
    so the live site never has broken internal links. They turn back into links once the target is published."""
    def fix(m):
        return m.group(0) if m.group(1) in slugs else m.group(2)
    return re.sub(r'<a href="/blog/([a-z0-9-]+)/"[^>]*>(.*?)</a>', fix, body, flags=re.S)


def article(p, all_posts, preview):
    p = dict(p, body=unlink_missing(p['body'], {o['slug'] for o in all_posts}))
    others = [o for o in all_posts if o['slug'] != p['slug']][:3]
    url = f"{SITE}/blog/{p['slug']}/"
    toc_html = ''
    if len(p['toc']) >= 3:
        toc_html = ('<nav class="toc" aria-label="محتويات المقال"><b>في هذا المقال</b><ol>'
                    + ''.join(f'<li><a href="#{i}">{html.escape(t)}</a></li>' for i, t in p['toc']) + '</ol></nav>')
    art = {'@type': 'BlogPosting', '@id': url + '#article', 'mainEntityOfPage': url, 'headline': p['title'],
           'description': p['description'], 'image': [p['cover_abs']], 'datePublished': iso(p['date']),
           'dateModified': iso(p['modified']), 'inLanguage': 'ar', 'author': {'@id': SITE + '/#org'},
           'publisher': {'@id': SITE + '/#org'}, 'articleSection': p['cat'], 'wordCount': p['words']}
    if p.get('focus_keyword'):
        art['keywords'] = p['focus_keyword']
    graph = [art, {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'الرئيسية', 'item': SITE + '/'},
        {'@type': 'ListItem', 'position': 2, 'name': 'المدونة', 'item': SITE + '/blog/'},
        {'@type': 'ListItem', 'position': 3, 'name': p['title'], 'item': url}]}, ORG]
    if p['faq']:
        graph.append({'@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in p['faq']]})
    share = quote(p['title'] + ' ' + url)
    body = f'''<section class="page-hero"><div class="container">
<ol class="crumbs"><li><a href="/">الرئيسية</a></li><li><a href="/blog/">المدونة</a></li><li aria-current="page">{html.escape(trunc(p['title'], 48))}</li></ol>
<a class="tag" href="/blog/category/{cat_slug(p)}/"><i></i>{html.escape(p['cat'])}</a>
<h1 style="margin-top:16px">{html.escape(p['title'])}</h1>
<div class="meta-row"><span>{icon('cal', 17)}<time datetime="{p['date'][:10]}">{ar_date(p['date'])}</time></span><span>{icon('clock', 17)}{p['mins']} دقائق قراءة</span><span>فريق بوينت ماركت</span></div>
</div></section>
<div class="article-wrap"><div class="container">
<figure class="article-cover"><img src="{p['cover']}" alt="{html.escape(p['cover_alt'])}" fetchpriority="high"></figure>
<div class="article-grid">
<article class="prose">
{p['body']}
<div class="share"><span>شارك المقال:</span><a href="https://wa.me/?text={share}" target="_blank" rel="noopener">واتساب</a><a href="https://x.com/intent/post?text={share}" target="_blank" rel="noopener">X</a><a href="https://www.linkedin.com/sharing/share-offsite/?url={quote(url)}" target="_blank" rel="noopener">لينكدإن</a><button type="button" data-copy>نسخ الرابط</button></div>
</article>
<aside class="aside">{toc_html}<div class="cta-card"><b>كل احتياجاتك في مكان واحد</b><p>أكثر من 37 فرعاً في الرياض وجدة، بأفضل جودة وأفضل سعر.</p><a class="button yellow" href="/branches/">ابحث عن أقرب فرع {icon('arrow', 17)}</a></div></aside>
</div></div></div>
<section class="related"><div class="container"><div class="head"><div><span class="kicker">من المدونة</span><h2>مقالات قد تهمك</h2></div><a class="all" href="/blog/">كل المقالات {icon('arrow', 16)}</a></div><div class="post-grid">{''.join(card(o) for o in others)}</div></div></section>'''
    head = (f'<meta property="article:published_time" content="{iso(p["date"])}">\n'
            f'<meta property="article:modified_time" content="{iso(p["modified"])}">\n')
    out = page(f"{p['title']} | بوينت ماركت", p['description'], url, body,
               {'@context': 'https://schema.org', '@graph': graph}, p['cover_abs'], 'article', head)
    if p['status'] == 'draft':
        out = out.replace('</body>', DRAFT_BANNER + '\n</body>')
    return out


CATS = [('tips', 'نصائح وأدلة تسوق', 'نصائح وأدلة تسوق',
         'نصائح وأدلة تسوق من بوينت ماركت: قوائم مقاضي جاهزة، أدلة مواسم، وأفكار عملية لتجهيز بيتك بأفضل جودة وأفضل سعر.'),
        ('news', 'أخبار', 'أخبار بوينت',
         'آخر أخبار بوينت ماركت: الفروع الجديدة، الشراكات، الرعايات، والفعاليات.')]


def cat_slug(p):
    for slug, _, cat, _ in CATS:
        if p['cat'] == cat:
            return slug
    return 'tips'


def blog_index(posts, cat=None):
    if cat:
        slug, label, catname, desc = cat
        shown = [p for p in posts if cat_slug(p) == slug]
        url = f'{SITE}/blog/category/{slug}/'
        title = f'{label} | مدونة بوينت ماركت'
        crumbs = f'<li><a href="/">الرئيسية</a></li><li><a href="/blog/">المدونة</a></li><li aria-current="page">{label}</li>'
        h1 = f'{label} <em>بوينت</em>' if slug == 'news' else f'نصائح وأدلة <em>تسوق</em>'
        lead = desc
    else:
        shown = posts
        url = SITE + '/blog/'
        title = 'مدونة بوينت ماركت | نصائح تسوق وقوائم مقاضي وأخبار بوينت'
        desc = 'مدونة بوينت ماركت: قوائم مقاضي جاهزة، أدلة تسوق للمواسم، ونصائح عملية لتجهيز بيتك بأفضل جودة وأفضل سعر، مع آخر أخبار بوينت.'
        crumbs = '<li><a href="/">الرئيسية</a></li><li aria-current="page">المدونة</li>'
        h1 = 'أفكار ونصائح لتسوّق <em>أذكى</em>'
        lead = 'قوائم مقاضي جاهزة، أدلة مواسم، ونصائح عملية لبيت سعودي مرتب، مع آخر أخبار بوينت ماركت.'
    tabs = [('/blog/', 'الكل', len(posts), cat is None)] + \
           [(f'/blog/category/{c[0]}/', c[1], sum(1 for p in posts if cat_slug(p) == c[0]), bool(cat) and cat[0] == c[0]) for c in CATS]
    ON = ' class="on" aria-current="page"'
    tabs_html = '<nav class="cat-tabs" aria-label="أقسام المدونة">' + ''.join(
        f'<a href="{h}"{ON if on else ""}>{l} <small>{n}</small></a>' for h, l, n, on in tabs) + '</nav>'
    crumb_items = [{'@type': 'ListItem', 'position': 1, 'name': 'الرئيسية', 'item': SITE + '/'},
                   {'@type': 'ListItem', 'position': 2, 'name': 'المدونة', 'item': SITE + '/blog/'}]
    if cat:
        crumb_items.append({'@type': 'ListItem', 'position': 3, 'name': cat[1], 'item': url})
    schema = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'CollectionPage' if cat else 'Blog', '@id': url + '#page', 'url': url, 'name': title,
         'inLanguage': 'ar', 'publisher': {'@id': SITE + '/#org'},
         ('hasPart' if cat else 'blogPost'): [{'@type': 'BlogPosting', 'headline': p['title'], 'url': f"{SITE}/blog/{p['slug']}/",
                       'datePublished': p['date'][:10], 'image': p['cover_abs']} for p in shown]},
        {'@type': 'BreadcrumbList', 'itemListElement': crumb_items}, ORG]}
    grid = (card(shown[0], True) + ''.join(card(p) for p in shown[1:])) if shown else '<p>لا توجد مقالات في هذا القسم بعد.</p>'
    body = f'''<section class="page-hero"><div class="container">
<ol class="crumbs">{crumbs}</ol>
<span class="kicker">مدونة بوينت</span>
<h1 style="margin-top:14px">{h1}</h1>
<p class="lead">{lead}</p>
</div></section>
<section class="blog-list"><div class="container">{tabs_html}<div class="post-grid">{grid}</div></div></section>'''
    return page(title, desc, url, body, schema, shown[0]['cover_abs'] if shown else SITE + '/assets/img/hero.jpg')


def legal_page(d):
    url = f"{SITE}/{d['slug']}/"
    secs = d['sections']
    prose = ''.join(f'<h2 id="l{i}">{html.escape(t)}</h2>{b}' for i, (t, b) in enumerate(secs, 1))
    toc = ('<nav class="toc" aria-label="محتويات الصفحة"><b>في هذه الصفحة</b><ol>'
           + ''.join(f'<li><a href="#l{i}">{html.escape(t)}</a></li>' for i, (t, _) in enumerate(secs, 1)) + '</ol></nav>')
    other = [x for x in legal.PAGES if x is not d][0]
    schema = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'WebPage', '@id': url + '#page', 'url': url, 'name': d['title'], 'description': d['meta'],
         'inLanguage': 'ar', 'dateModified': legal.UPDATED, 'publisher': {'@id': SITE + '/#org'}},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'الرئيسية', 'item': SITE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': d['title'], 'item': url}]}, ORG]}
    body = f'''<section class="page-hero"><div class="container">
<ol class="crumbs"><li><a href="/">الرئيسية</a></li><li aria-current="page">{d['title']}</li></ol>
<span class="kicker">بوينت ماركت</span>
<h1 style="margin-top:14px">{d['h1']}</h1>
<p class="lead">{d['lead']}</p>
<div class="meta-row"><span>{icon('cal', 17)}آخر تحديث: <time datetime="{legal.UPDATED}">{ar_date(legal.UPDATED)}</time></span></div>
</div></section>
<div class="article-wrap legal"><div class="container"><div class="article-grid">
<article class="prose">{prose}
<p class="legal-note">اطّلع أيضاً على <a href="/{other['slug']}/">{other['title']}</a>.</p></article>
<aside class="aside">{toc}</aside>
</div></div></div>'''
    return page(f"{d['title']} | بوينت ماركت", d['meta'], url, body, schema, SITE + '/assets/img/hero.jpg') \
        .replace('<a href="/blog/" class="active" aria-current="page">', '<a href="/blog/">')


OFFER_ICONS = {  # flat placeholder illustrations (replaced by product photos when an item has "image")
 'tomato': '<circle cx="60" cy="68" r="34" fill="#e8553e"/><path d="M60 34l-9 10-12-3 8 10-9 9 14-2 8 9 8-9 14 2-9-9 8-10-12 3z" fill="#3fa34d"/><ellipse cx="48" cy="58" rx="7" ry="4" fill="#fff" opacity=".35" transform="rotate(-30 48 58)"/>',
 'cucumber': '<rect x="14" y="46" width="92" height="30" rx="15" fill="#3fa34d" transform="rotate(-18 60 61)"/><g fill="#2d7e38" transform="rotate(-18 60 61)"><circle cx="34" cy="58" r="2"/><circle cx="52" cy="66" r="2"/><circle cx="70" cy="56" r="2"/><circle cx="86" cy="64" r="2"/></g>',
 'orange': '<circle cx="60" cy="66" r="34" fill="#f28c28"/><path d="M60 32c8-2 14 2 16 8-8 2-14-1-16-8z" fill="#3fa34d"/><ellipse cx="47" cy="55" rx="8" ry="5" fill="#fff" opacity=".35" transform="rotate(-35 47 55)"/>',
 'milk': '<path d="M38 36l22-14 22 14v66H38z" fill="#fff" stroke="#11a9c3" stroke-width="4" stroke-linejoin="round"/><path d="M38 36h44" stroke="#11a9c3" stroke-width="4"/><rect x="46" y="54" width="28" height="26" rx="6" fill="#11a9c3"/><circle cx="60" cy="67" r="6" fill="#fff"/>',
 'labneh': '<rect x="26" y="52" width="68" height="46" rx="10" fill="#fff" stroke="#11a9c3" stroke-width="4"/><rect x="22" y="42" width="76" height="16" rx="8" fill="#11a9c3"/><path d="M40 78c8-8 16 8 24 0s14 4 16 0" fill="none" stroke="#f5c400" stroke-width="5" stroke-linecap="round"/>',
 'eggs': '<path d="M14 70h92l-8 28H22z" fill="#d9b38c"/><g fill="#fff" stroke="#e7dcc9" stroke-width="2"><ellipse cx="34" cy="62" rx="14" ry="18"/><ellipse cx="60" cy="58" rx="14" ry="18"/><ellipse cx="86" cy="62" rx="14" ry="18"/></g>',
 'bread': '<path d="M24 58c0-18 16-28 36-28s36 10 36 28v8H24z" fill="#c98a45"/><rect x="24" y="62" width="72" height="36" rx="8" fill="#e0a560"/><g stroke="#b9772f" stroke-width="3" stroke-linecap="round"><path d="M44 46l-4 14"/><path d="M60 42l-2 18"/><path d="M76 46l2 14"/></g>',
 'rice': '<path d="M34 28h52l8 74H26z" fill="#fff" stroke="#11a9c3" stroke-width="4" stroke-linejoin="round"/><rect x="38" y="52" width="44" height="28" rx="6" fill="#f5c400"/><path d="M60 42v6M54 44l6 4 6-4" stroke="#11a9c3" stroke-width="3" fill="none" stroke-linecap="round"/>',
 'oil': '<rect x="48" y="22" width="24" height="14" rx="3" fill="#3fa34d"/><path d="M50 36h20l10 20v46H40V56z" fill="#6a9b2f"/><rect x="44" y="62" width="32" height="26" rx="5" fill="#fff"/><circle cx="60" cy="75" r="6" fill="#3fa34d"/>',
 'dates': '<path d="M24 62h72l-8 36H32z" fill="#8a5a2b"/><g fill="#5b3a17"><ellipse cx="42" cy="56" rx="10" ry="14" transform="rotate(-20 42 56)"/><ellipse cx="62" cy="52" rx="10" ry="14"/><ellipse cx="82" cy="56" rx="10" ry="14" transform="rotate(20 82 56)"/></g><ellipse cx="62" cy="48" rx="3" ry="5" fill="#fff" opacity=".25"/>',
 'juice': '<path d="M36 40h48l-6 62H42z" fill="#f28c28"/><path d="M36 40h48l-1.5 16h-45z" fill="#ffd28a"/><path d="M70 40l14-22" stroke="#e8553e" stroke-width="5" stroke-linecap="round"/><circle cx="40" cy="48" r="0"/>',
 'coffee': '<path d="M30 54h52v26a20 20 0 0 1-20 20H50a20 20 0 0 1-20-20z" fill="#8a5a2b"/><path d="M82 60h8a10 10 0 0 1 0 20h-8" fill="none" stroke="#8a5a2b" stroke-width="6"/><g fill="none" stroke="#11a9c3" stroke-width="4" stroke-linecap="round"><path d="M44 42c-6-6 6-10 0-16"/><path d="M60 42c-6-6 6-10 0-16"/></g>',
}
OFFER_TINT = {'خضار وفواكه': '#eaf8ee', 'ألبان وبيض': '#e6f6f8', 'مخبوزات': '#fdf1dc', 'مواد غذائية': '#fff6cf', 'مشروبات': '#e9f1ff'}


def offers_page():
    """Branch offers page (test build only for now): content/offers.json -> /offers/."""
    data = json.load(open(os.path.join(ROOT, 'content', 'offers.json'), encoding='utf-8'))
    branch = next((b for b in load_branches() if b['name'] == data['branch']), None)
    items = data['items']
    cats = []
    for it in items:
        if it['category'] not in cats:
            cats.append(it['category'])
    fmt = lambda v: f'{v:.2f}'
    cards = ''
    for it in items:
        pct = round((it['was'] - it['now']) / it['was'] * 100)
        media = (f'<img class="{"pack" if it.get("fit") == "contain" else "photo"}" src="{html.escape(it["image"])}" alt="{html.escape(it["name"])}" loading="lazy">' if it.get('image') else
                 f'<svg viewBox="0 0 120 120" role="img" aria-label="{html.escape(it["name"])}">{OFFER_ICONS.get(it.get("icon"), "")}</svg>')
        tint = '#ffffff' if it.get('fit') == 'contain' else OFFER_TINT.get(it['category'], '#eaf9fc')
        cards += (f'<article class="offer-card" data-cat="{html.escape(it["category"])}">'
                  f'<div class="offer-media" style="--tint:{tint}">{media}<span class="offer-badge">خصم <bdi dir="ltr">{pct}%</bdi></span></div>'
                  f'<span class="offer-cat">{html.escape(it["category"])}</span>'
                  f'<h3>{html.escape(it["name"])}</h3><p class="offer-unit">{html.escape(it["unit"])}</p>'
                  f'<div class="offer-price"><b>{fmt(it["now"])}</b><span>ر.س</span><s>{fmt(it["was"])}</s></div>'
                  f'<p class="offer-save">توفّر <bdi dir="ltr">{fmt(round(it["was"] - it["now"], 2))}</bdi> ر.س</p></article>')
    feats = ''
    for it in [x for x in items if x.get('featured')][:3]:
        pct = round((it['was'] - it['now']) / it['was'] * 100)
        pic = (f'<img src="{html.escape(it["image"])}" alt="{html.escape(it["name"])}">' if it.get('image') else
               f'<svg viewBox="0 0 120 120" role="img" aria-label="{html.escape(it["name"])}">{OFFER_ICONS.get(it.get("icon"), "")}</svg>')
        feats += (f'<article class="feat-card"><div class="feat-pic">{pic}</div><div class="feat-body">'
                  f'<span class="offer-badge">خصم <bdi dir="ltr">{pct}%</bdi></span><h3>{html.escape(it["name"])}</h3>'
                  f'<p class="offer-unit">{html.escape(it["unit"])}</p>'
                  f'<div class="offer-price"><b>{fmt(it["now"])}</b><span>ر.س</span><s>{fmt(it["was"])}</s></div></div></article>')
    bn = data.get('banner') or {}
    featured = (f'<section class="offers-featured" aria-label="{html.escape(bn.get("title", "عروض مميزة"))}"><div class="container">'
                f'<div class="feat-head"><span class="kicker">{html.escape(bn.get("title", "عروض مميزة"))}</span><p>{html.escape(bn.get("sub", ""))}</p></div>'
                f'<div class="feat-row">{feats}</div></div></section>') if feats else ''
    chips = '<button type="button" class="on" data-cat="">الكل</button>' + ''.join(
        f'<button type="button" data-cat="{html.escape(c)}">{html.escape(c)}</button>' for c in cats)
    demo = ''
    where = (f'<a href="{branch["map"]}" target="_blank" rel="noopener">موقع الفرع على الخرائط {icon("pin", 17)}</a>' if branch else '')
    url = SITE + '/offers/'
    jlogo = os.path.exists(os.path.join(STATIC, 'assets', 'img', 'jahez-logo.png'))
    jmark = '<img src="/assets/img/jahez-logo.png" alt="جاهز">' if jlogo else '<span class="jz-word">جاهز</span>'
    body = f'''<section class="offers-hero"><div class="container">
<ol class="crumbs"><li><a href="/">الرئيسية</a></li><li aria-current="page">العروض</li></ol>
<div class="oh-grid"><div class="oh-text">
<span class="oh-ribbon">عروض الأسبوع</span>
<h1>عروض فرع <em>{html.escape(data['branch'])}</em></h1>
<p class="lead">خصومات حقيقية على مقاضيك اليومية، من {ar_date(data['valid_from'])} إلى {ar_date(data['valid_to'])} أو حتى نفاد الكمية.</p>
<div class="offers-meta"><span>{icon('pin', 17)}فرع {html.escape(data['branch'])}، {html.escape(data['city'])}</span>{where}</div></div>
<svg class="oh-art" viewBox="0 0 300 260" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M70 96h160l14 140H56z" fill="rgba(255,255,255,.08)"/><path d="M110 96c0-34 20-54 40-54s40 20 40 54"/><circle cx="150" cy="168" r="34" fill="#f5c400" stroke="#002b3c"/><path d="M137 184l26-32" stroke="#002b3c"/><circle cx="136" cy="153" r="5" stroke="#002b3c"/><circle cx="164" cy="183" r="5" stroke="#002b3c"/><g transform="rotate(14 250 60)"><path d="M214 34h44l22 22-34 34-32-34z" fill="#f5c400" stroke="#002b3c"/><circle cx="232" cy="52" r="5" stroke="#002b3c"/></g><path d="M40 60l8 18 18 8-18 8-8 18-8-18-18-8 18-8z"/><path d="M270 160l5 11 11 5-11 5-5 11-5-11-11-5 11-5z"/></svg>
<div class="oh-stamp" aria-hidden="true"><b>حتى</b><strong>{ar_date(data['valid_to']).split()[0]}</strong><span>{' '.join(ar_date(data['valid_to']).split()[1:])}</span></div></div>
</div></section>
'''
    body += f'''{featured}
<section class="jz-banner"><div class="container"><a class="jz-card" href="{JAHEZ}" target="_blank" rel="noopener">
<div class="jz-logo">{jmark}</div>
<div class="jz-text"><b>نفس العروض تصلك لين باب البيت</b><p>اطلب من بوينت عبر تطبيق جاهز.</p></div>
<span class="jz-cta">اطلب الآن {icon('arrow', 17)}</span></a></div></section>
<section class="offers"><div class="container">{demo}
<div class="offers-chips" aria-label="القسم">{chips}</div>
<div class="offers-grid">{cards}</div>
<p class="offers-note">العروض والخصومات المعلنة سارية حسب مدتها المحددة وحتى نفاد الكمية، والسعر المعتمد هو السعر المعروض في الفرع وقت الشراء. اطّلع على <a href="/terms/">الشروط والأحكام</a>.</p>
<div class="br-jahez"><div><b>ما تقدر توصل الفرع؟</b><p>اطلب مقاضيك من بوينت عبر تطبيق جاهز، وتوصلك لباب البيت.</p></div><a class="button yellow" href="{JAHEZ}" target="_blank" rel="noopener">اطلب عبر جاهز {icon('arrow', 17)}</a></div>
</div></section>
<script>(function(){{var cs=document.querySelectorAll('.offers-chips button'),cards=document.querySelectorAll('.offer-card');
cs.forEach(function(b){{b.onclick=function(){{cs.forEach(function(x){{x.classList.toggle('on',x===b)}});cards.forEach(function(c){{c.hidden=!!b.dataset.cat&&c.dataset.cat!==b.dataset.cat}})}}}});}})();</script>'''
    return page(f"عروض فرع {data['branch']} | بوينت ماركت", 'عروض فرع ' + data['branch'], url, body,
                {'@context': 'https://schema.org', '@type': 'WebPage', 'name': 'العروض', 'url': url}, SITE + '/assets/img/hero.jpg') \
        .replace('<a href="/blog/" class="active" aria-current="page">', '<a href="/blog/">') \
        .replace('index, follow, max-image-preview:large', 'noindex, nofollow')


def load_branches():
    """Single source of truth: the branch list inside the homepage bundle (static/assets/app.js)."""
    a = open(os.path.join(STATIC, 'assets', 'app.js'), encoding='utf-8').read()
    rows = re.findall(r'\["(الرياض|جدة)","([^"]+)","(https://[^"]+)"\]', a)
    seen, out = {}, []
    for city, name, url in rows:
        seen[name] = seen.get(name, 0) + 1
        out.append({'city': city, 'name': name, 'map': url, 'n': seen[name]})
    for b in out:  # disambiguate duplicate district names (e.g. two branches in النزهة)
        b['label'] = f"{b['name']} {b['n']}" if seen[b['name']] > 1 and not re.search(r'\d$', b['name']) else b['name']
    return out


REGIONS = [('north', 'شمال الرياض', 'شمال'), ('east', 'شرق الرياض', 'شرق'), ('west', 'غرب الرياض', 'غرب'),
           ('center', 'وسط الرياض', 'وسط'), ('south', 'جنوب الرياض', 'جنوب')]
REGION_OF = {  # Riyadh district -> region (confirm uncertain ones with the client)
    'الرحمانية': 'north', 'المحمدية': 'north', 'الربيع': 'north', 'النفل': 'north', 'النزهة 1': 'north', 'النزهة 2': 'north',
    'النرجس': 'north', 'العارض': 'north', 'يو ووك': 'north', 'الورود': 'north', 'الملك سلمان': 'north', 'أبو بكر': 'north',
    'الياسمين': 'north', 'أنس بن مالك': 'north', 'الندى': 'north', 'الملقا': 'north',
    'خريص': 'east', 'الملك عبدالله': 'east', 'الروضة': 'east', 'النهضة': 'east', 'غرناطة': 'east', 'النسيم': 'east',
    'الرمال 1': 'east', 'الرمال 2': 'east', 'المونسية': 'east', 'السلي': 'east', 'الجنادرية': 'east',
    'لبن': 'west', 'نجم الدين': 'west', 'المزاحمية': 'west',
    'التحلية': 'center', 'التواصل': 'center',
    'الرفيعة': 'south',
}
ZONES = {  # schematic Riyadh map (viewBox 0 0 320 360): west on the left, east on the right
    'north': 'M60 70 Q160 10 260 70 L222 128 Q160 104 98 128 Z',
    'west': 'M60 70 L98 128 Q84 180 98 232 L60 290 Q14 180 60 70 Z',
    'east': 'M260 70 Q306 180 260 290 L222 232 Q236 180 222 128 Z',
    'south': 'M60 290 L98 232 Q160 256 222 232 L260 290 Q160 350 60 290 Z',
    'center': 'M98 128 Q160 104 222 128 Q236 180 222 232 Q160 256 98 232 Q84 180 98 128 Z',
}
ZONE_LABEL = {'north': (160, 78), 'west': (66, 184), 'east': (254, 184), 'south': (160, 298), 'center': (160, 184)}

BR_JS = r"""<script>(function(){
var city='الرياض',region='all',q='';
var $=function(s){return [].slice.call(document.querySelectorAll(s))};
var cards=$('.br-card'),groups=$('.br-group'),count=document.querySelector('.br-count'),empty=document.querySelector('.br-empty'),chips=document.querySelector('.br-chips'),inp=document.querySelector('.br-search input');
function norm(s){return s.replace(/[أإآ]/g,'ا').replace(/ة/g,'ه').replace(/ى/g,'ي').replace(/^حي\s*/,'').trim()}
function run(){
  var n=0;
  cards.forEach(function(c){var ok=(q?true:c.dataset.city===city&&(city!=='الرياض'||region==='all'||c.dataset.region===region))&&(!q||norm(c.dataset.q).indexOf(q)>-1);c.hidden=!ok;if(ok)n++});
  groups.forEach(function(g){g.hidden=!g.querySelector('.br-card:not([hidden])')});
  empty.hidden=n>0;count.textContent=n?(n+' '+(n>2&&n<11?'فروع':(n>10?'فرعاً':'فرع'))+(q?' مطابقة':(city==='جدة'?' في جدة':(region==='all'?' في الرياض':' في '+({north:'شمال',east:'شرق',west:'غرب',center:'وسط',south:'جنوب'}[region])+' الرياض')))):'';
  chips.classList.toggle('off',city!=='الرياض'||!!q);
  $('.br-city button').forEach(function(b){b.classList.toggle('on',!q&&b.dataset.city===city)});
  $('.br-chips button').forEach(function(b){b.classList.toggle('on',b.dataset.region===region)});
  $('.br-zone,.br-zl').forEach(function(z){z.classList.toggle('on',region!=='all'&&z.dataset.region===region)});
  $('.br-map-card').forEach(function(m){m.hidden=m.dataset.for!==city});
  if(window.brMapSync)brMapSync(city,region);
  try{history.replaceState(null,'',(city==='جدة'?'#jeddah':(region!=='all'?'#'+region:location.pathname)))}catch(e){}
}
function top(){var m=document.querySelector('.br-main');if(m.getBoundingClientRect().top<0)scrollTo({top:m.getBoundingClientRect().top+scrollY-(innerWidth<700?200:190),behavior:'smooth'})}
$('.br-city button').forEach(function(b){b.onclick=function(){city=b.dataset.city;region='all';q='';inp.value='';run();top()}});
$('.br-chips button').forEach(function(b){b.onclick=function(){region=b.dataset.region;run();top()}});
$('.br-zone,.br-zl').forEach(function(z){z.addEventListener('click',function(){city='الرياض';q='';inp.value='';region=(region===z.dataset.region?'all':z.dataset.region);run();if(innerWidth<1000)document.querySelector('.br-results').scrollIntoView({behavior:'smooth'})})});
inp.addEventListener('input',function(e){q=norm(e.target.value);run()});
window.brSet=function(k){city='الرياض';q='';inp.value='';region=(region===k?'all':k);run();top()};
var h=location.hash.slice(1);if(h==='jeddah')city='جدة';else if(['north','east','west','center','south'].indexOf(h)>-1)region=h;
run();
})();</script>"""


BR_MAP_JS = r"""<script src="/assets/vendor/leaflet/leaflet.js"></script>
<script>(function(){
var el=document.getElementById('br-leaflet');if(!window.L||!el)return;
el.parentNode.classList.add('has-map');
var counts=__COUNTS__;
var names={north:'شمال',east:'شرق',west:'غرب',center:'وسط',south:'جنوب'};
var C={north:[24.83,46.66],east:[24.74,46.86],west:[24.63,46.55],center:[24.70,46.69],south:[24.58,46.72]}; /* approximate */
var map=L.map(el,{zoomControl:false,scrollWheelZoom:false,dragging:!L.Browser.mobile,tap:false,zoomSnap:.25});
L.control.zoom({position:'bottomleft'}).addTo(map);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:17,className:'br-tiles',attribution:'&copy; OpenStreetMap'}).addTo(map);
var mk={},grp=L.featureGroup().addTo(map);
Object.keys(C).forEach(function(k){
  if(!counts[k])return;
  var size=Math.round(46+Math.sqrt(counts[k])*9);
  var m=L.marker(C[k],{icon:L.divIcon({className:'br-bub-wrap',iconSize:[size,size],iconAnchor:[size/2,size/2],
    html:'<button type="button" class="br-bub" style="width:'+size+'px;height:'+size+'px"><b>'+counts[k]+'</b><span>'+names[k]+'</span></button>'}),keyboard:false}).addTo(grp);
  m.on('click',function(){window.brSet&&brSet(k)});
  mk[k]=m;
});
map.fitBounds(grp.getBounds(),{padding:[60,60]});
window.brMapSync=function(city,region){
  Object.keys(mk).forEach(function(k){var e=mk[k].getElement();e&&e.classList.toggle('on',region===k);e&&e.classList.toggle('dim',region!=='all'&&region!==k)});
  setTimeout(function(){map.invalidateSize()},60);
};
var h=location.hash.slice(1);brMapSync('الرياض',mk[h]?h:'all');
})();</script>"""


def branches_page():
    br = load_branches()
    for b in br:
        b['region'] = REGION_OF.get(b['label'], REGION_OF.get(b['name'], 'center')) if b['city'] == 'الرياض' else ''
    url = SITE + '/branches/'
    riyadh = [b for b in br if b['city'] == 'الرياض']
    jeddah = [b for b in br if b['city'] == 'جدة']
    rcount = {k: sum(1 for b in riyadh if b['region'] == k) for k, _, _ in REGIONS}
    rname = {k: n for k, n, _ in REGIONS}
    rshort = {k: t for k, _, t in REGIONS}

    def card(b, n):
        tag = rname[b['region']] if b['region'] else 'جدة'
        q = html.escape(f"{b['label']} {b['city']} {tag}")
        wa = 'https://wa.me/966599232857?text=' + quote(f"مرحباً بوينت، عندي استفسار عن فرع {b['label']} - {b['city']}")
        return (f'<li class="br-card" data-city="{b["city"]}" data-region="{b["region"]}" data-q="{q}"><div class="br-row">'
                f'<a class="br-main-link" href="{html.escape(b["map"])}" target="_blank" rel="noopener" aria-label="الاتجاهات إلى بوينت ماركت {html.escape(b["label"])}">'
                f'<span class="br-pin">{icon("pin", 18)}</span>'
                f'<span class="br-info"><b>{html.escape(b["label"])}</b><small>{tag}</small></span></a>'
                f'<a class="br-call" href="{wa}" target="_blank" rel="noopener" aria-label="تواصل واتساب بخصوص فرع {html.escape(b["label"])}">{icon("wa", 16)}<span dir="ltr">+966 59 923 2857</span></a>'
                f'<a class="br-go" href="{html.escape(b["map"])}" target="_blank" rel="noopener">الاتجاهات {icon("arrow", 14)}</a></div></li>')

    groups, n = '', 0
    for k, name, _ in REGIONS:
        items = [b for b in riyadh if b['region'] == k]
        if not items:
            continue
        cards = ''
        for b in items:
            n += 1
            cards += card(b, n)
        groups += (f'<section class="br-group" data-region="{k}"><div class="br-gh"><h2>{name}</h2><span>{len(items)} {"فرع" if len(items) in (1, 2) or len(items) > 10 else "فروع"}</span></div>'
                   f'<ul class="br-list">{cards}</ul></section>')
    cards = ''
    for b in jeddah:
        n += 1
        cards += card(b, n)
    groups += f'<section class="br-group" data-region="jeddah"><div class="br-gh"><h2>جدة</h2><span>{len(jeddah)} فروع</span></div><ul class="br-list">{cards}</ul></section>'

    zones = ''.join(f'<path class="br-zone" data-region="{k}" d="{ZONES[k]}"><title>{rname[k]}</title></path>' for k, _, _ in REGIONS)
    labels = ''.join(f'<g class="br-zl" data-region="{k}" transform="translate({ZONE_LABEL[k][0]} {ZONE_LABEL[k][1]})"><text class="n" y="-2">{rcount[k]}</text><text class="t" y="17">{short}</text></g>'
                     for k, _, short in REGIONS)
    chips = (f'<button type="button" class="on" data-region="all">كل المناطق <small>{len(riyadh)}</small></button>'
             + ''.join(f'<button type="button" data-region="{k}">{short} <small>{rcount[k]}</small></button>' for k, _, short in REGIONS if rcount[k]))

    faq = [
        ('كم عدد فروع بوينت ماركت؟', f'لدى بوينت ماركت {len(br)} فرعاً: {len(riyadh)} فرعاً في الرياض و{len(jeddah)} فروع في جدة.'),
        ('أين تقع فروع بوينت ماركت في الرياض؟', 'تتوزع فروع بوينت على شمال الرياض وشرقها وغربها ووسطها وجنوبها. اختر منطقتك من الفلتر لتظهر لك الفروع القريبة منك.'),
        ('كيف أصل إلى أقرب فرع لي؟', 'اختر المدينة والمنطقة أو ابحث باسم الحي، ثم اضغط «الاتجاهات» ليفتح موقع الفرع مباشرة على خرائط Google.'),
        ('هل يمكنني طلب المقاضي من بوينت ماركت أونلاين؟', 'نعم، يمكنك طلب مقاضيك من بوينت ماركت عبر تطبيق جاهز لتصلك إلى باب بيتك.'),
    ]
    faq_html = ''.join(f'<details class="faq-item"><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)
    stores = [{'@type': 'GroceryStore', 'name': f"بوينت ماركت - {b['label']}", 'hasMap': b['map'],
               'address': {'@type': 'PostalAddress', 'addressLocality': b['city'],
                           'addressRegion': 'منطقة الرياض' if b['city'] == 'الرياض' else 'منطقة مكة المكرمة',
                           'streetAddress': b['name'] if re.search(r'(يو ووك|أبو بكر|أنس بن مالك|نجم الدين|التحلية)', b['name']) else 'حي ' + re.sub(r' [0-9]$', '', b['name']),
                           'addressCountry': 'SA'},
               'parentOrganization': {'@id': SITE + '/#org'}} for b in br]
    schema = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'CollectionPage', '@id': url + '#page', 'url': url, 'name': 'فروع بوينت ماركت', 'inLanguage': 'ar',
         'publisher': {'@id': SITE + '/#org'},
         'mainEntity': {'@type': 'ItemList', 'numberOfItems': len(br),
                        'itemListElement': [{'@type': 'ListItem', 'position': i, 'item': st} for i, st in enumerate(stores, 1)]}},
        {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'الرئيسية', 'item': SITE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'الفروع', 'item': url}]}, ORG]}

    jed_names = '، '.join(b['label'] for b in jeddah)
    body = f"""<section class="br-hero"><div class="container">
<ol class="crumbs"><li><a href="/">الرئيسية</a></li><li aria-current="page">الفروع</li></ol>
<div class="br-hero-grid"><div>
<span class="kicker">فروعنا</span>
<h1>بوينت، <em>أقرب إليك</em></h1>
<p class="lead">{len(br)} فرعاً في الرياض وجدة. اختر مدينتك ومنطقتك، أو ابحث باسم حيّك.</p>
<div class="br-search">{icon('search', 20)}<input type="search" placeholder="ابحث باسم الحي، مثلاً: النرجس" aria-label="ابحث عن فرع"></div>
</div>
<figure class="br-photo"><img src="/assets/img/branch-front.jpg" alt="واجهة أحد فروع بوينت ماركت" width="1600" height="812" fetchpriority="high"><ul class="br-stats"><li><b>{len(br)}</b><span>فرعاً</span></li><li><b>{len(riyadh)}</b><span>في الرياض</span></li><li><b>{len(jeddah)}</b><span>في جدة</span></li></ul></figure>
</div></div></section>
<div class="br-bar"><div class="container">
<div class="br-city" aria-label="المدينة"><button type="button" class="on" data-city="الرياض">الرياض <small>{len(riyadh)}</small></button><button type="button" data-city="جدة">جدة <small>{len(jeddah)}</small></button></div>
<div class="br-chips" aria-label="المنطقة">{chips}</div>
</div></div>
<section class="br-main"><div class="container br-layout">
<div class="br-panel"><div class="br-panel-head"><b class="br-count" aria-live="polite"></b><span>للتواصل والاتجاهات اختر الفرع</span></div>
<div class="br-results">{groups}<p class="br-empty" hidden>ما لقينا فرع بهذا الاسم. جرّب اسم حي ثاني أو غيّر المنطقة.</p></div></div>
<aside class="br-map">
<div class="br-map-card" data-for="الرياض"><div class="br-leaflet" id="br-leaflet" role="application" aria-label="خريطة مناطق الرياض"></div><svg class="br-fallback" viewBox="0 0 320 360" role="img" aria-label="خريطة مناطق الرياض">{zones}{labels}</svg><p class="br-map-note">اضغط على المنطقة لعرض فروعها · المواقع تقريبية</p></div>
<div class="br-map-card br-jed" data-for="جدة" hidden><div class="br-jed-art">{icon('pin', 54)}</div><b>فروع جدة</b><p>{len(jeddah)} فروع: {jed_names}.</p></div>
</aside>
</div>
<div class="container"><div class="br-jahez"><div><b>ما تقدر توصل الفرع؟</b><p>اطلب مقاضيك من بوينت عبر تطبيق جاهز، وتوصلك لباب البيت.</p></div><a class="button yellow" href="{JAHEZ}" target="_blank" rel="noopener">اطلب عبر جاهز {icon('arrow', 17)}</a></div></div>
</section>
<section class="br-faq"><div class="container"><h2>أسئلة شائعة عن الفروع</h2>{faq_html}</div></section>
""" + BR_JS + BR_MAP_JS.replace("__COUNTS__", json.dumps(rcount))
    return page('فروع بوينت ماركت في الرياض وجدة | ابحث عن أقرب فرع',
                f'فروع بوينت ماركت: {len(br)} فرعاً في الرياض وجدة. اختر منطقتك في الرياض (شمال، شرق، غرب، وسط، جنوب) أو ابحث باسم الحي وافتح موقع الفرع على خرائط Google.',
                url, body, schema, SITE + '/assets/img/store.jpg', extra_head='<link rel="stylesheet" href="/assets/vendor/leaflet/leaflet.css">\n').replace('<a href="/blog/" class="active" aria-current="page">', '<a href="/blog/">') \
        .replace('<a href="/branches/">الفروع', '<a href="/branches/" class="active" aria-current="page">الفروع', 1)


def not_found():
    body = f'''<section class="page-hero" style="min-height:70vh"><div class="container">
<span class="kicker">خطأ 404</span>
<h1 style="margin-top:14px">الصفحة غير <em>موجودة</em></h1>
<p class="lead">يبدو أن الرابط تغيّر أو لم يعد متاحاً. جرّب العودة للرئيسية أو تصفّح أحدث مقالات المدونة.</p>
<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:28px"><a class="button yellow" href="/">الصفحة الرئيسية {icon('arrow')}</a><a class="button" style="background:#fff;border:1px solid var(--line);color:var(--ink)" href="/blog/">المدونة</a></div>
</div></section>'''
    return page('الصفحة غير موجودة | بوينت ماركت', 'الصفحة المطلوبة غير موجودة.', SITE + '/404', body,
                {'@context': 'https://schema.org', '@type': 'WebPage', 'name': '404'},
                SITE + '/assets/img/hero.jpg').replace('index, follow, max-image-preview:large', 'noindex')


def redirects(posts):
    lines = []
    for p in posts:
        old = unquote(str(p.get('old_url') or '')).strip('/')
        if old:
            lines.append(f'RewriteRule ^{re.escape(old).replace(chr(92) + "-", "-")}/?$ /blog/{p["slug"]}/ [R=301,L,NC]')
    for p in posts:
        if p.get('wp_id'):
            lines.append(f'RewriteCond %{{QUERY_STRING}} (^|&)p={int(p["wp_id"])}(&|$)\nRewriteRule ^$ /blog/{p["slug"]}/? [R=301,L]')
    return '\n'.join(lines)


def llms(posts):
    s = f'''# بوينت ماركت (Point Market)

> سلسلة سوبرماركت سعودية بشعار "أفضل جودة بأفضل سعر"، بأكثر من 37 فرعاً في الرياض وجدة. توفر المنتجات الغذائية والمنزلية اليومية، والخضار والفواكه الطازجة، والمنتجات الصحية والعضوية، مع خدمة توصيل عبر تطبيق جاهز.

- الموقع: {SITE}/
- البريد: info@pointmarkets.sa
- واتساب: +966599232857
- انستغرام: https://www.instagram.com/point_marketsa/
- لينكدإن: https://www.linkedin.com/company/point-marketsa/
- تيك توك: https://www.tiktok.com/@marketspoint

## الصفحات الرئيسية

- [الصفحة الرئيسية]({SITE}/): من نحن، الأقسام، الفروع، والتواصل
- [المدونة]({SITE}/blog/): أدلة تسوق وقوائم مقاضي وأخبار بوينت

## المدونة

'''
    return s + ''.join(f"- [{p['title']}]({SITE}/blog/{p['slug']}/): {p['description']}\n" for p in posts)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)



def bust_cache(out):
    """Append ?v=<content-hash> to asset URLs so browsers fetch new CSS/JS after every change."""
    import hashlib, glob
    assets = ['/assets/site.css', '/assets/blog.css', '/assets/app.js', '/assets/motion.js', '/assets/newsletter.js']
    ver = {}
    for a in assets:
        f = out + a
        if os.path.exists(f):
            ver[a] = hashlib.md5(open(f, 'rb').read()).hexdigest()[:8]
    for h in glob.glob(out + '/**/*.html', recursive=True):
        t = open(h, encoding='utf-8').read()
        for a, v in ver.items():
            t = t.replace('"' + a + '"', '"' + a + '?v=' + v + '"')
        open(h, 'w', encoding='utf-8').write(t)


def _build(out, posts, preview):
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(STATIC, out, ignore=shutil.ignore_patterns('htaccess.tpl', '.DS_Store'))
    for p in posts:
        write(f'{out}/blog/{p["slug"]}/index.html', article(p, posts, preview))
    write(f'{out}/blog/index.html', blog_index(posts))
    for c in CATS:
        write(f'{out}/blog/category/{c[0]}/index.html', blog_index(posts, c))
    write(f'{out}/blog/posts.json', json.dumps([{'title': p['title'], 'slug': p['slug'], 'url': f"{SITE}/blog/{p['slug']}/",
          'status': p['status'], 'date': p['date'], 'focus_keyword': p.get('focus_keyword', '')} for p in posts], ensure_ascii=False, indent=1))
    write(f'{out}/404.html', not_found())
    for d in legal.PAGES:
        write(f'{out}/{d["slug"]}/index.html', legal_page(d))
    write(f'{out}/branches/index.html', branches_page())
    if preview:
        write(f'{out}/offers/index.html', offers_page())  # test build only until offers go live
        idx = open(f'{out}/index.html', encoding='utf-8').read()
        write(f'{out}/index.html', idx.replace('<meta name="viewport"', '<meta name="robots" content="noindex">\n<meta name="viewport"'))
        # noindex is enforced by meta tag + X-Robots-Tag header (crawlers must be allowed to see it)
        write(f'{out}/robots.txt', 'User-agent: *\nAllow: /\n')
        write(f'{out}/.htaccess', 'Options -Indexes\nDirectoryIndex index.html\nErrorDocument 404 /404.html\n'
              'AddDefaultCharset UTF-8\nAddType font/woff2 .woff2\n<IfModule mod_headers.c>\nHeader set X-Robots-Tag "noindex, nofollow"\n</IfModule>\n')
        return
    pub = [p for p in posts if p['status'] == 'published']
    today = datetime.date.today().isoformat()
    urls = [(SITE + '/', today), (SITE + '/blog/', max([p['modified'][:10] for p in pub] or [today]))] + \
           [(f"{SITE}/blog/category/{c[0]}/", today) for c in CATS] + \
           [(f"{SITE}/{d['slug']}/", legal.UPDATED) for d in legal.PAGES] + [(SITE + '/branches/', today)] + \
           [(f"{SITE}/blog/{p['slug']}/", p['modified'][:10]) for p in pub]
    write(f'{out}/sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + ''.join(f'  <url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n' for u, d in urls) + '</urlset>\n')
    write(f'{out}/robots.txt', f'User-agent: *\nAllow: /\nDisallow: /wp-admin/\n\nSitemap: {SITE}/sitemap.xml\n')
    write(f'{out}/llms.txt', llms(pub))
    tpl = open(os.path.join(STATIC, 'htaccess.tpl'), encoding='utf-8').read()
    write(f'{out}/.htaccess', tpl.replace('{{REDIRECTS}}', redirects(pub)))


def build(out, posts, preview):
    _build(out, posts, preview)
    bust_cache(out)


def main():
    posts, errors = load_posts()
    if errors:
        print('Content errors:\n  ' + '\n  '.join(errors))
        sys.exit(1)
    posts = [enrich(p) for p in posts]
    posts.sort(key=lambda p: p['date'], reverse=True)
    # scheduled publishing: a 'published' post with a future date stays a draft until that date (Riyadh time)
    now = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    for p in posts:
        if p['status'] == 'published' and str(p['date']) > now:
            p['status'] = 'draft'
            p['scheduled'] = True
    published = [p for p in posts if p['status'] == 'published']
    build(os.path.join(ROOT, 'public'), published, preview=False)
    build(os.path.join(ROOT, 'preview'), posts, preview=True)
    print(f'Built {len(published)} published + {len(posts) - len(published)} draft posts')
    for p in posts:
        print(f"  [{p['status']:9}] {p['slug']}  (toc {len(p['toc'])}, faq {len(p['faq'])})")


if __name__ == '__main__':
    main()
