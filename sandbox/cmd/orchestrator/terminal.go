package main

import (
	"context"
	"fmt"
	"net/http"

	"github.com/coder/websocket"
)

// terminal upgrades the candidate browser to a WebSocket and transparently
// proxies it to the claimed container's toolbox terminal WS. Auth is the session
// token (browsers can't set headers on WS, so it rides in ?token=). The proxy is
// frame-transparent: binary I/O and text resize-control pass straight through.
func (s *server) terminal(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	token := r.URL.Query().Get("token")

	sess, err := s.store.GetSession(r.Context(), id)
	if err != nil {
		http.Error(w, "session not found", http.StatusNotFound)
		return
	}
	if token == "" || token != sess.SessionToken {
		http.Error(w, "invalid token", http.StatusUnauthorized)
		return
	}
	if sess.Status != "ACTIVE" {
		http.Error(w, "session not active", http.StatusConflict)
		return
	}
	if sess.HostToolbox == 0 {
		http.Error(w, "container not live", http.StatusConflict)
		return
	}

	client, err := websocket.Accept(w, r, nil)
	if err != nil {
		return
	}
	defer client.CloseNow()
	client.SetReadLimit(1 << 20)

	ctx, cancel := context.WithCancel(r.Context())
	defer cancel()

	upstreamURL := fmt.Sprintf("ws://%s:%d/ws/terminal", sess.NodeHost, sess.HostToolbox)
	upstream, _, err := websocket.Dial(ctx, upstreamURL, nil)
	if err != nil {
		_ = client.Close(websocket.StatusInternalError, "toolbox dial failed")
		return
	}
	defer upstream.CloseNow()
	upstream.SetReadLimit(1 << 20)

	// Bridge both directions; first error tears down the pair.
	go copyFrames(ctx, cancel, client, upstream)
	copyFrames(ctx, cancel, upstream, client)
}

func copyFrames(ctx context.Context, cancel context.CancelFunc, src, dst *websocket.Conn) {
	defer cancel()
	for {
		typ, data, err := src.Read(ctx)
		if err != nil {
			return
		}
		if err := dst.Write(ctx, typ, data); err != nil {
			return
		}
	}
}

// terminalPage serves a self-contained xterm.js terminal. The candidate IDE can
// embed this in an iframe, or the frontend team can lift the WS wiring from it.
func (s *server) terminalPage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(terminalHTML))
}

const terminalHTML = `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Flash Sandbox Terminal</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.min.css" />
<style>
  html,body{margin:0;height:100%;background:#1e1e1e}
  #bar{font:13px ui-monospace,monospace;color:#ccc;padding:6px 10px;background:#252526}
  #term{height:calc(100% - 33px);padding:6px}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
  .ok{background:#3fb950}.bad{background:#f85149}
</style>
</head>
<body>
<div id="bar"><span id="dot" class="dot bad"></span><span id="status">connecting…</span></div>
<div id="term"></div>
<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.min.js"></script>
<script>
(function () {
  var q = new URLSearchParams(location.search);
  var sid = q.get('session'), token = q.get('token');
  var term = new Terminal({ cursorBlink: true, fontFamily: 'ui-monospace, monospace', fontSize: 13,
                            theme: { background: '#1e1e1e' } });
  var fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(document.getElementById('term'));
  fit.fit();

  var status = document.getElementById('status'), dot = document.getElementById('dot');
  function setStatus(t, ok) { status.textContent = t; dot.className = 'dot ' + (ok ? 'ok' : 'bad'); }

  if (!sid || !token) { setStatus('missing session or token', false); return; }

  var proto = location.protocol === 'https:' ? 'wss' : 'ws';
  var ws = new WebSocket(proto + '://' + location.host + '/v1/sessions/' + sid + '/terminal?token=' + encodeURIComponent(token));
  ws.binaryType = 'arraybuffer';
  var enc = new TextEncoder();

  function sendResize() {
    if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
  }

  ws.onopen = function () { setStatus('connected', true); fit.fit(); sendResize(); term.focus(); };
  ws.onclose = function () { setStatus('disconnected', false); term.write('\r\n\x1b[31m[connection closed]\x1b[0m\r\n'); };
  ws.onerror = function () { setStatus('error', false); };
  ws.onmessage = function (ev) {
    if (typeof ev.data === 'string') term.write(ev.data);
    else term.write(new Uint8Array(ev.data));
  };

  term.onData(function (d) { if (ws.readyState === 1) ws.send(enc.encode(d)); });
  window.addEventListener('resize', function () { fit.fit(); sendResize(); });
})();
</script>
</body>
</html>`
