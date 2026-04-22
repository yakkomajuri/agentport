# AgentPort Docs

The AgentPort documentation site, powered by [teeny](https://github.com/yakkomajuri/teeny).

## Layout

```
docs/
├── pages/          ← Markdown content (one page per file)
├── templates/      ← HTML templates (default.html wraps every page)
├── static/         ← CSS and other static assets
├── teeny.config.js
└── package.json
```

Each `.md` file in `pages/` becomes a page at the matching URL — `pages/api.md` → `/api`. `pages/index.md` is the homepage. All pages render into `templates/default.html`, which provides the sidebar navigation and layout.

## Developing

From this directory:

```bash
pnpm install        # one-time
pnpm dev            # dev server on http://localhost:8000 with hot reload
```

## Building

```bash
pnpm build          # outputs static HTML to ./public/
```

## Adding a page

1. Create a new `.md` file in `pages/`. The filename (minus `.md`) becomes the URL slug.
2. Add a matching link in the sidebar nav inside `templates/default.html`.
3. Markdown is rendered via [marked](https://marked.js.org/). Frontmatter is optional — the first `h1` is used as the page title if no `title:` is given.
