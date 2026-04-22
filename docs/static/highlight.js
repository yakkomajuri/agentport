/*
 * Tiny syntax highlighter for AgentPort docs.
 * Mirrors the app's tokenizers (ui/src/components/playground/ResponsePanel.tsx)
 * and emits <span style="color: var(--syn-*)"> so colors track light/dark theme.
 */
(function () {
    var JSON_RE =
        /("(?:\\.|[^"\\])*")\s*:|("(?:\\.|[^"\\])*")|(true|false|null)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}[\],:])|(\s+|.)/g;

    function tokenizeJson(src) {
        var tokens = [];
        var matches = src.matchAll(JSON_RE);
        for (var m of matches) {
            if (m[1] !== undefined) {
                tokens.push({ text: m[1], color: 'var(--syn-constant)' });
                tokens.push({ text: m[0].slice(m[1].length), color: 'var(--syn-comment)' });
            } else if (m[2] !== undefined) {
                tokens.push({ text: m[2], color: 'var(--syn-string)' });
            } else if (m[3] !== undefined) {
                tokens.push({ text: m[3], color: 'var(--syn-keyword)' });
            } else if (m[4] !== undefined) {
                tokens.push({ text: m[4], color: 'var(--syn-variable)' });
            } else if (m[5] !== undefined) {
                tokens.push({ text: m[5], color: 'var(--syn-comment)' });
            } else {
                tokens.push({ text: m[0] });
            }
        }
        return tokens;
    }

    var BASH_BUILTINS = /^(?:if|then|else|elif|fi|case|esac|for|in|while|do|done|return|exit|export|local|readonly|set|unset|function|source|eval|trap|cd|echo)$/;

    var BASH_RE = /(#[^\n]*)|("(?:\\.|[^"\\])*")|('[^']*')|(\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*)|(^|[\s])(--?[A-Za-z][\w-]*)|(\b\d+(?:\.\d+)?\b)|(\||&&|\|\||;|>>?|<<?|&|\\$)|([A-Za-z_][\w./:-]*)|(\s+)|(.)/gm;

    function tokenizeBash(src) {
        var tokens = [];
        var atLineStart = true;
        var matches = src.matchAll(BASH_RE);
        for (var m of matches) {
            if (m[1] !== undefined) {
                tokens.push({ text: m[1], color: 'var(--syn-comment)' });
                atLineStart = false;
            } else if (m[2] !== undefined) {
                tokens.push({ text: m[2], color: 'var(--syn-string)' });
                atLineStart = false;
            } else if (m[3] !== undefined) {
                tokens.push({ text: m[3], color: 'var(--syn-string)' });
                atLineStart = false;
            } else if (m[4] !== undefined) {
                tokens.push({ text: m[4], color: 'var(--syn-variable)' });
                atLineStart = false;
            } else if (m[6] !== undefined) {
                if (m[5]) tokens.push({ text: m[5] });
                tokens.push({ text: m[6], color: 'var(--syn-keyword)' });
                atLineStart = false;
            } else if (m[7] !== undefined) {
                tokens.push({ text: m[7], color: 'var(--syn-variable)' });
                atLineStart = false;
            } else if (m[8] !== undefined) {
                tokens.push({ text: m[8], color: 'var(--syn-keyword)' });
                atLineStart = (m[8] === '|' || m[8] === '&&' || m[8] === '||' || m[8] === ';' || m[8] === '\\');
            } else if (m[9] !== undefined) {
                if (BASH_BUILTINS.test(m[9])) {
                    tokens.push({ text: m[9], color: 'var(--syn-keyword)' });
                } else if (atLineStart) {
                    tokens.push({ text: m[9], color: 'var(--syn-function)' });
                } else {
                    tokens.push({ text: m[9] });
                }
                atLineStart = false;
            } else if (m[10] !== undefined) {
                tokens.push({ text: m[10] });
                if (m[10].indexOf('\n') !== -1) atLineStart = true;
            } else {
                tokens.push({ text: m[0] });
                atLineStart = false;
            }
        }
        return tokens;
    }

    function detectLang(codeEl) {
        var cls = codeEl.className || '';
        var parts = cls.split(/\s+/);
        for (var i = 0; i < parts.length; i++) {
            if (parts[i].indexOf('language-') === 0) return parts[i].slice('language-'.length).toLowerCase();
        }
        return '';
    }

    function render(el, tokens) {
        var frag = document.createDocumentFragment();
        for (var i = 0; i < tokens.length; i++) {
            var t = tokens[i];
            if (t.color) {
                var span = document.createElement('span');
                span.style.color = t.color;
                span.textContent = t.text;
                frag.appendChild(span);
            } else if (t.text) {
                frag.appendChild(document.createTextNode(t.text));
            }
        }
        el.textContent = '';
        el.appendChild(frag);
    }

    function highlightAll() {
        var blocks = document.querySelectorAll('pre > code');
        for (var i = 0; i < blocks.length; i++) {
            var code = blocks[i];
            if (code.dataset.highlighted === 'true') continue;
            var lang = detectLang(code);
            var src = code.textContent || '';
            var tokens = null;
            if (lang === 'json') tokens = tokenizeJson(src);
            else if (lang === 'bash' || lang === 'sh' || lang === 'shell') tokens = tokenizeBash(src);
            if (tokens) {
                render(code, tokens);
                code.dataset.highlighted = 'true';
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', highlightAll);
    } else {
        highlightAll();
    }
})();
