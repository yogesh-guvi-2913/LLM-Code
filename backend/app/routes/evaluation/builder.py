import re
import json
from typing import Dict, Any

REACT_VERSION = "18.3.1"
BABEL_VERSION = "7.24.7"

JS_EXTENSIONS = [".jsx", ".js", ".tsx", ".ts", ".mjs"]


def is_js_file(path: str) -> bool:
    return any(path.endswith(ext) for ext in JS_EXTENSIONS)


def is_css_file(path: str) -> bool:
    return any(path.endswith(ext) for ext in [".css", ".scss", ".sass", ".less"])


def collect_css(files: Dict[str, Any]) -> str:
    css = ""
    for path, file in files.items():
        if is_css_file(path):
            content = file.get("content", "") if isinstance(file, dict) else str(file)
            css += f"\n/* {path} */\n{content}\n"
    return css


def get_dir(file_path: str) -> str:
    idx = file_path.rfind("/")
    return file_path[:idx] if idx >= 0 else ""


def resolve_relative_path(import_path: str, directory: str, all_files: Dict[str, Any]) -> str:
    path = import_path

    if path.startswith("./"):
        path = path[2:]
        path = f"{directory}/{path}" if directory else path
    elif path.startswith("../"):
        dir_parts = directory.split("/") if directory else []
        while path.startswith("../"):
            if dir_parts:
                dir_parts.pop()
            path = path[3:]
        path = "/".join(dir_parts + [path]) if dir_parts else path

    if path in all_files:
        return path

    for ext in JS_EXTENSIONS:
        if f"{path}{ext}" in all_files:
            return f"{path}{ext}"

    for ext in JS_EXTENSIONS:
        if f"{path}/index{ext}" in all_files:
            return f"{path}/index{ext}"

    return path


def parse_import_clause(clause: str) -> dict:
    clause = clause.strip()
    result = {"default": None, "named": [], "namespace": None}

    if clause.startswith("*"):
        match = re.match(r"\*\s*as\s+(\w+)", clause)
        if match:
            result["namespace"] = match.group(1)
        return result

    comma_idx = clause.find(",")
    default_part = clause
    named_part = ""

    if comma_idx >= 0 and clause.find("{") > comma_idx:
        default_part = clause[:comma_idx].strip()
        named_part = clause[comma_idx + 1 :].strip()
    elif clause.startswith("{"):
        named_part = clause
        default_part = ""

    if default_part and not default_part.startswith("{"):
        result["default"] = default_part.strip()

    if named_part:
        brace_match = re.search(r"\{([^}]+)\}", named_part)
        if brace_match:
            result["named"] = [
                parts[1].strip() if len(parts := re.split(r"\s+as\s+", item.strip())) == 2 else parts[0].strip()
                for item in brace_match.group(1).split(",")
            ]

    return result


def transform_package_imports(code: str) -> str:
    result = code

    result = re.sub(
        r"import\s+(\w+)\s*,\s*\{([^}]+)\}\s+from\s+['\"]react['\"]",
        lambda m: f"const {m.group(1)} = window.React;\nconst {{ {m.group(2).strip()} }} = window.React;",
        result,
    )

    result = re.sub(
        r"import\s+\{([^}]+)\}\s+from\s+['\"]react['\"]",
        lambda m: f"const {{ {m.group(1).strip()} }} = window.React;",
        result,
    )

    result = re.sub(
        r"import\s+(\w+)\s+from\s+['\"]react['\"]",
        r"const \1 = window.React;",
        result,
    )

    result = re.sub(
        r"import\s+\*\s+as\s+(\w+)\s+from\s+['\"]react['\"]",
        r"const \1 = window.React;",
        result,
    )

    result = re.sub(
        r"import\s+(\w+)\s+from\s+['\"]react-dom/client['\"]",
        r"const \1 = window.ReactDOM;",
        result,
    )

    result = re.sub(
        r"import\s+\{([^}]+)\}\s+from\s+['\"]react-dom/client['\"]",
        lambda m: f"const {{ {m.group(1).strip()} }} = window.ReactDOM;",
        result,
    )

    result = re.sub(
        r"import\s+(\w+)\s+from\s+['\"]react-dom['\"]",
        r"const \1 = window.ReactDOM;",
        result,
    )

    result = re.sub(
        r"import\s+\{([^}]+)\}\s+from\s+['\"]react-dom['\"]",
        lambda m: f"const {{ {m.group(1).strip()} }} = window.ReactDOM;",
        result,
    )

    return result


def transform_relative_imports(code: str, directory: str, all_files: Dict[str, Any]) -> str:
    import_regex = r"import\s+(.+?)\s+from\s+['\"](\.\.?\/[^'\"]+)['\"]"

    def replacer(match):
        clause = match.group(1)
        import_path = match.group(2)
        resolved = resolve_relative_path(import_path, directory, all_files)
        parts = parse_import_clause(clause)
        statements = []

        if parts["default"] and parts["named"]:
            statements.extend([
                f"const __m = __getModule__('{resolved}');",
                f"const {parts['default']} = __m.default !== undefined ? __m.default : __m;",
                f"const {{ {', '.join(parts['named'])} }} = __m;",
            ])
        elif parts["default"]:
            statements.append(
                f"const {parts['default']} = ((__m) => __m.default !== undefined ? __m.default : __m)(__getModule__('{resolved}'))"
            )
        elif parts["named"]:
            statements.append(f"const {{ {', '.join(parts['named'])} }} = __getModule__('{resolved}');")
        elif parts["namespace"]:
            statements.append(f"const {parts['namespace']} = __getModule__('{resolved}');")

        return "\n".join(statements)

    return re.sub(import_regex, replacer, code)


def transform_exports(code: str) -> str:
    result = code
    export_names = []

    def add_export(key: str, value: str):
        export_names.append({"key": key, "value": value})

    result = re.sub(
        r"export\s+default\s+function\s+(\w+)\s*\(",
        lambda m: (add_export("default", m.group(1)), f"function {m.group(1)}(")[1],
        result,
    )

    result = re.sub(
        r"export\s+default\s+class\s+(\w+)",
        lambda m: (add_export("default", m.group(1)), f"class {m.group(1)}")[1],
        result,
    )

    result = re.sub(r"export\s+default\s+", "module.exports.default = ", result)

    result = re.sub(
        r"export\s+function\s+(\w+)",
        lambda m: (add_export(m.group(1), m.group(1)), f"function {m.group(1)}")[1],
        result,
    )

    result = re.sub(
        r"export\s+class\s+(\w+)",
        lambda m: (add_export(m.group(1), m.group(1)), f"class {m.group(1)}")[1],
        result,
    )

    def handle_named_export(match):
        decl_type = match.group(1)
        name = match.group(2)
        if name.startswith("{") or name.startswith("["):
            inner = re.sub(r"[{}\[\]]", "", name).strip()
            for item in inner.split(","):
                clean_name = item.strip().split()[0].split(":")[0].strip()
                add_export(clean_name, clean_name)
        else:
            add_export(name, name)
        return f"{decl_type} {name}"

    result = re.sub(
        r"export\s+(const|let|var)\s+(\{[^}]+\}|\[[^\]]+\]|\w+)",
        handle_named_export,
        result,
    )

    def handle_export_braces(match):
        items = match.group(1)
        for item in items.split(","):
            parts = re.split(r"\s+as\s+", item.strip())
            original = parts[0].strip()
            exported = parts[1].strip() if len(parts) > 1 else parts[0].strip()
            if original == "default":
                add_export(exported, "module.exports.default")
            else:
                add_export(exported, original)
        return ""

    result = re.sub(r"export\s+\{([^}]+)\}", handle_export_braces, result)

    seen = set()
    export_lines = []
    for exp in export_names:
        if exp["key"] not in seen:
            seen.add(exp["key"])
            export_lines.append(f"module.exports.{exp['key']} = {exp['value']};")

    if export_lines:
        result = result + "\n" + "\n".join(export_lines) + "\n"

    return result


def transform_module_code(code: str, file_path: str, all_files: Dict[str, Any]) -> str:
    directory = get_dir(file_path)

    code = re.sub(r"^\s*import\s+['\"][^'\"]+\.(css|scss|less|sass)['\"]\s*;?\s*$", "", code, flags=re.MULTILINE)

    code = transform_package_imports(code)
    code = transform_relative_imports(code, directory, all_files)
    code = transform_exports(code)

    return code


def find_entry_point(files: Dict[str, Any]) -> str:
    candidates = [
        "src/main.jsx",
        "src/index.jsx",
        "src/main.js",
        "src/index.js",
        "src/main.tsx",
        "src/index.tsx",
    ]

    for candidate in candidates:
        if candidate in files:
            return candidate

    return ""


def build_preview_html(files: Dict[str, Any]) -> str:
    css = collect_css(files)

    module_map = {}
    for path, file in files.items():
        if is_js_file(path):
            content = file.get("content", "") if isinstance(file, dict) else str(file)
            module_map[path] = transform_module_code(content, path, files)

    entry = find_entry_point(files)

    if not entry:
        app_path = None
        for p in ["src/App.jsx", "src/App.tsx", "src/App.js"]:
            if p in files:
                app_path = p
                break

        if app_path:
            entry = "__auto_entry__"
            module_map[entry] = f"""const App = ((__m) => __m.default !== undefined ? __m.default : __m)(__getModule__('{app_path}'));
const root = window.ReactDOM.createRoot(document.getElementById('root'));
root.render(window.React.createElement(App));"""

    module_sources = ",\n".join(
        f"{json.dumps(path)}: {json.dumps(code)}"
        for path, code in module_map.items()
    )

    entry_point = entry or "__auto_entry__"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Preview</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    #root {{ min-height: 100vh; }}
    #__error-overlay {{
      position: fixed; inset: 0; z-index: 9999;
      background: #1e1e1e; color: #f48771;
      font-family: 'JetBrains Mono', monospace; font-size: 13px;
      padding: 24px; overflow: auto; display: none;
      white-space: pre-wrap; line-height: 1.6;
    }}
    #__error-overlay.show {{ display: block; }}
    {css}
  </style>
</head>
<body>
  <div id="root"></div>
  <div id="__error-overlay"></div>

  <script crossorigin src="https://unpkg.com/react@{REACT_VERSION}/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@{REACT_VERSION}/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/@babel/standalone@{BABEL_VERSION}/babel.min.js"></script>

  <script>
    (function() {{
      var __sources__ = {{
        {module_sources}
      }};

      var __cache__ = {{}};

      function showError(message) {{
        var overlay = document.getElementById('__error-overlay');
        overlay.textContent = message;
        overlay.classList.add('show');
      }}

      function clearError() {{
        var overlay = document.getElementById('__error-overlay');
        overlay.classList.remove('show');
        overlay.textContent = '';
      }}

      ['log', 'error', 'warn', 'info', 'debug'].forEach(function(level) {{
        var original = console[level] ? console[level].bind(console) : function() {{}};
        console[level] = function() {{
          original.apply(console, arguments);
          var args = Array.prototype.slice.call(arguments);
          var message = args.map(function(a) {{
            if (a === null) return 'null';
            if (a === undefined) return 'undefined';
            if (typeof a === 'object') {{
              try {{ return JSON.stringify(a, null, 2); }}
              catch(e) {{ return String(a); }}
            }}
            return String(a);
          }}).join(' ');
          window.__consoleLogs__ = window.__consoleLogs__ || [];
          window.__consoleLogs__.push({{ level: level, message: message }});
        }};
      }});

      window.addEventListener('error', function(e) {{
        var msg = e.error && e.error.stack ? e.error.stack : (e.message || 'Unknown error');
        showError(msg);
        window.__runtimeError__ = msg;
      }});

      window.addEventListener('unhandledrejection', function(e) {{
        var msg = e.reason && e.reason.stack ? e.reason.stack : String(e.reason);
        showError('Unhandled Promise Rejection:\\n' + msg);
        window.__runtimeError__ = msg;
      }});

      function __getModule__(path) {{
        if (__cache__[path]) return __cache__[path];

        var source = __sources__[path];
        if (!source) {{
          throw new Error('Module not found: ' + path);
        }}

        var transformed;
        try {{
          var babelResult = Babel.transform(source, {{
            presets: [['react', {{ runtime: 'classic' }}]],
            filename: path,
            sourceMaps: false
          }});
          transformed = babelResult.code;
        }} catch (err) {{
          showError('Babel transform error in ' + path + ':\\n\\n' + err.message);
          throw err;
        }}

        var module = {{ exports: {{}} }};
        __cache__[path] = module.exports;

        try {{
          var fn = new Function('module', 'exports', '__getModule__',
            'document', 'window', 'navigator', transformed);
          fn(module, module.exports, __getModule__,
             document, window, navigator);
        }} catch (err) {{
          __cache__[path] = undefined;
          showError('Runtime error in ' + path + ':\\n\\n' + (err.stack || err.message));
          throw err;
        }}

        __cache__[path] = module.exports;
        return module.exports;
      }}

      window.__getModule__ = __getModule__;

      function init() {{
        clearError();
        try {{
          __getModule__({json.dumps(entry_point)});
        }} catch (err) {{
          if (!document.getElementById('__error-overlay').classList.contains('show')) {{
            showError(err.stack || err.message);
          }}
        }}
      }}

      if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', init);
      }} else {{
        init();
      }}
    }})();
  </script>
</body>
</html>"""

    return html
