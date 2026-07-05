// Package store persists sessions and submissions in Postgres.
package store

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Store struct {
	pool *pgxpool.Pool
}

const schema = `
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    candidate_id  TEXT NOT NULL,
    question_id   TEXT NOT NULL,
    assessment_id TEXT NOT NULL DEFAULT '',
    container_id  TEXT,
    host_port     INT,
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    session_token TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ NOT NULL,
    submitted_at  TIMESTAMPTZ,
    destroyed_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS sessions_status_expiry ON sessions (status, expires_at);

CREATE TABLE IF NOT EXISTS submissions (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id),
    question_id  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'scoring',
    score        INT,
    max_score    INT,
    results_json JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scored_at    TIMESTAMPTZ
);

-- Auth: an org owns API keys and has a concurrency cap (also a cost guardrail).
-- API keys are high-entropy random tokens, so we store a SHA-256 of the raw key
-- (fast hash is correct for 256-bit secrets; bcrypt is for low-entropy passwords).
CREATE TABLE IF NOT EXISTS orgs (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    concurrency_limit INT  NOT NULL DEFAULT 20,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS api_keys (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES orgs(id),
    name         TEXT NOT NULL DEFAULT '',
    key_hash     TEXT NOT NULL UNIQUE,
    prefix       TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);
-- Sessions are owned by an org, so the concurrency cap can be counted per-org.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS sessions_org_active ON sessions (org_id, status);

-- Multi-node routing: which node-agent owns the sandbox, how to reach it, and the
-- host:port the preview/terminal proxies target. Durable so a control-plane restart
-- (and the preview/terminal proxies) can still route to the owning node.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS node_id      TEXT NOT NULL DEFAULT '';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS node_addr    TEXT NOT NULL DEFAULT '';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS node_host    TEXT NOT NULL DEFAULT '127.0.0.1';
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS host_toolbox INT  NOT NULL DEFAULT 0;

-- Scheduled scaling: a booked assessment window pre-warms a template ahead of T.
-- The planner sums the seats of every window currently inside its pre-warm span
-- ([starts_at - lead_minutes, ends_at)) per question and raises that template's
-- warm floor to cover the arrival burst, then restores the baseline after. The
-- table is the durable source of truth, so the planner is stateless and a
-- control-plane restart resumes the schedule with no in-memory state to rebuild.
CREATE TABLE IF NOT EXISTS assessment_windows (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL DEFAULT '',
    question_id  TEXT NOT NULL,
    label        TEXT NOT NULL DEFAULT '',
    seats        INT  NOT NULL,
    lead_minutes INT  NOT NULL DEFAULT 5,
    starts_at    TIMESTAMPTZ NOT NULL,
    ends_at      TIMESTAMPTZ NOT NULL,
    canceled_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS aw_span ON assessment_windows (question_id, starts_at, ends_at);

-- SDK sandboxes: arbitrary user metadata attached at create time, filterable
-- on list. Sessions created by the assessment plane leave it empty.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';
`

func New(ctx context.Context, dsn string) (*Store, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, fmt.Errorf("pg connect: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("pg ping: %w", err)
	}
	if _, err := pool.Exec(ctx, schema); err != nil {
		return nil, fmt.Errorf("migrate: %w", err)
	}
	return &Store{pool: pool}, nil
}

func (s *Store) Close() { s.pool.Close() }

type Session struct {
	ID, CandidateID, QuestionID, AssessmentID string
	OrgID                                     string
	ContainerID, SessionToken                 string
	HostPort                                  int // host port of the dev server (app)
	NodeID, NodeAddr, NodeHost                string
	HostToolbox                               int
	Status                                    string
	Metadata                                  []byte // raw JSON object (SDK sandboxes)
	CreatedAt                                 time.Time
	ExpiresAt                                 time.Time
}

func (s *Store) CreateSession(ctx context.Context, ss Session) error {
	meta := ss.Metadata
	if len(meta) == 0 {
		meta = []byte("{}")
	}
	_, err := s.pool.Exec(ctx,
		`INSERT INTO sessions (id, candidate_id, question_id, assessment_id, org_id, container_id, host_port,
		    node_id, node_addr, node_host, host_toolbox, status, session_token, expires_at, metadata)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)`,
		ss.ID, ss.CandidateID, ss.QuestionID, ss.AssessmentID, ss.OrgID, ss.ContainerID, ss.HostPort,
		ss.NodeID, ss.NodeAddr, ss.NodeHost, ss.HostToolbox, ss.Status, ss.SessionToken, ss.ExpiresAt, meta)
	return err
}

const sessionCols = `id, candidate_id, question_id, assessment_id, COALESCE(org_id,''), COALESCE(container_id,''),
	COALESCE(host_port,0), COALESCE(node_id,''), COALESCE(node_addr,''), COALESCE(node_host,'127.0.0.1'),
	COALESCE(host_toolbox,0), status, session_token, created_at, expires_at, COALESCE(metadata,'{}'::jsonb)`

func scanSession(row interface {
	Scan(dest ...any) error
}) (Session, error) {
	var ss Session
	err := row.Scan(&ss.ID, &ss.CandidateID, &ss.QuestionID, &ss.AssessmentID, &ss.OrgID, &ss.ContainerID,
		&ss.HostPort, &ss.NodeID, &ss.NodeAddr, &ss.NodeHost, &ss.HostToolbox, &ss.Status, &ss.SessionToken,
		&ss.CreatedAt, &ss.ExpiresAt, &ss.Metadata)
	return ss, err
}

// ExtendSession moves an ACTIVE session's expiry (the SDK's set-timeout). Returns
// false if the session isn't ACTIVE (nothing to extend).
func (s *Store) ExtendSession(ctx context.Context, id string, expires time.Time) (bool, error) {
	tag, err := s.pool.Exec(ctx,
		`UPDATE sessions SET expires_at=$2 WHERE id=$1 AND status='ACTIVE'`, id, expires)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() > 0, nil
}

// SessionsByOrg lists an org's sessions newest-first, optionally filtered by
// status (e.g. "ACTIVE" for the SDK's running-sandbox list).
func (s *Store) SessionsByOrg(ctx context.Context, orgID, status string, limit int) ([]Session, error) {
	q := `SELECT ` + sessionCols + ` FROM sessions WHERE org_id=$1`
	args := []any{orgID}
	if status != "" {
		q += ` AND status=$2`
		args = append(args, status)
	}
	q += fmt.Sprintf(` ORDER BY created_at DESC LIMIT %d`, limit)
	rows, err := s.pool.Query(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Session
	for rows.Next() {
		ss, err := scanSession(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, ss)
	}
	return out, rows.Err()
}

func (s *Store) GetSession(ctx context.Context, id string) (*Session, error) {
	ss, err := scanSession(s.pool.QueryRow(ctx, `SELECT `+sessionCols+` FROM sessions WHERE id=$1`, id))
	if err != nil {
		return nil, err
	}
	return &ss, nil
}

func (s *Store) SetStatus(ctx context.Context, id, status string) error {
	_, err := s.pool.Exec(ctx, `UPDATE sessions SET status=$2 WHERE id=$1`, id, status)
	return err
}

func (s *Store) MarkSubmitted(ctx context.Context, id string) error {
	_, err := s.pool.Exec(ctx, `UPDATE sessions SET status='SUBMITTED', submitted_at=NOW() WHERE id=$1`, id)
	return err
}

func (s *Store) MarkDestroyed(ctx context.Context, id string) error {
	_, err := s.pool.Exec(ctx, `UPDATE sessions SET status='DESTROYED', destroyed_at=NOW() WHERE id=$1`, id)
	return err
}

// ActiveSessions returns every session still marked ACTIVE, with the fields
// reconcile needs to re-adopt its container after an orchestrator restart. This is
// the durable half of the truth (Docker is the other half): Postgres says which
// sessions are live and which container each holds.
func (s *Store) ActiveSessions(ctx context.Context) ([]Session, error) {
	rows, err := s.pool.Query(ctx, `SELECT `+sessionCols+` FROM sessions WHERE status='ACTIVE'`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Session
	for rows.Next() {
		ss, err := scanSession(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, ss)
	}
	return out, rows.Err()
}

// ExpiredActive returns IDs of ACTIVE sessions past their expiry.
func (s *Store) ExpiredActive(ctx context.Context) ([]string, error) {
	rows, err := s.pool.Query(ctx, `SELECT id FROM sessions WHERE status='ACTIVE' AND expires_at < NOW()`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

// SessionRow is a denormalized session view for the dashboard, with the latest
// submission's score joined in (if any).
type SessionRow struct {
	ID           string     `json:"id"`
	CandidateID  string     `json:"candidate_id"`
	QuestionID   string     `json:"question_id"`
	Status       string     `json:"status"`
	CreatedAt    time.Time  `json:"created_at"`
	ExpiresAt    time.Time  `json:"expires_at"`
	SubmittedAt  *time.Time `json:"submitted_at,omitempty"`
	Score        *int       `json:"score,omitempty"`
	MaxScore     *int       `json:"max_score,omitempty"`
	SubmitStatus *string    `json:"submission_status,omitempty"`
}

func (s *Store) ListSessions(ctx context.Context, limit int) ([]SessionRow, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT s.id, s.candidate_id, s.question_id, s.status, s.created_at, s.expires_at, s.submitted_at,
		       sub.score, sub.max_score, sub.status
		FROM sessions s
		LEFT JOIN LATERAL (
		    SELECT score, max_score, status FROM submissions
		    WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1
		) sub ON true
		ORDER BY s.created_at DESC
		LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []SessionRow
	for rows.Next() {
		var r SessionRow
		if err := rows.Scan(&r.ID, &r.CandidateID, &r.QuestionID, &r.Status, &r.CreatedAt, &r.ExpiresAt,
			&r.SubmittedAt, &r.Score, &r.MaxScore, &r.SubmitStatus); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// QuestionUsage is billed sandbox time for one template. SandboxSeconds sums each
// session's live duration (created_at → destroyed_at, or now for still-active ones)
// — the "sold" hours you compare against a managed-provider invoice.
type QuestionUsage struct {
	QuestionID     string  `json:"question_id"`
	Sessions       int     `json:"sessions"`
	ActiveNow      int     `json:"active_now"`
	SandboxSeconds float64 `json:"sandbox_seconds"`
}

// UsageSummary aggregates billed sandbox time from the sessions ledger. The
// sessions table already records each sandbox's lifetime (created_at → destroyed_at),
// so it IS the usage ledger — no separate events table needed at one node.
func (s *Store) UsageSummary(ctx context.Context) ([]QuestionUsage, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT question_id,
		       COUNT(*) AS sessions,
		       COUNT(*) FILTER (WHERE status='ACTIVE') AS active_now,
		       COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(destroyed_at, NOW()) - created_at))), 0) AS sandbox_seconds
		FROM sessions
		GROUP BY question_id
		ORDER BY question_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []QuestionUsage
	for rows.Next() {
		var u QuestionUsage
		if err := rows.Scan(&u.QuestionID, &u.Sessions, &u.ActiveNow, &u.SandboxSeconds); err != nil {
			return nil, err
		}
		out = append(out, u)
	}
	return out, rows.Err()
}

func (s *Store) CreateSubmission(ctx context.Context, id, sessionID, questionID string) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO submissions (id, session_id, question_id, status) VALUES ($1,$2,$3,'scoring')`,
		id, sessionID, questionID)
	return err
}

// LatestSubmission returns the most recent submission for a session (for the
// candidate playground's score panel). ok=false if none yet.
func (s *Store) LatestSubmission(ctx context.Context, sessionID string) (status string, score, maxScore int, ok bool, err error) {
	var sc, mx *int
	err = s.pool.QueryRow(ctx,
		`SELECT status, score, max_score FROM submissions
		 WHERE session_id=$1 ORDER BY created_at DESC LIMIT 1`, sessionID).
		Scan(&status, &sc, &mx)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", 0, 0, false, nil
	}
	if err != nil {
		return "", 0, 0, false, err
	}
	if sc != nil {
		score = *sc
	}
	if mx != nil {
		maxScore = *mx
	}
	return status, score, maxScore, true, nil
}

func (s *Store) WriteScore(ctx context.Context, subID, status string, score, maxScore int, resultsJSON []byte) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE submissions SET status=$2, score=$3, max_score=$4, results_json=$5, scored_at=NOW() WHERE id=$1`,
		subID, status, score, maxScore, resultsJSON)
	return err
}

// --- auth: orgs + api keys ---

type Org struct {
	ID               string `json:"id"`
	Name             string `json:"name"`
	ConcurrencyLimit int    `json:"concurrency_limit"`
}

// EnsureOrg idempotently creates (or leaves) an org. Used to bootstrap a default
// org on first boot.
func (s *Store) EnsureOrg(ctx context.Context, id, name string, concurrency int) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO orgs (id, name, concurrency_limit) VALUES ($1,$2,$3)
		 ON CONFLICT (id) DO UPDATE SET concurrency_limit = EXCLUDED.concurrency_limit`,
		id, name, concurrency)
	return err
}

// UpsertAPIKey idempotently registers a key hash for an org (keyed on the hash, so
// re-supplying the same bootstrap key is a no-op).
func (s *Store) UpsertAPIKey(ctx context.Context, id, orgID, name, keyHash, prefix string) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO api_keys (id, org_id, name, key_hash, prefix) VALUES ($1,$2,$3,$4,$5)
		 ON CONFLICT (key_hash) DO NOTHING`, id, orgID, name, keyHash, prefix)
	return err
}

// CountAPIKeys reports how many live (non-revoked) keys exist, so boot can decide
// whether to mint a first one.
func (s *Store) CountAPIKeys(ctx context.Context) (int, error) {
	var n int
	err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM api_keys WHERE revoked_at IS NULL`).Scan(&n)
	return n, err
}

// LookupAPIKey resolves a key hash to its org. Returns ok=false for an unknown or
// revoked key. Does not error on not-found (that's an auth failure, not a fault).
func (s *Store) LookupAPIKey(ctx context.Context, keyHash string) (Org, string, bool, error) {
	var o Org
	var keyID string
	err := s.pool.QueryRow(ctx,
		`SELECT k.id, o.id, o.name, o.concurrency_limit
		 FROM api_keys k JOIN orgs o ON o.id = k.org_id
		 WHERE k.key_hash=$1 AND k.revoked_at IS NULL`, keyHash).
		Scan(&keyID, &o.ID, &o.Name, &o.ConcurrencyLimit)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return Org{}, "", false, nil
		}
		return Org{}, "", false, err
	}
	return o, keyID, true, nil
}

// APIKey is the dashboard/SDK view of a key — never the hash, only the display
// prefix. The raw key is shown once at mint time and is unrecoverable after.
type APIKey struct {
	ID         string     `json:"id"`
	OrgID      string     `json:"org_id"`
	Name       string     `json:"name"`
	Prefix     string     `json:"prefix"`
	CreatedAt  time.Time  `json:"created_at"`
	LastUsedAt *time.Time `json:"last_used_at,omitempty"`
}

// ListAPIKeys returns an org's live (non-revoked) keys, newest first.
func (s *Store) ListAPIKeys(ctx context.Context, orgID string) ([]APIKey, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id, org_id, COALESCE(name,''), COALESCE(prefix,''), created_at, last_used_at
		 FROM api_keys WHERE org_id=$1 AND revoked_at IS NULL ORDER BY created_at DESC`, orgID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []APIKey
	for rows.Next() {
		var k APIKey
		if err := rows.Scan(&k.ID, &k.OrgID, &k.Name, &k.Prefix, &k.CreatedAt, &k.LastUsedAt); err != nil {
			return nil, err
		}
		out = append(out, k)
	}
	return out, rows.Err()
}

// RevokeAPIKey revokes a key (scoped to its owning org). Revoked keys stop
// authenticating immediately (LookupAPIKey filters them) but stay in the table
// as an audit record. Returns false if no live key matched.
func (s *Store) RevokeAPIKey(ctx context.Context, id, orgID string) (bool, error) {
	tag, err := s.pool.Exec(ctx,
		`UPDATE api_keys SET revoked_at=NOW() WHERE id=$1 AND org_id=$2 AND revoked_at IS NULL`, id, orgID)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() > 0, nil
}

// TouchAPIKey records last use (best-effort; callers ignore the error).
func (s *Store) TouchAPIKey(ctx context.Context, keyID string) error {
	_, err := s.pool.Exec(ctx, `UPDATE api_keys SET last_used_at=NOW() WHERE id=$1`, keyID)
	return err
}

// ActiveCountsByQuestion returns the live-sandbox count per template, for fleet
// metrics in cluster mode (the registry tracks per-node totals, not per-question).
func (s *Store) ActiveCountsByQuestion(ctx context.Context) (map[string]int, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT question_id, COUNT(*) FROM sessions WHERE status='ACTIVE' GROUP BY question_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]int{}
	for rows.Next() {
		var q string
		var n int
		if err := rows.Scan(&q, &n); err != nil {
			return nil, err
		}
		out[q] = n
	}
	return out, rows.Err()
}

// ActiveCountByOrg counts an org's live sandboxes, for the concurrency cap.
func (s *Store) ActiveCountByOrg(ctx context.Context, orgID string) (int, error) {
	var n int
	err := s.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM sessions WHERE org_id=$1 AND status='ACTIVE'`, orgID).Scan(&n)
	return n, err
}

// --- scheduled scaling: assessment windows ---

// Window is a booked pre-warm window for a template. Seats is the number of warm
// sandboxes to have ready during the window; LeadMinutes is how far ahead of
// StartsAt to begin warming. CanceledAt is set when an operator cancels it.
type Window struct {
	ID          string     `json:"id"`
	OrgID       string     `json:"org_id"`
	QuestionID  string     `json:"question_id"`
	Label       string     `json:"label"`
	Seats       int        `json:"seats"`
	LeadMinutes int        `json:"lead_minutes"`
	StartsAt    time.Time  `json:"starts_at"`
	EndsAt      time.Time  `json:"ends_at"`
	CanceledAt  *time.Time `json:"canceled_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`
}

func (s *Store) CreateWindow(ctx context.Context, w Window) error {
	_, err := s.pool.Exec(ctx,
		`INSERT INTO assessment_windows (id, org_id, question_id, label, seats, lead_minutes, starts_at, ends_at)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
		w.ID, w.OrgID, w.QuestionID, w.Label, w.Seats, w.LeadMinutes, w.StartsAt, w.EndsAt)
	return err
}

const windowCols = `id, COALESCE(org_id,''), question_id, COALESCE(label,''), seats, lead_minutes,
	starts_at, ends_at, canceled_at, created_at`

func scanWindow(row interface {
	Scan(dest ...any) error
}) (Window, error) {
	var w Window
	err := row.Scan(&w.ID, &w.OrgID, &w.QuestionID, &w.Label, &w.Seats, &w.LeadMinutes,
		&w.StartsAt, &w.EndsAt, &w.CanceledAt, &w.CreatedAt)
	return w, err
}

// ListWindows returns windows ordered by start time. When includeEnded is false,
// canceled and already-finished windows are omitted (the operator's live view).
func (s *Store) ListWindows(ctx context.Context, includeEnded bool) ([]Window, error) {
	q := `SELECT ` + windowCols + ` FROM assessment_windows`
	if !includeEnded {
		q += ` WHERE canceled_at IS NULL AND ends_at > NOW()`
	}
	q += ` ORDER BY starts_at ASC`
	rows, err := s.pool.Query(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Window
	for rows.Next() {
		w, err := scanWindow(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, w)
	}
	return out, rows.Err()
}

// CancelWindow marks a window canceled (scoped to its owning org). Returns false
// if no matching live window existed.
func (s *Store) CancelWindow(ctx context.Context, id, orgID string) (bool, error) {
	tag, err := s.pool.Exec(ctx,
		`UPDATE assessment_windows SET canceled_at=NOW()
		 WHERE id=$1 AND org_id=$2 AND canceled_at IS NULL`, id, orgID)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() > 0, nil
}

// DesiredWarmByQuestion is the planner's core query: for every question with a
// window currently inside its pre-warm span ([starts_at - lead, ends_at)), sum the
// seats. That sum is the warm floor the planner wants for that template right now.
func (s *Store) DesiredWarmByQuestion(ctx context.Context) (map[string]int, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT question_id, COALESCE(SUM(seats),0)
		FROM assessment_windows
		WHERE canceled_at IS NULL
		  AND NOW() >= starts_at - make_interval(mins => lead_minutes)
		  AND NOW() < ends_at
		GROUP BY question_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]int{}
	for rows.Next() {
		var q string
		var n int
		if err := rows.Scan(&q, &n); err != nil {
			return nil, err
		}
		out[q] = n
	}
	return out, rows.Err()
}
