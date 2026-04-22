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

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
}

function pageSlug(pagePath) {
    return pagePath
        .replace(/^pages[\\/]/, '')
        .replace(/\.md$/, '')
        .split(path.sep)
        .join('/')
}

function slugToUrl(slug) {
    if (slug === 'index') return '/'
    return '/' + slug
}

function firstH1(markdown) {
    const m = markdown.match(/^#\s+(.+?)\s*$/m)
    return m ? m[1] : null
}

module.exports = function sidebarPlugin(config = {}) {
    const { configFile = 'sidebar.json' } = config
    const pageInfo = new Map()

    return {
        name: 'sidebar-plugin',
        version: '1.1.0',
        onPage: ({ pagePath, frontmatter, markdown }) => {
            const slug = pageSlug(pagePath)
            const label =
                frontmatter.nav_title ||
                frontmatter.title ||
                firstH1(markdown) ||
                slug
            pageInfo.set(slug, { label, url: slugToUrl(slug) })
        },
        onBuildComplete: (fs, outputDir) => {
            const configPath = path.resolve(process.cwd(), configFile)
            if (!nodeFs.existsSync(configPath)) {
                console.warn(
                    `[sidebar-plugin] ${configFile} not found — skipping sidebar generation.`
                )
                return
            }

            let sidebarConfig
            try {
                sidebarConfig = JSON.parse(
                    nodeFs.readFileSync(configPath, 'utf-8')
                )
            } catch (err) {
                console.error(
                    `[sidebar-plugin] Failed to parse ${configFile}: ${err.message}`
                )
                return
            }

            const items = Array.isArray(sidebarConfig)
                ? sidebarConfig
                : sidebarConfig.items || []

            const renderLink = (slug) => {
                const info = pageInfo.get(slug)
                if (!info) {
                    console.warn(
                        `[sidebar-plugin] "${slug}" referenced in ${configFile} but no matching page was found.`
                    )
                    return null
                }
                return `<a href="${escapeHtml(info.url)}" data-path="${escapeHtml(
                    info.url
                )}">${escapeHtml(info.label)}</a>`
            }

            const parts = []
            for (const item of items) {
                if (typeof item === 'string') {
                    const link = renderLink(item)
                    if (link) parts.push(link)
                } else if (item && typeof item === 'object') {
                    if (item.section) {
                        parts.push(
                            `<div class="nav-section">${escapeHtml(
                                item.section
                            )}</div>`
                        )
                    }
                    for (const child of item.items || []) {
                        const link = renderLink(child)
                        if (link) parts.push(link)
                    }
                }
            }

            const indent = '\n                '
            const navInner = parts.join(indent)
            const navRegex = /<nav data-sidebar[^>]*>[\s\S]*?<\/nav>/

            const files = walkHtml(outputDir)
            for (const file of files) {
                let html = fs.readFileSync(file, 'utf-8')
                if (!navRegex.test(html)) continue
                html = html.replace(
                    navRegex,
                    `<nav data-sidebar>${indent}${navInner}\n            </nav>`
                )
                fs.writeFileSync(file, html)
            }
        },
    }
}
