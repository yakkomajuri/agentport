const nodeFs = require('fs')
const path = require('path')

function walkHtml(dir) {
    const out = []
    for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) out.push(...walkHtml(full))
        else if (entry.isFile() && entry.name.endsWith('.html')) out.push(full)
    }
    return out
}

const TOC_CLIENT_SCRIPT = `(function () {
    var tocEl = document.querySelector('.toc-float');
    if (!tocEl) return;
    var selector = tocEl.getAttribute('data-toc-selector') || '#page-content';
    var article = document.querySelector(selector);
    if (!article) { tocEl.remove(); return; }
    var headings = article.querySelectorAll('h2, h3');
    if (headings.length < 2) { tocEl.remove(); return; }

    function slug(text) {
        return text.toLowerCase().trim()
            .replace(/[^\\w\\s-]/g, '')
            .replace(/\\s+/g, '-')
            .replace(/-+/g, '-');
    }
    var usedIds = Object.create(null);
    function uniqueId(base) {
        var candidate = base || 'section';
        var i = 2;
        while (usedIds[candidate]) candidate = (base || 'section') + '-' + (i++);
        usedIds[candidate] = true;
        return candidate;
    }

    var list = document.createElement('ul');
    list.className = 'toc-list';
    var entries = [];
    headings.forEach(function (h) {
        if (!h.id) h.id = uniqueId(slug(h.textContent));
        else usedIds[h.id] = true;
        var li = document.createElement('li');
        li.className = h.tagName === 'H3' ? 'toc-l3' : 'toc-l2';
        var a = document.createElement('a');
        a.href = '#' + h.id;
        a.setAttribute('data-target', h.id);
        a.textContent = h.textContent;
        li.appendChild(a);
        list.appendChild(li);
        entries.push(h);
    });

    var titleEl = document.createElement('div');
    titleEl.className = 'toc-title';
    titleEl.textContent = tocEl.getAttribute('data-toc-title') || 'On this page';
    tocEl.textContent = '';
    tocEl.appendChild(titleEl);
    tocEl.appendChild(list);

    var linkEls = tocEl.querySelectorAll('a[data-target]');
    var activeId = null;
    function setActive(id) {
        if (id === activeId) return;
        activeId = id;
        linkEls.forEach(function (a) {
            if (a.getAttribute('data-target') === id) a.classList.add('active');
            else a.classList.remove('active');
        });
    }

    if ('IntersectionObserver' in window) {
        var visible = new Map();
        var observer = new IntersectionObserver(function (changes) {
            changes.forEach(function (change) {
                if (change.isIntersecting) visible.set(change.target.id, change.target);
                else visible.delete(change.target.id);
            });
            var first = null;
            entries.forEach(function (h) {
                if (!first && visible.has(h.id)) first = h.id;
            });
            if (first) setActive(first);
        }, { rootMargin: '-80px 0px -70% 0px', threshold: 0 });
        entries.forEach(function (h) { observer.observe(h); });
    }

    if (entries.length) setActive(entries[0].id);
})();`

function escapeAttr(value) {
    return String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')
}

module.exports = function tocPlugin(config = {}) {
    const {
        minHeadings = 3,
        exclude = [],
        selector = '#page-content',
        title = 'On this page',
    } = config

    const excludeSet = new Set(exclude.map((p) => p.replace(/^\//, '')))

    return {
        name: 'toc-plugin',
        version: '1.0.0',
        onBuildComplete: (fs, outputDir) => {
            const files = walkHtml(outputDir)
            for (const file of files) {
                const rel = path.relative(outputDir, file).split(path.sep).join('/')
                if (excludeSet.has(rel)) continue

                let html = fs.readFileSync(file, 'utf-8')
                if (html.includes('class="toc-float"')) continue

                const articleMatch = html.match(
                    /<article[^>]*id="page-content"[^>]*>([\s\S]*?)<\/article>/
                )
                if (!articleMatch) continue
                const h2Count = (articleMatch[1].match(/<h2\b/g) || []).length
                if (h2Count < minHeadings) continue

                const tocMarkup =
                    '<aside class="toc-float"' +
                    ' aria-label="' + escapeAttr(title) + '"' +
                    ' data-toc-title="' + escapeAttr(title) + '"' +
                    ' data-toc-selector="' + escapeAttr(selector) + '"></aside>'
                const scriptTag = '<script>' + TOC_CLIENT_SCRIPT + '</script>'

                if (html.includes('</main>')) {
                    html = html.replace('</main>', '</main>' + tocMarkup)
                } else {
                    html = html.replace('</body>', tocMarkup + '</body>')
                }
                html = html.replace('</body>', scriptTag + '</body>')

                fs.writeFileSync(file, html)
            }
        },
    }
}
