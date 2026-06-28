const REACT_VERSION = '18.3.1';
const BABEL_VERSION = '7.24.7';

const JS_EXTENSIONS = ['.jsx', '.js', '.tsx', '.ts', '.mjs'];

function isJSFile(path) {
  return JS_EXTENSIONS.some(ext => path.endsWith(ext));
}

function isCSSFile(path) {
  return path.endsWith('.css') || path.endsWith('.scss') || path.endsWith('.sass') || path.endsWith('.less');
}

function collectCSS(files) {
  let css = '';
  for (const [path, file] of Object.entries(files)) {
    if (isCSSFile(path)) {
      css += `\n/* ${path} */\n${file.content || ''}\n`;
    }
  }
  return css;
}

function getDir(filePath) {
  const idx = filePath.lastIndexOf('/');
  return idx >= 0 ? filePath.substring(0, idx) : '';
}

function resolveRelativePath(importPath, dir, allFiles) {
  let path = importPath;

  if (path.startsWith('./')) {
    path = path.substring(2);
    path = dir ? `${dir}/${path}` : path;
  } else if (path.startsWith('../')) {
    const dirParts = dir ? dir.split('/') : [];
    while (path.startsWith('../')) {
      dirParts.pop();
      path = path.substring(3);
    }
    path = [...dirParts, path].join('/');
  }

  if (allFiles[path]) return path;

  for (const ext of JS_EXTENSIONS) {
    if (allFiles[`${path}${ext}`]) return `${path}${ext}`;
  }

  for (const ext of JS_EXTENSIONS) {
    if (allFiles[`${path}/index${ext}`]) return `${path}/index${ext}`;
  }

  return path;
}

function parseImportClause(clause) {
  clause = clause.trim();
  const result = { default: null, named: [], namespace: null };

  if (clause.startsWith('*')) {
    const match = clause.match(/\*\s*as\s+(\w+)/);
    if (match) result.namespace = match[1];
    return result;
  }

  const commaIdx = clause.indexOf(',');
  let defaultPart = clause;
  let namedPart = '';

  if (commaIdx >= 0 && clause.indexOf('{') > commaIdx) {
    defaultPart = clause.substring(0, commaIdx).trim();
    namedPart = clause.substring(commaIdx + 1).trim();
  } else if (clause.startsWith('{')) {
    namedPart = clause;
    defaultPart = '';
  }

  if (defaultPart && !defaultPart.startsWith('{')) {
    result.default = defaultPart.trim();
  }

  if (namedPart) {
    const braceMatch = namedPart.match(/\{([^}]+)\}/);
    if (braceMatch) {
      result.named = braceMatch[1]
        .split(',')
        .map(s => {
          const parts = s.trim().split(/\s+as\s+/);
          return parts.length === 2
            ? `${parts[0].trim()}: ${parts[1].trim()}`
            : parts[0].trim();
        });
    }
  }

  return result;
}

function transformPackageImports(code) {
  let result = code;

  result = result.replace(
    /import\s+(\w+)\s*,\s*\{([^}]+)\}\s+from\s+['"]react['"]/g,
    (match, defaultName, named) => {
      const namedClean = named.trim();
      return `const ${defaultName} = window.React;\nconst { ${namedClean} } = window.React;`;
    }
  );

  result = result.replace(
    /import\s+\{([^}]+)\}\s+from\s+['"]react['"]/g,
    (match, named) => `const { ${named.trim()} } = window.React;`
  );

  result = result.replace(
    /import\s+(\w+)\s+from\s+['"]react['"]/g,
    'const $1 = window.React;'
  );

  result = result.replace(
    /import\s+\*\s+as\s+(\w+)\s+from\s+['"]react['"]/g,
    'const $1 = window.React;'
  );

  result = result.replace(
    /import\s+(\w+)\s+from\s+['"]react-dom\/client['"]/g,
    'const $1 = window.ReactDOM;'
  );

  result = result.replace(
    /import\s+\{([^}]+)\}\s+from\s+['"]react-dom\/client['"]/g,
    (match, named) => `const { ${named.trim()} } = window.ReactDOM;`
  );

  result = result.replace(
    /import\s+(\w+)\s+from\s+['"]react-dom['"]/g,
    'const $1 = window.ReactDOM;'
  );

  result = result.replace(
    /import\s+\{([^}]+)\}\s+from\s+['"]react-dom['"]/g,
    (match, named) => `const { ${named.trim()} } = window.ReactDOM;`
  );

  return result;
}

function transformRelativeImports(code, dir, allFiles) {
  const importRegex = /import\s+(.+?)\s+from\s+['"](\.\.?\/[^'"]+)['"]/g;

  return code.replace(importRegex, (match, clause, importPath) => {
    const resolved = resolveRelativePath(importPath, dir, allFiles);
    const parts = parseImportClause(clause);
    const statements = [];

    if (parts.default && parts.named.length > 0) {
      statements.push(
        `const __m = __getModule__('${resolved}');`,
        `const ${parts.default} = __m.default !== undefined ? __m.default : __m;`,
        `const { ${parts.named.join(', ')} } = __m;`
      );
    } else if (parts.default) {
      statements.push(
        `const ${parts.default} = ((__m) => __m.default !== undefined ? __m.default : __m)(__getModule__('${resolved}'))`
      );
    } else if (parts.named.length > 0) {
      statements.push(`const { ${parts.named.join(', ')} } = __getModule__('${resolved}');`);
    } else if (parts.namespace) {
      statements.push(`const ${parts.namespace} = __getModule__('${resolved}');`);
    }

    return statements.join('\n');
  });
}

function transformExports(code) {
  let result = code;
  const exportNames = [];

  result = result.replace(
    /export\s+default\s+function\s+(\w+)\s*\(/g,
    (match, name) => {
      exportNames.push({ key: 'default', value: name });
      return `function ${name}(`;
    }
  );

  result = result.replace(
    /export\s+default\s+class\s+(\w+)/g,
    (match, name) => {
      exportNames.push({ key: 'default', value: name });
      return `class ${name}`;
    }
  );

  result = result.replace(
    /export\s+default\s+/g,
    'module.exports.default = '
  );

  result = result.replace(
    /export\s+function\s+(\w+)/g,
    (match, name) => {
      exportNames.push({ key: name, value: name });
      return `function ${name}`;
    }
  );

  result = result.replace(
    /export\s+class\s+(\w+)/g,
    (match, name) => {
      exportNames.push({ key: name, value: name });
      return `class ${name}`;
    }
  );

  result = result.replace(
    /export\s+(const|let|var)\s+(\{[^}]+\}|\[[^\]]+\]|\w+)/g,
    (match, declType, name) => {
      if (name.startsWith('{') || name.startsWith('[')) {
        const inner = name.replace(/[{}\[\]]/g, '').trim();
        inner.split(',').forEach(n => {
          const trimmed = n.trim().split(/\s+as\s+/)[0].trim().split(':')[0].trim();
          exportNames.push({ key: trimmed, value: trimmed });
        });
      } else {
        exportNames.push({ key: name, value: name });
      }
      return `${declType} ${name}`;
    }
  );

  result = result.replace(
    /export\s+\{([^}]+)\}/g,
    (match, items) => {
      items.split(',').forEach(item => {
        const parts = item.trim().split(/\s+as\s+/);
        const original = parts[0].trim();
        const exported = (parts[1] || parts[0]).trim();
        if (original === 'default') {
          exportNames.push({ key: exported, value: 'module.exports.default' });
        } else {
          exportNames.push({ key: exported, value: original });
        }
      });
      return '';
    }
  );

  const seen = new Set();
  const exportLines = exportNames
    .filter(({ key }) => {
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map(({ key, value }) => `module.exports.${key} = ${value};`)
    .join('\n');

  if (exportLines) {
    result += '\n' + exportLines + '\n';
  }

  return result;
}

function transformModuleCode(code, filePath, allFiles) {
  const dir = getDir(filePath);

  code = code.replace(/^\s*import\s+['"][^'"]+\.(css|scss|less|sass)['"];?\s*$/gm, '');

  code = transformPackageImports(code);

  code = transformRelativeImports(code, dir, allFiles);

  code = transformExports(code);

  return code;
}

function findEntryPoint(files) {
  const candidates = [
    'src/main.jsx',
    'src/index.jsx',
    'src/main.js',
    'src/index.js',
    'src/main.tsx',
    'src/index.tsx',
  ];

  for (const candidate of candidates) {
    if (files[candidate]) return candidate;
  }

  return null;
}

export function buildPreviewHTML(files) {
  const css = collectCSS(files);

  const moduleMap = {};
  for (const [path, file] of Object.entries(files)) {
    if (isJSFile(path)) {
      moduleMap[path] = transformModuleCode(file.content || '', path, files);
    }
  }

  let entry = findEntryPoint(files);

  if (!entry) {
    if (files['src/App.jsx'] || files['src/App.tsx'] || files['src/App.js']) {
      const appPath = files['src/App.jsx'] ? 'src/App.jsx'
        : files['src/App.tsx'] ? 'src/App.tsx'
        : 'src/App.js';

      entry = '__auto_entry__';
      moduleMap[entry] = `const App = ((__m) => __m.default !== undefined ? __m.default : __m)(__getModule__('${appPath}'));
const root = window.ReactDOM.createRoot(document.getElementById('root'));
root.render(window.React.createElement(App));`;
    }
  }

  const moduleSources = Object.entries(moduleMap)
    .map(([path, code]) => `${JSON.stringify(path)}: ${JSON.stringify(code)}`)
    .join(',\n');

  const entryPoint = entry || '__auto_entry__';

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Preview</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    #root { min-height: 100vh; }
    #__error-overlay {
      position: fixed; inset: 0; z-index: 9999;
      background: #1e1e1e; color: #f48771;
      font-family: 'JetBrains Mono', monospace; font-size: 13px;
      padding: 24px; overflow: auto; display: none;
      white-space: pre-wrap; line-height: 1.6;
    }
    #__error-overlay.show { display: block; }
    ${css}
  </style>
</head>
<body>
  <div id="root"></div>
  <div id="__error-overlay"></div>

  <script crossorigin src="https://unpkg.com/react@${REACT_VERSION}/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@${REACT_VERSION}/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/@babel/standalone@${BABEL_VERSION}/babel.min.js"></script>

  <script>
    (function() {
      var __sources__ = {
        ${moduleSources}
      };

      var __cache__ = {};

      function showError(message) {
        var overlay = document.getElementById('__error-overlay');
        overlay.textContent = message;
        overlay.classList.add('show');
        parent.postMessage({ type: 'preview-error', message: message }, '*');
      }

      function clearError() {
        var overlay = document.getElementById('__error-overlay');
        overlay.classList.remove('show');
        overlay.textContent = '';
      }

      ['log', 'error', 'warn', 'info', 'debug'].forEach(function(level) {
        var original = console[level] ? console[level].bind(console) : function() {};
        console[level] = function() {
          original.apply(console, arguments);
          var args = Array.prototype.slice.call(arguments);
          var message = args.map(function(a) {
            if (a === null) return 'null';
            if (a === undefined) return 'undefined';
            if (typeof a === 'object') {
              try { return JSON.stringify(a, null, 2); }
              catch(e) { return String(a); }
            }
            return String(a);
          }).join(' ');
          parent.postMessage({ type: 'console', level: level, message: message }, '*');
        };
      });

      window.addEventListener('error', function(e) {
        var msg = e.error && e.error.stack ? e.error.stack : (e.message || 'Unknown error');
        showError(msg);
      });

      window.addEventListener('unhandledrejection', function(e) {
        var msg = e.reason && e.reason.stack ? e.reason.stack : String(e.reason);
        showError('Unhandled Promise Rejection:\\n' + msg);
      });

      function __getModule__(path) {
        if (__cache__[path]) return __cache__[path];

        var source = __sources__[path];
        if (!source) {
          throw new Error('Module not found: ' + path);
        }

        var transformed;
        try {
          var babelResult = Babel.transform(source, {
            presets: [['react', { runtime: 'classic' }]],
            filename: path,
            sourceMaps: false
          });
          transformed = babelResult.code;
        } catch (err) {
          showError('Babel transform error in ' + path + ':\\n\\n' + err.message);
          throw err;
        }

        var module = { exports: {} };
        __cache__[path] = module.exports;

        try {
          var fn = new Function('module', 'exports', '__getModule__',
            'document', 'window', 'navigator', transformed);
          fn(module, module.exports, __getModule__,
             document, window, navigator);
        } catch (err) {
          __cache__[path] = undefined;
          showError('Runtime error in ' + path + ':\\n\\n' + (err.stack || err.message));
          throw err;
        }

        __cache__[path] = module.exports;
        return module.exports;
      }

      window.__getModule__ = __getModule__;

      function init() {
        clearError();
        try {
          __getModule__(${JSON.stringify(entryPoint)});
        } catch (err) {
          if (!document.getElementById('__error-overlay').classList.contains('show')) {
            showError(err.stack || err.message);
          }
        }
      }

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
      } else {
        init();
      }
    })();
  </script>
</body>
</html>`;

  return html;
}

export default buildPreviewHTML;