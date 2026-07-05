package flash

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"time"
)

// AssessmentService is the assessment layer on top of raw sandboxes:
// claim a session for a candidate, hand them the playground/preview, then
// submit → snapshot → automated scoring. Everything a raw Sandbox can't do.
type AssessmentService struct{ c *Client }

// Session is a candidate's assessment sandbox.
type Session struct {
	ID          string    `json:"session_id"`
	Token       string    `json:"session_token"`
	CandidateID string    `json:"candidate_id"`
	QuestionID  string    `json:"question_id"`
	Status      string    `json:"status"`
	AppURL      string    `json:"app_url"`
	PreviewURL  string    `json:"preview_url"`
	TerminalURL string    `json:"terminal_url"`
	ExpiresAt   time.Time `json:"expires_at"`

	c *Client
}

// CreateSessionOpts configures a candidate session claim.
type CreateSessionOpts struct {
	CandidateID  string // required — who is being assessed
	QuestionID   string // required — the template/question id
	AssessmentID string
	TimeLimit    time.Duration // zero = template default
}

// CreateSession claims a sandbox for a candidate. Hand Session.Token to the
// candidate (it scopes them to this one session); keep your org key private.
func (s *AssessmentService) CreateSession(ctx context.Context, opts CreateSessionOpts) (*Session, error) {
	if opts.CandidateID == "" || opts.QuestionID == "" {
		return nil, fmt.Errorf("flash: CandidateID and QuestionID required")
	}
	req := map[string]any{"candidate_id": opts.CandidateID, "question_id": opts.QuestionID}
	if opts.AssessmentID != "" {
		req["assessment_id"] = opts.AssessmentID
	}
	if opts.TimeLimit > 0 {
		req["time_limit_minutes"] = int(opts.TimeLimit / time.Minute)
	}
	var sess Session
	if err := s.c.do(ctx, http.MethodPost, "/v1/sessions", req, &sess); err != nil {
		return nil, err
	}
	sess.c = s.c
	return &sess, nil
}

// GetSession fetches a session by id (operator view, includes the token).
func (s *AssessmentService) GetSession(ctx context.Context, id string) (*Session, error) {
	var sess Session
	if err := s.c.do(ctx, http.MethodGet, "/v1/sessions/"+url.PathEscape(id), nil, &sess); err != nil {
		return nil, err
	}
	sess.c = s.c
	return &sess, nil
}

// Destroy tears the session down without scoring.
func (s *AssessmentService) Destroy(ctx context.Context, id string) error {
	return s.c.do(ctx, http.MethodDelete, "/v1/sessions/"+url.PathEscape(id), nil, nil)
}

// Submission is a scored (or in-flight) submission.
type Submission struct {
	SubmissionID string `json:"submission_id"`
	Status       string `json:"status"` // "scoring" | "scored" | "error" | …
	Score        int    `json:"score"`
	MaxScore     int    `json:"max_score"`
}

// Submit snapshots the candidate's work, destroys the sandbox, and starts
// scoring. Authenticated by the session token (candidate credential).
func (sess *Session) Submit(ctx context.Context) (*Submission, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		sess.c.baseURL+"/v1/sessions/"+url.PathEscape(sess.ID)+"/submit", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+sess.Token)
	resp, err := sess.c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("flash: submit: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, &APIError{StatusCode: resp.StatusCode, Message: "submit failed"}
	}
	var out Submission
	if err := decodeJSON(resp.Body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Result returns the latest submission's score. ok=false while nothing has
// been submitted yet.
func (sess *Session) Result(ctx context.Context) (*Submission, bool, error) {
	var out struct {
		Submitted bool   `json:"submitted"`
		Status    string `json:"status"`
		Score     int    `json:"score"`
		MaxScore  int    `json:"max_score"`
	}
	err := sess.c.do(ctx, http.MethodGet,
		"/v1/sessions/"+url.PathEscape(sess.ID)+"/result?token="+url.QueryEscape(sess.Token), nil, &out)
	if err != nil {
		return nil, false, err
	}
	if !out.Submitted {
		return nil, false, nil
	}
	return &Submission{Status: out.Status, Score: out.Score, MaxScore: out.MaxScore}, true, nil
}

// WaitForScore polls Result until scoring completes or ctx expires.
func (sess *Session) WaitForScore(ctx context.Context) (*Submission, error) {
	t := time.NewTicker(2 * time.Second)
	defer t.Stop()
	for {
		sub, ok, err := sess.Result(ctx)
		if err != nil {
			return nil, err
		}
		if ok && sub.Status != "scoring" {
			return sub, nil
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-t.C:
		}
	}
}
