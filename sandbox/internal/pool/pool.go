// Package pool manages the warm pool of sandbox containers entirely in-process:
// no Redis, no SQS. State is a mutex-guarded map. This is sufficient for a
// single-node v1 and keeps the whole claim path synchronous and debuggable.
package pool

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"

	dk "github.com/guvi-geek/flash/internal/docker"
)

// QuestionConfig is the per-template pool + image configuration.
type QuestionConfig struct {
	Image       string
	MinWarm     int
	AppPort     int
	ToolboxPort int
	MemoryMB    int64
	CPUQuota    int64
	PidsLimit   int64
	TimeLimit   time.Duration
	Runtime     string   // "" = runc, "runsc" = gVisor
	DevCmd      string   // dev server command, e.g. "node server.js"
	ExtraEnv    []string // extra container env, e.g. "HMR_CLIENT_PORT=8090"
}

type containerMeta struct {
	id          string
	questionID  string
	hostApp     int
	hostToolbox int
}

type Manager struct {
	log     *slog.Logger
	docker  *dk.Client
	network string
	host    string // host the toolbox/app ports are reachable on (127.0.0.1)

	cfg  map[string]QuestionConfig
	node string // owning node-agent id, stamped on every container ("" for the local orchestrator)

	mu        sync.Mutex
	warm      map[string][]*containerMeta // questionID -> idle containers
	active    map[string]*containerMeta   // containerID -> meta
	usedPorts map[int]bool
	nextPort  int
	portLo    int
	portHi    int
}

func New(log *slog.Logger, d *dk.Client, network string, cfg map[string]QuestionConfig) *Manager {
	return &Manager{
		log:       log,
		docker:    d,
		network:   network,
		host:      "127.0.0.1",
		cfg:       cfg,
		warm:      map[string][]*containerMeta{},
		active:    map[string]*containerMeta{},
		usedPorts: map[int]bool{},
		nextPort:  20000,
		portLo:    20000,
		portHi:    39000,
	}
}

// SetPortRange constrains host-port allocation to [lo, hi). Multiple node-agents on
// one physical host must use disjoint ranges so their sandbox port bindings never
// collide. No-op for an invalid range.
func (m *Manager) SetPortRange(lo, hi int) {
	if lo <= 0 || hi <= lo {
		return
	}
	m.mu.Lock()
	m.portLo, m.portHi, m.nextPort = lo, hi, lo
	m.mu.Unlock()
}

// SetNode stamps an owning node-agent id on every container this pool creates, so
// agents sharing a Docker daemon (the local sim) only manage their own.
func (m *Manager) SetNode(id string) {
	m.mu.Lock()
	m.node = id
	m.mu.Unlock()
}

// ReservedMB sums the CONFIGURED memory of every live (warm + active) container —
// the reservation a node advertises as "used" so the scheduler bin-packs against
// committed capacity, not optimistic measured RSS.
func (m *Manager) ReservedMB() int64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	var total int64
	for q, list := range m.warm {
		total += int64(len(list)) * m.cfg[q].MemoryMB
	}
	for _, cm := range m.active {
		total += m.cfg[cm.questionID].MemoryMB
	}
	return total
}

// ClaimResult is what a successful claim returns to the API layer.
type ClaimResult struct {
	ContainerID string
	HostApp     int
	HostToolbox int
	Cold        bool // true if the warm pool was empty and we spun on the claim path
}

var ErrUnknownQuestion = errors.New("unknown question template")

// Register adds (or replaces) a template's pool config at runtime, so the
// dashboard can publish a new template without a restart. Guarded by the same
// mutex that protects the warm/active maps, so config reads on the claim path
// never race a registration.
func (m *Manager) Register(questionID string, cfg QuestionConfig) {
	m.mu.Lock()
	m.cfg[questionID] = cfg
	m.mu.Unlock()
}

// config returns a template's pool config under lock.
func (m *Manager) config(questionID string) (QuestionConfig, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	cfg, ok := m.cfg[questionID]
	return cfg, ok
}

// SetMinWarm changes a template's target warm depth at runtime. This is the seam
// scheduled scaling writes to: raise it ahead of a booked assessment window, lower
// it after. Returns false for an unknown template. Replenishing up to the new floor
// is the caller's job (call Replenish after raising).
func (m *Manager) SetMinWarm(questionID string, n int) bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	cfg, ok := m.cfg[questionID]
	if !ok {
		return false
	}
	cfg.MinWarm = n
	m.cfg[questionID] = cfg
	return true
}

// AdoptActive re-registers a still-running container that an ACTIVE session points
// at, after an orchestrator restart. The container kept running across the restart
// (its candidate never lost the dev server or their tmpfs work); this rebuilds the
// in-process binding so preview/terminal/submit resolve its host ports again. Port
// reservations are restored so the allocator never hands these ports out twice.
func (m *Manager) AdoptActive(questionID, containerID string, hostApp, hostToolbox int) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.usedPorts[hostApp] = true
	m.usedPorts[hostToolbox] = true
	m.active[containerID] = &containerMeta{
		id: containerID, questionID: questionID, hostApp: hostApp, hostToolbox: hostToolbox,
	}
}

// AdoptWarm re-registers a surviving warm container after a restart, but only if it
// still passes its health check — a half-booted or wedged warm container is reaped
// by the caller instead. Returns true if adopted.
func (m *Manager) AdoptWarm(questionID, containerID string, hostApp, hostToolbox int) bool {
	cm := &containerMeta{id: containerID, questionID: questionID, hostApp: hostApp, hostToolbox: hostToolbox}
	if !m.healthy(cm, 2*time.Second) {
		return false
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.usedPorts[hostApp] = true
	m.usedPorts[hostToolbox] = true
	m.warm[questionID] = append(m.warm[questionID], cm)
	return true
}

// Claim hands a candidate a warm container, or spins one on the cold path.
func (m *Manager) Claim(ctx context.Context, questionID, candidateID, sessionID, token string) (*ClaimResult, error) {
	cfg, ok := m.config(questionID)
	if !ok {
		return nil, ErrUnknownQuestion
	}

	cm := m.popWarm(questionID)
	coldPath := false
	if cm == nil {
		coldPath = true
		m.log.Warn("pool empty, cold path", "question", questionID)
		var err error
		cm, err = m.spinOne(ctx, questionID, cfg)
		if err != nil {
			return nil, fmt.Errorf("cold spin: %w", err)
		}
	}

	// Verify health before handing it over.
	if !m.healthy(cm, 2*time.Second) {
		m.log.Warn("claimed container unhealthy, destroying", "id", short(cm.id))
		m.destroy(cm)
		// One retry on a fresh container.
		fresh, err := m.spinOne(ctx, questionID, cfg)
		if err != nil {
			return nil, fmt.Errorf("retry spin: %w", err)
		}
		cm = fresh
	}

	if err := m.injectCandidate(ctx, cm, candidateID, questionID, sessionID, token, cfg.TimeLimit); err != nil {
		// Injection failure is not the container's fault — return it to the pool.
		m.pushWarm(questionID, cm)
		return nil, fmt.Errorf("inject candidate: %w", err)
	}

	m.mu.Lock()
	m.active[cm.id] = cm
	m.mu.Unlock()

	m.log.Info("container.claimed", "session", sessionID, "container", short(cm.id),
		"question", questionID, "warm_path", !coldPath)

	go m.Replenish(context.Background(), questionID)

	return &ClaimResult{ContainerID: cm.id, HostApp: cm.hostApp, HostToolbox: cm.hostToolbox, Cold: coldPath}, nil
}

// Release destroys an active container (on submit/destroy/timeout) and frees ports.
func (m *Manager) Release(containerID string) {
	m.mu.Lock()
	cm := m.active[containerID]
	delete(m.active, containerID)
	m.mu.Unlock()
	if cm == nil {
		cm = &containerMeta{id: containerID}
	}
	m.destroy(cm)
}

// ToolboxPort returns the host port of an active container's toolbox, used by
// the orchestrator to proxy the terminal WebSocket. Only valid while active.
func (m *Manager) ToolboxPort(containerID string) (int, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	cm := m.active[containerID]
	if cm == nil {
		return 0, false
	}
	return cm.hostToolbox, true
}

// HostAddr renders host:port for the address the orchestrator reaches sandbox
// published ports on (127.0.0.1 in v1).
func (m *Manager) HostAddr(port int) string {
	return net.JoinHostPort(m.host, fmt.Sprintf("%d", port))
}

// AppPort returns the host port mapped to an active container's dev server,
// used by the preview reverse proxy. Only valid while the session is active.
func (m *Manager) AppPort(containerID string) (int, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	cm := m.active[containerID]
	if cm == nil {
		return 0, false
	}
	return cm.hostApp, true
}

// Snapshot tars /app/src out of an active container for scoring. Uses exec-tar
// because /app/src is a tmpfs mount that docker cp cannot see.
func (m *Manager) Snapshot(ctx context.Context, containerID string) ([]byte, error) {
	return m.docker.SnapshotDir(ctx, containerID, "/app", "src")
}

// Replenish tops the warm pool back up to MinWarm, capped per burst.
func (m *Manager) Replenish(ctx context.Context, questionID string) {
	cfg, ok := m.config(questionID)
	if !ok {
		return
	}
	m.mu.Lock()
	deficit := cfg.MinWarm - len(m.warm[questionID])
	m.mu.Unlock()
	if deficit <= 0 {
		return
	}
	if deficit > 3 {
		deficit = 3 // cap burst so we don't hammer the daemon
	}
	var wg sync.WaitGroup
	for i := 0; i < deficit; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			cm, err := m.spinOne(ctx, questionID, cfg)
			if err != nil {
				m.log.Error("replenish spin failed", "question", questionID, "err", err)
				return
			}
			m.pushWarm(questionID, cm)
		}()
	}
	wg.Wait()
}

// HealthSweep evicts warm containers that fail their health check.
func (m *Manager) HealthSweep(ctx context.Context) {
	m.mu.Lock()
	var checks []*containerMeta
	var qs []string
	for q, list := range m.warm {
		for _, cm := range list {
			checks = append(checks, cm)
			qs = append(qs, q)
		}
	}
	m.mu.Unlock()

	for i, cm := range checks {
		if !m.healthy(cm, 3*time.Second) {
			m.log.Warn("evicting unhealthy warm container", "id", short(cm.id))
			m.removeFromWarm(qs[i], cm.id)
			m.destroy(cm)
			go m.Replenish(ctx, qs[i])
		}
	}
}

// WarmCount reports current warm depth per question (for /stats).
func (m *Manager) WarmCount() map[string]int {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := map[string]int{}
	for q, l := range m.warm {
		out[q] = len(l)
	}
	return out
}

// ActiveCount reports the number of claimed (live) sandboxes per question.
func (m *Manager) ActiveCount() map[string]int {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := map[string]int{}
	for _, cm := range m.active {
		out[cm.questionID]++
	}
	return out
}

// LiveContainerIDs returns the ids of every warm and active container, for the
// density sampler to read real per-container memory.
func (m *Manager) LiveContainerIDs() []string {
	m.mu.Lock()
	defer m.mu.Unlock()
	ids := make([]string, 0, len(m.active))
	for id := range m.active {
		ids = append(ids, id)
	}
	for _, list := range m.warm {
		for _, cm := range list {
			ids = append(ids, cm.id)
		}
	}
	return ids
}

// --- internals ---

func (m *Manager) spinOne(ctx context.Context, questionID string, cfg QuestionConfig) (*containerMeta, error) {
	hostApp := m.allocPort()
	hostTB := m.allocPort()

	env := append([]string{"MODE=warm", "QUESTION_ID=" + questionID, "DEV_CMD=" + cfg.DevCmd}, cfg.ExtraEnv...)
	id, err := m.docker.CreateSandbox(ctx, dk.SandboxSpec{
		Image:       cfg.Image,
		Question:    questionID,
		Node:        m.node,
		Network:     m.network,
		Env:         env,
		AppPort:     cfg.AppPort,
		ToolboxPort: cfg.ToolboxPort,
		HostApp:     hostApp,
		HostToolbox: hostTB,
		MemoryMB:    cfg.MemoryMB,
		CPUQuota:    cfg.CPUQuota,
		PidsLimit:   cfg.PidsLimit,
		Runtime:     cfg.Runtime,
	})
	if err != nil {
		m.freePort(hostApp)
		m.freePort(hostTB)
		return nil, err
	}

	cm := &containerMeta{id: id, questionID: questionID, hostApp: hostApp, hostToolbox: hostTB}

	if err := m.waitHealthy(cm, 30*time.Second); err != nil {
		m.destroy(cm)
		return nil, fmt.Errorf("never became healthy: %w", err)
	}
	return cm, nil
}

func (m *Manager) waitHealthy(cm *containerMeta, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if m.healthy(cm, 1*time.Second) {
			return nil
		}
		time.Sleep(300 * time.Millisecond)
	}
	return errors.New("health timeout")
}

// healthy returns true only when the toolbox reports the dev server is ready.
func (m *Manager) healthy(cm *containerMeta, timeout time.Duration) bool {
	url := fmt.Sprintf("http://%s:%d/health", m.host, cm.hostToolbox)
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func (m *Manager) injectCandidate(ctx context.Context, cm *containerMeta, candidateID, questionID, sessionID, token string, ttl time.Duration) error {
	url := fmt.Sprintf("http://%s:%d/claim", m.host, cm.hostToolbox)
	body := fmt.Sprintf(`{"candidate_id":%q,"session_id":%q,"session_token":%q,"question_id":%q,"time_limit_minutes":%d}`,
		candidateID, sessionID, token, questionID, int(ttl.Minutes()))
	reqCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(reqCtx, http.MethodPost, url, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("toolbox /claim returned %d", resp.StatusCode)
	}
	return nil
}

func (m *Manager) destroy(cm *containerMeta) {
	_ = m.docker.Remove(context.Background(), cm.id)
	if cm.hostApp != 0 {
		m.freePort(cm.hostApp)
	}
	if cm.hostToolbox != 0 {
		m.freePort(cm.hostToolbox)
	}
}

func (m *Manager) popWarm(q string) *containerMeta {
	m.mu.Lock()
	defer m.mu.Unlock()
	list := m.warm[q]
	if len(list) == 0 {
		return nil
	}
	cm := list[len(list)-1]
	m.warm[q] = list[:len(list)-1]
	return cm
}

func (m *Manager) pushWarm(q string, cm *containerMeta) {
	m.mu.Lock()
	m.warm[q] = append(m.warm[q], cm)
	m.mu.Unlock()
}

func (m *Manager) removeFromWarm(q, id string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	list := m.warm[q]
	for i, cm := range list {
		if cm.id == id {
			m.warm[q] = append(list[:i], list[i+1:]...)
			return
		}
	}
}

// allocPort returns a free host port, probing the OS to avoid collisions.
func (m *Manager) allocPort() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	for {
		p := m.nextPort
		m.nextPort++
		if m.nextPort >= m.portHi {
			m.nextPort = m.portLo
		}
		if m.usedPorts[p] {
			continue
		}
		ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", p))
		if err != nil {
			continue // in use by something else
		}
		ln.Close()
		m.usedPorts[p] = true
		return p
	}
}

func (m *Manager) freePort(p int) {
	m.mu.Lock()
	delete(m.usedPorts, p)
	m.mu.Unlock()
}

func short(id string) string {
	if len(id) > 12 {
		return id[:12]
	}
	return id
}

// NewID returns a short random hex id with a prefix.
func NewID(prefix string) string {
	b := make([]byte, 9)
	_, _ = rand.Read(b)
	return prefix + "_" + hex.EncodeToString(b)
}
