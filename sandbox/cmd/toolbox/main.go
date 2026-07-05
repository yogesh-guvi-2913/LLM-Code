// Command toolbox is a static binary embedded in every sandbox image. It starts
// the candidate's dev server as a child process and exposes an HTTP control
// plane to the orchestrator: /claim, /health, /ws/terminal.
//
// Build: CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o toolbox ./cmd/toolbox
package main

import (
	"context"
	"encoding/json"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"sync"
	"time"

	"github.com/coder/websocket"
	"github.com/creack/pty"
)

const (
	appPort     = "3000"  // dev server
	toolboxPort = "49983" // this control plane
)

type state struct {
	mu        sync.Mutex
	mode      string // "warm" | "active"
	sessionID string
	dev       *exec.Cmd
}

var st = &state{mode: "warm"}

func main() {
	// /app/src is a tmpfs (read-only rootfs hardening): seed it from the baked
	// clean starter before the dev server boots, or require('./src') fails.
	ensureSrc()
	st.startDevServer()

	mux := http.NewServeMux()
	mux.HandleFunc("/claim", handleClaim)
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/ws/terminal", handleTerminal)

	log.Println("toolbox listening on :" + toolboxPort)
	log.Fatal(http.ListenAndServe(":"+toolboxPort, mux))
}

type claimReq struct {
	CandidateID  string `json:"candidate_id"`
	SessionID    string `json:"session_id"`
	SessionToken string `json:"session_token"`
	QuestionID   string `json:"question_id"`
	TimeLimitMin int    `json:"time_limit_minutes"`
}

func handleClaim(w http.ResponseWriter, r *http.Request) {
	var req claimReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	st.mu.Lock()
	defer st.mu.Unlock()

	// Reset source to clean starter code. /app/src is a tmpfs we cannot replace,
	// so clear its contents in place rather than rm -rf the mountpoint itself.
	if err := exec.Command("sh", "-c", "rm -rf /app/src/* /app/src/.[!.]* 2>/dev/null; cp -r /template-src/. /app/src/").Run(); err != nil {
		http.Error(w, "reset src: "+err.Error(), http.StatusInternalServerError)
		return
	}
	// Session context lives on tmpfs (/tmp) since the rootfs is read-only.
	_ = os.WriteFile("/tmp/.session", []byte(req.SessionID), 0o644)
	_ = os.WriteFile("/tmp/.token", []byte(req.SessionToken), 0o644)

	st.mode = "active"
	st.sessionID = req.SessionID

	// Restart dev server if it died, so the candidate gets a live server.
	if st.dev == nil || (st.dev.ProcessState != nil && st.dev.ProcessState.Exited()) {
		st.startDevServerLocked()
	}
	w.WriteHeader(http.StatusOK)
}

// handleHealth reports 200 only when the dev server port is actually accepting
// connections — "warm" must mean "claim-ready", not just "process alive".
func handleHealth(w http.ResponseWriter, r *http.Request) {
	if !devServerUp() {
		http.Error(w, "dev server not ready", http.StatusServiceUnavailable)
		return
	}
	st.mu.Lock()
	mode := st.mode
	st.mu.Unlock()
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "mode": mode})
}

func devServerUp() bool {
	conn, err := net.DialTimeout("tcp", "127.0.0.1:"+appPort, 500*time.Millisecond)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}

// ensureSrc seeds /app/src from the baked /template-src when it is empty (the
// tmpfs case on a read-only rootfs). Idempotent.
func ensureSrc() {
	entries, err := os.ReadDir("/app/src")
	if err == nil && len(entries) > 0 {
		return
	}
	if err := exec.Command("sh", "-c", "cp -r /template-src/. /app/src/").Run(); err != nil {
		log.Printf("seed /app/src failed: %v", err)
	}
}

func (s *state) startDevServer() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.startDevServerLocked()
}

func (s *state) startDevServerLocked() {
	// DEV_CMD is set per template (e.g. "node server.js", "python server.py").
	devCmd := os.Getenv("DEV_CMD")
	if devCmd == "" {
		devCmd = "node server.js"
	}
	cmd := exec.Command("sh", "-c", devCmd)
	cmd.Dir = "/app"
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		log.Printf("dev server failed to start: %v", err)
		return
	}
	s.dev = cmd
	go func() {
		_ = cmd.Wait()
		log.Printf("dev server exited")
	}()
}

// handleTerminal is a WebSocket server backing the candidate IDE terminal. It
// runs an interactive shell in /app/src (the candidate work dir) over a PTY.
// Protocol: binary frames are raw terminal I/O; text frames are JSON control
// messages ({"type":"resize","cols":N,"rows":M}). The orchestrator proxies this
// WS transparently to the browser, so the same protocol is end-to-end.
func handleTerminal(w http.ResponseWriter, r *http.Request) {
	c, err := websocket.Accept(w, r, nil)
	if err != nil {
		return
	}
	defer c.CloseNow()
	c.SetReadLimit(1 << 20)

	cmd := exec.Command("/bin/sh")
	cmd.Dir = "/app/src"
	cmd.Env = append(os.Environ(), "TERM=xterm-256color", "PS1=$ ")
	ptmx, err := pty.Start(cmd)
	if err != nil {
		_ = c.Close(websocket.StatusInternalError, "pty start")
		return
	}
	defer func() { _ = ptmx.Close(); _ = cmd.Process.Kill() }()

	ctx, cancel := context.WithCancel(r.Context())
	defer cancel()

	// PTY output -> browser.
	go func() {
		buf := make([]byte, 4096)
		for {
			n, err := ptmx.Read(buf)
			if n > 0 {
				if werr := c.Write(ctx, websocket.MessageBinary, buf[:n]); werr != nil {
					cancel()
					return
				}
			}
			if err != nil {
				cancel()
				return
			}
		}
	}()

	// Browser -> PTY (keystrokes) and control (resize).
	for {
		typ, data, err := c.Read(ctx)
		if err != nil {
			return
		}
		switch typ {
		case websocket.MessageBinary:
			if _, err := ptmx.Write(data); err != nil {
				return
			}
		case websocket.MessageText:
			var ctrl struct {
				Type string `json:"type"`
				Cols uint16 `json:"cols"`
				Rows uint16 `json:"rows"`
			}
			if json.Unmarshal(data, &ctrl) == nil && ctrl.Type == "resize" {
				_ = pty.Setsize(ptmx, &pty.Winsize{Cols: ctrl.Cols, Rows: ctrl.Rows})
			}
		}
	}
}
