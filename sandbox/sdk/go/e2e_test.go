package flash

// Real end-to-end tests: they drive a live orchestrator (real containers, real
// Postgres) — no mocks, no stubs. Run with:
//
//	FLASH_E2E=1 FLASH_BASE_URL=http://127.0.0.1:8090 FLASH_API_KEY=flash_… go test ./...
//
// Requirements: the orchestrator is up with the default templates built
// (scripts/build-image.sh) and warm.

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"
)

func e2eClient(t *testing.T) *Client {
	t.Helper()
	if os.Getenv("FLASH_E2E") == "" {
		t.Skip("set FLASH_E2E=1 (with FLASH_BASE_URL/FLASH_API_KEY) to run e2e tests against a live orchestrator")
	}
	c, err := New()
	if err != nil {
		t.Fatalf("client: %v", err)
	}
	return c
}

func TestSandboxLifecycle(t *testing.T) {
	c := e2eClient(t)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	tmpls, err := c.Templates.List(ctx)
	if err != nil {
		t.Fatalf("templates: %v", err)
	}
	if len(tmpls) == 0 {
		t.Fatal("no templates registered")
	}

	start := time.Now()
	sbx, err := c.Sandboxes.Create(ctx, CreateSandboxOpts{
		Template: "q1",
		Timeout:  10 * time.Minute,
		Metadata: map[string]string{"purpose": "sdk-e2e"},
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	t.Logf("claimed sandbox %s in %s", sbx.ID, time.Since(start))
	defer sbx.Kill(context.Background())

	if sbx.State != "running" {
		t.Fatalf("state = %q, want running", sbx.State)
	}
	if sbx.Metadata["purpose"] != "sdk-e2e" {
		t.Fatalf("metadata not round-tripped: %v", sbx.Metadata)
	}

	// Shell command, stdout comes back, exit 0.
	res, err := sbx.Run(ctx, "echo hello from $HOSTNAME")
	if err != nil {
		t.Fatalf("run: %v", err)
	}
	if res.ExitCode != 0 || !strings.HasPrefix(res.Stdout, "hello from") {
		t.Fatalf("run = exit %d stdout %q", res.ExitCode, res.Stdout)
	}

	// Non-zero exit is a result, not an error.
	res, err = sbx.Run(ctx, "exit 3")
	if err != nil {
		t.Fatalf("run exit 3: %v", err)
	}
	if res.ExitCode != 3 {
		t.Fatalf("exit code = %d, want 3", res.ExitCode)
	}

	// Argv exec + per-command env + stderr separation.
	res, err = sbx.Exec(ctx, []string{"sh", "-c", "echo out; echo err >&2; echo $FOO"},
		ExecOpts{Env: map[string]string{"FOO": "bar"}})
	if err != nil {
		t.Fatalf("exec: %v", err)
	}
	if !strings.Contains(res.Stdout, "out") || !strings.Contains(res.Stdout, "bar") {
		t.Fatalf("stdout = %q", res.Stdout)
	}
	if !strings.Contains(res.Stderr, "err") {
		t.Fatalf("stderr = %q", res.Stderr)
	}

	// Files: write, read back, list, delete, read-after-delete fails.
	files := sbx.Files()
	if err := files.Write(ctx, "e2e/hello.txt", []byte("sdk wrote this")); err != nil {
		t.Fatalf("write: %v", err)
	}
	b, err := files.Read(ctx, "e2e/hello.txt")
	if err != nil || string(b) != "sdk wrote this" {
		t.Fatalf("read = %q, %v", b, err)
	}
	list, err := files.List(ctx)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	found := false
	for _, f := range list {
		if f == "e2e/hello.txt" {
			found = true
		}
	}
	if !found {
		t.Fatalf("e2e/hello.txt not in listing (%d files)", len(list))
	}
	if err := files.Delete(ctx, "e2e/hello.txt"); err != nil {
		t.Fatalf("delete: %v", err)
	}
	if _, err := files.Read(ctx, "e2e/hello.txt"); err == nil {
		t.Fatal("read after delete should fail")
	}

	// Keep-alive.
	before := sbx.ExpiresAt
	if err := sbx.SetTimeout(ctx, 30*time.Minute); err != nil {
		t.Fatalf("set timeout: %v", err)
	}
	if !sbx.ExpiresAt.After(before) {
		t.Fatalf("expires_at did not move: %s -> %s", before, sbx.ExpiresAt)
	}

	// Connect + list see it.
	again, err := c.Sandboxes.Connect(ctx, sbx.ID)
	if err != nil || again.State != "running" {
		t.Fatalf("connect = %+v, %v", again, err)
	}
	running, err := c.Sandboxes.List(ctx, true)
	if err != nil {
		t.Fatalf("list sandboxes: %v", err)
	}
	found = false
	for _, s := range running {
		if s.ID == sbx.ID {
			found = true
		}
	}
	if !found {
		t.Fatal("created sandbox missing from running list")
	}

	// Kill is real and idempotent.
	if err := sbx.Kill(ctx); err != nil {
		t.Fatalf("kill: %v", err)
	}
	if err := sbx.Kill(ctx); err != nil {
		t.Fatalf("second kill should be idempotent: %v", err)
	}
	if err := sbx.Refresh(ctx); err != nil {
		t.Fatalf("refresh: %v", err)
	}
	if sbx.State != "destroyed" {
		t.Fatalf("state after kill = %q", sbx.State)
	}
	if _, err := sbx.Run(ctx, "echo nope"); err == nil {
		t.Fatal("exec on a destroyed sandbox should fail")
	}
}

func TestAPIKeyLifecycle(t *testing.T) {
	c := e2eClient(t)
	if os.Getenv("FLASH_API_KEY") == "" {
		t.Skip("auth disabled (no FLASH_API_KEY) — key lifecycle needs AUTH_ENABLED=true")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	created, err := c.APIKeys.Create(ctx, "sdk-e2e")
	if err != nil {
		t.Fatalf("create key: %v", err)
	}
	if !strings.HasPrefix(created.Key, "flash_") {
		t.Fatalf("raw key %q missing prefix", created.Key)
	}

	// The new key authenticates a fresh client.
	c2, err := New(WithAPIKey(created.Key))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c2.Templates.List(ctx); err != nil {
		t.Fatalf("new key rejected: %v", err)
	}

	keys, err := c.APIKeys.List(ctx)
	if err != nil {
		t.Fatalf("list keys: %v", err)
	}
	found := false
	for _, k := range keys {
		if k.ID == created.ID && k.Name == "sdk-e2e" {
			found = true
		}
	}
	if !found {
		t.Fatal("minted key not in list")
	}

	// A key cannot revoke itself…
	if err := c2.APIKeys.Revoke(ctx, created.ID); err == nil {
		t.Fatal("self-revocation should be refused")
	}
	// …but another key can revoke it, after which it stops working.
	if err := c.APIKeys.Revoke(ctx, created.ID); err != nil {
		t.Fatalf("revoke: %v", err)
	}
	if _, err := c2.Templates.List(ctx); err == nil {
		t.Fatal("revoked key still authenticates")
	}
}

func TestAssessmentFlow(t *testing.T) {
	c := e2eClient(t)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	sess, err := c.Assessments.CreateSession(ctx, CreateSessionOpts{
		CandidateID: "sdk-e2e-candidate",
		QuestionID:  "q1",
		TimeLimit:   10 * time.Minute,
	})
	if err != nil {
		t.Fatalf("create session: %v", err)
	}
	if sess.Token == "" {
		t.Fatal("no session token returned")
	}

	// Submit the starter code as-is and wait for the real scorer.
	sub, err := sess.Submit(ctx)
	if err != nil {
		t.Fatalf("submit: %v", err)
	}
	if sub.SubmissionID == "" {
		t.Fatal("no submission id")
	}
	scored, err := sess.WaitForScore(ctx)
	if err != nil {
		t.Fatalf("wait for score: %v", err)
	}
	if scored.Status != "scored" {
		t.Fatalf("submission status = %q, want scored", scored.Status)
	}
	if scored.MaxScore <= 0 {
		t.Fatalf("max score = %d", scored.MaxScore)
	}
	t.Logf("starter code scored %d/%d", scored.Score, scored.MaxScore)
}
