// Package dashboard embeds the static-exported Next.js control-plane UI so the
// orchestrator serves it natively — one binary is the whole product (API +
// preview proxy + dashboard), no Node runtime in production.
//
// The assets are produced by `scripts/build-dashboard.sh` (next build with
// output:"export", copied into dist/). The dashboard is a fully client-driven
// app that talks to the same origin it is served from, so embedding it here
// means zero configuration: start the orchestrator, open it in a browser.
package dashboard

import (
	"embed"
	"io/fs"
	"net/http"
	"path"
	"strings"
)

//go:embed all:dist
var assets embed.FS

// content returns the embedded site root.
func content() fs.FS {
	sub, err := fs.Sub(assets, "dist")
	if err != nil {
		// The embed is compiled in; a missing dist is a build error, not a
		// runtime condition.
		panic("dashboard: embedded dist missing: " + err.Error())
	}
	return sub
}

// Available reports whether a real dashboard build is embedded (index.html
// present). Guards the route registration so a binary built without assets
// degrades to 404 instead of serving an empty page.
func Available() bool {
	_, err := fs.Stat(content(), "index.html")
	return err == nil
}

// Handler serves the exported app: exact files, then Next's `<route>.html`
// convention (/play → play.html), then the exported 404 page.
func Handler() http.Handler {
	sub := content()
	files := http.FileServerFS(sub)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := strings.TrimPrefix(path.Clean(r.URL.Path), "/")
		if p == "" || p == "." {
			p = "index.html"
		}
		// Serve only regular files directly — the export can contain BOTH a
		// `play/` payload directory and `play.html`; the page must win (a bare
		// directory would make FileServer redirect and list).
		if st, err := fs.Stat(sub, p); err == nil && !st.IsDir() {
			files.ServeHTTP(w, r)
			return
		}
		if _, err := fs.Stat(sub, p+".html"); err == nil {
			r2 := r.Clone(r.Context())
			r2.URL.Path = "/" + p + ".html"
			files.ServeHTTP(w, r2)
			return
		}
		if b, err := fs.ReadFile(sub, "404.html"); err == nil {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write(b)
			return
		}
		http.NotFound(w, r)
	})
}
