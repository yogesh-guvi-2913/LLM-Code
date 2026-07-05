// Package docker is a thin wrapper around the Docker Engine SDK, exposing only
// the operations the orchestrator needs: create, start, remove, copy, run-once.
package docker

import (
	"archive/tar"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"strconv"
	"strings"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/network"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/docker/go-connections/nat"
)

// sandboxLabel marks every container this orchestrator owns, so a restarting
// orchestrator can find the containers its previous incarnation left behind and
// reconcile them (re-adopt the live ones, reap the orphans) rather than blindly
// destroying every sandbox — which would drop candidates mid-assessment.
const sandboxLabel = "flash.sandbox"

// questionLabel records which template a sandbox belongs to, so reconcile on boot
// can map a recovered container back to its pool config (app/toolbox ports) with
// no in-process state.
const questionLabel = "flash.question"

// nodeLabel records which node-agent owns a sandbox. On a multi-node fleet (and in
// the local multi-agent simulation, where several agents share one Docker daemon)
// each agent manages only its own containers.
const nodeLabel = "flash.node"

type Client struct {
	cli *client.Client
}

// New connects to the local Docker daemon using the environment (DOCKER_HOST etc).
func New() (*Client, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("docker client: %w", err)
	}
	return &Client{cli: cli}, nil
}

func (c *Client) Close() error { return c.cli.Close() }

// ImageExists reports whether an image (by tag or id) is present in the daemon.
// Used to reject template registration for images that were never built/pulled,
// rather than registering a pool that silently never warms.
func (c *Client) ImageExists(ctx context.Context, ref string) bool {
	_, _, err := c.cli.ImageInspectWithRaw(ctx, ref)
	return err == nil
}

// SandboxSpec describes a warm/active sandbox container.
type SandboxSpec struct {
	Image       string
	Question    string // template id, stamped as a label for boot reconcile
	Node        string // owning node-agent id, stamped as a label
	Network     string
	Env         []string
	AppPort     int // container port the dev server listens on (e.g. 3000)
	ToolboxPort int // container port the toolbox listens on (e.g. 49983)
	HostApp     int // host port mapped to AppPort
	HostToolbox int // host port mapped to ToolboxPort
	MemoryMB    int64
	CPUQuota    int64 // microseconds per 100ms period; 50000 = 0.5 vCPU
	PidsLimit   int64
	// Runtime selects the OCI runtime: "" = dockerd default (runc), "runsc" =
	// gVisor. gVisor gives a real kernel boundary for untrusted candidate code.
	Runtime string
}

// SandboxInfo is a reconciled view of a labeled container, built from Docker on
// boot so the orchestrator can rebuild its pool with no surviving in-process state.
type SandboxInfo struct {
	ID       string
	Question string      // from the questionLabel
	Node     string      // from the nodeLabel
	Running  bool        // container state == "running"
	Ports    map[int]int // container (private) port -> host (public) port
}

// ListSandboxes returns every labeled container with its question and current
// container→host port mapping, so reconcile can re-adopt live sandboxes after an
// orchestrator restart. Docker is the source of truth for what is actually running.
func (c *Client) ListSandboxes(ctx context.Context) ([]SandboxInfo, error) {
	list, err := c.cli.ContainerList(ctx, container.ListOptions{
		All:     true,
		Filters: filters.NewArgs(filters.Arg("label", sandboxLabel)),
	})
	if err != nil {
		return nil, err
	}
	out := make([]SandboxInfo, 0, len(list))
	for _, ct := range list {
		ports := map[int]int{}
		for _, p := range ct.Ports {
			if p.PublicPort != 0 {
				ports[int(p.PrivatePort)] = int(p.PublicPort)
			}
		}
		out = append(out, SandboxInfo{
			ID:       ct.ID,
			Question: ct.Labels[questionLabel],
			Node:     ct.Labels[nodeLabel],
			Running:  ct.State == "running",
			Ports:    ports,
		})
	}
	return out, nil
}

// ContainerMem returns a container's current resident memory in bytes via a
// one-shot stats read. This is the measured density input behind $/sandbox-hr:
// the real working-set, not the configured limit. Docker reports memory_stats.usage
// inclusive of page cache, so we subtract the cache (inactive_file) to approximate
// true RSS — the same adjustment `docker stats` makes for its MEM USAGE column.
func (c *Client) ContainerMem(ctx context.Context, id string) (int64, error) {
	resp, err := c.cli.ContainerStatsOneShot(ctx, id)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	var v struct {
		MemoryStats struct {
			Usage uint64            `json:"usage"`
			Stats map[string]uint64 `json:"stats"`
		} `json:"memory_stats"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&v); err != nil {
		return 0, err
	}
	usage := v.MemoryStats.Usage
	// cgroup v2 reports inactive_file; v1 reports total_inactive_file. Subtract
	// whichever is present so cache doesn't inflate the working-set number.
	if cache, ok := v.MemoryStats.Stats["inactive_file"]; ok && cache <= usage {
		usage -= cache
	} else if cache, ok := v.MemoryStats.Stats["total_inactive_file"]; ok && cache <= usage {
		usage -= cache
	}
	return int64(usage), nil
}

// CreateSandbox creates and starts a hardened sandbox container. Returns its ID.
func (c *Client) CreateSandbox(ctx context.Context, s SandboxSpec) (string, error) {
	appPort := nat.Port(strconv.Itoa(s.AppPort) + "/tcp")
	tbPort := nat.Port(strconv.Itoa(s.ToolboxPort) + "/tcp")

	pids := s.PidsLimit
	period := int64(100000)

	resp, err := c.cli.ContainerCreate(ctx,
		&container.Config{
			Image:  s.Image,
			Env:    s.Env,
			Labels: map[string]string{sandboxLabel: "1", questionLabel: s.Question, nodeLabel: s.Node},
			ExposedPorts: nat.PortSet{
				appPort: {},
				tbPort:  {},
			},
		},
		&container.HostConfig{
			PortBindings: nat.PortMap{
				appPort: []nat.PortBinding{{HostIP: "127.0.0.1", HostPort: strconv.Itoa(s.HostApp)}},
				tbPort:  []nat.PortBinding{{HostIP: "127.0.0.1", HostPort: strconv.Itoa(s.HostToolbox)}},
			},
			Resources: container.Resources{
				Memory:    s.MemoryMB * 1024 * 1024,
				CPUQuota:  s.CPUQuota,
				CPUPeriod: period,
				PidsLimit: &pids,
			},
			NetworkMode: container.NetworkMode(s.Network),
			Runtime:     s.Runtime,
			// Drop every capability — a node dev server needs none. Default
			// seccomp + AppArmor stay on (we never pass unconfined).
			CapDrop:        []string{"ALL"},
			SecurityOpt:    []string{"no-new-privileges"},
			ReadonlyRootfs: true,
			// Only the candidate work dir and /tmp are writable, both on capped
			// tmpfs. The rest of the image (node_modules, binaries) is immutable.
			// mode=1777: tmpfs is root-owned, so without a world-writable sticky
			// mode the non-root 'node' user cannot write its work dir.
			Tmpfs: map[string]string{
				"/app/src": "rw,nosuid,nodev,mode=1777,size=64m",
				"/tmp":     "rw,nosuid,nodev,mode=1777,size=16m",
			},
			RestartPolicy: container.RestartPolicy{Name: "no"},
		},
		&network.NetworkingConfig{}, nil, "",
	)
	if err != nil {
		return "", fmt.Errorf("container create: %w", err)
	}
	if err := c.cli.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		_ = c.Remove(context.Background(), resp.ID)
		return "", fmt.Errorf("container start: %w", err)
	}
	return resp.ID, nil
}

// Remove force-removes a container; safe to call on a missing container.
func (c *Client) Remove(ctx context.Context, id string) error {
	return c.cli.ContainerRemove(ctx, id, container.RemoveOptions{Force: true})
}

// SnapshotDir tars `name` under `parent` from inside the container and returns
// the tar bytes (entries prefixed with `name/`). It runs `tar` via exec rather
// than CopyFromContainer because the candidate work dir is a tmpfs mount —
// docker cp reads the image layer and would miss every live edit.
func (c *Client) SnapshotDir(ctx context.Context, id, parent, name string) ([]byte, error) {
	execResp, err := c.cli.ContainerExecCreate(ctx, id, container.ExecOptions{
		Cmd:          []string{"tar", "-C", parent, "-cf", "-", name},
		AttachStdout: true,
		AttachStderr: true,
	})
	if err != nil {
		return nil, fmt.Errorf("exec create (snapshot): %w", err)
	}
	att, err := c.cli.ContainerExecAttach(ctx, execResp.ID, container.ExecAttachOptions{})
	if err != nil {
		return nil, fmt.Errorf("exec attach (snapshot): %w", err)
	}
	defer att.Close()

	var out, errBuf bytes.Buffer
	if _, err := stdcopy.StdCopy(&out, &errBuf, att.Reader); err != nil {
		return nil, fmt.Errorf("read snapshot stream: %w", err)
	}
	inspect, err := c.cli.ContainerExecInspect(ctx, execResp.ID)
	if err == nil && inspect.ExitCode != 0 {
		return nil, fmt.Errorf("tar exited %d: %s", inspect.ExitCode, errBuf.String())
	}
	if out.Len() == 0 {
		return nil, fmt.Errorf("empty snapshot: %s", errBuf.String())
	}
	return out.Bytes(), nil
}

// ExecOutput runs cmd in a running container and returns its stdout. Used by the
// playground to list/read candidate files (`find`, `cat`) without a toolbox API —
// the orchestrator/node-agent already has Docker, and /app/src is a tmpfs the exec
// sees live (docker cp would read the stale image layer).
func (c *Client) ExecOutput(ctx context.Context, id string, cmd []string) ([]byte, error) {
	execResp, err := c.cli.ContainerExecCreate(ctx, id, container.ExecOptions{
		Cmd: cmd, AttachStdout: true, AttachStderr: true,
	})
	if err != nil {
		return nil, fmt.Errorf("exec create: %w", err)
	}
	att, err := c.cli.ContainerExecAttach(ctx, execResp.ID, container.ExecAttachOptions{})
	if err != nil {
		return nil, fmt.Errorf("exec attach: %w", err)
	}
	defer att.Close()
	var out, errBuf bytes.Buffer
	if _, err := stdcopy.StdCopy(&out, &errBuf, att.Reader); err != nil {
		return nil, fmt.Errorf("read exec stream: %w", err)
	}
	if inspect, err := c.cli.ContainerExecInspect(ctx, execResp.ID); err == nil && inspect.ExitCode != 0 {
		return nil, fmt.Errorf("exec exit %d: %s", inspect.ExitCode, bytes.TrimSpace(errBuf.Bytes()))
	}
	return out.Bytes(), nil
}

// ExecResult is the outcome of a command run inside a live sandbox: the two
// streams kept separate plus the real exit code — the SDK-facing exec contract
// (a non-zero exit is a result, not a transport error).
type ExecResult struct {
	Stdout   []byte
	Stderr   []byte
	ExitCode int
}

// ExecRun runs cmd in a running container and returns stdout, stderr, and the
// exit code. Unlike ExecOutput it never maps a non-zero exit to an error — SDK
// callers need the code and both streams either way. cwd/env are optional.
func (c *Client) ExecRun(ctx context.Context, id string, cmd []string, cwd string, envKV []string) (ExecResult, error) {
	if cwd == "" {
		cwd = candidateDir
	}
	execResp, err := c.cli.ContainerExecCreate(ctx, id, container.ExecOptions{
		Cmd: cmd, WorkingDir: cwd, Env: envKV, AttachStdout: true, AttachStderr: true,
	})
	if err != nil {
		return ExecResult{}, fmt.Errorf("exec create: %w", err)
	}
	att, err := c.cli.ContainerExecAttach(ctx, execResp.ID, container.ExecAttachOptions{})
	if err != nil {
		return ExecResult{}, fmt.Errorf("exec attach: %w", err)
	}
	defer att.Close()
	var out, errBuf bytes.Buffer
	if _, err := stdcopy.StdCopy(&out, &errBuf, att.Reader); err != nil {
		// A canceled context (caller timeout) surfaces here; the exec keeps running
		// in the container but we report the abort to the caller.
		return ExecResult{}, fmt.Errorf("read exec stream: %w", err)
	}
	inspect, err := c.cli.ContainerExecInspect(ctx, execResp.ID)
	if err != nil {
		return ExecResult{}, fmt.Errorf("exec inspect: %w", err)
	}
	return ExecResult{Stdout: out.Bytes(), Stderr: errBuf.Bytes(), ExitCode: inspect.ExitCode}, nil
}

// ExecWithInput runs cmd feeding `stdin` to it (used to write a candidate file via
// `sh -c 'cat > "$1"'`). Returns an error on a non-zero exit.
func (c *Client) ExecWithInput(ctx context.Context, id string, cmd []string, stdin []byte) error {
	execResp, err := c.cli.ContainerExecCreate(ctx, id, container.ExecOptions{
		Cmd: cmd, AttachStdin: true, AttachStdout: true, AttachStderr: true,
	})
	if err != nil {
		return fmt.Errorf("exec create: %w", err)
	}
	att, err := c.cli.ContainerExecAttach(ctx, execResp.ID, container.ExecAttachOptions{})
	if err != nil {
		return fmt.Errorf("exec attach: %w", err)
	}
	defer att.Close()
	if _, err := att.Conn.Write(stdin); err != nil {
		return fmt.Errorf("exec write stdin: %w", err)
	}
	_ = att.CloseWrite() // signal EOF so `cat` finishes
	var out, errBuf bytes.Buffer
	_, _ = stdcopy.StdCopy(&out, &errBuf, att.Reader)
	if inspect, err := c.cli.ContainerExecInspect(ctx, execResp.ID); err == nil && inspect.ExitCode != 0 {
		return fmt.Errorf("exec exit %d: %s", inspect.ExitCode, bytes.TrimSpace(errBuf.Bytes()))
	}
	return nil
}

// candidateDir is the writable work dir inside every sandbox (a tmpfs).
const candidateDir = "/app/src"

// ListCandidateFiles returns the candidate's files as paths relative to the work
// dir (e.g. "src/App.tsx"). Callers sanitize any path they later read/write.
func (c *Client) ListCandidateFiles(ctx context.Context, id string) ([]string, error) {
	out, err := c.ExecOutput(ctx, id, []string{"find", candidateDir, "-type", "f"})
	if err != nil {
		return nil, err
	}
	var files []string
	for _, line := range bytes.Split(bytes.TrimSpace(out), []byte("\n")) {
		s := string(bytes.TrimSpace(line))
		if s == "" {
			continue
		}
		s = strings.TrimPrefix(s, candidateDir+"/")
		files = append(files, s)
	}
	return files, nil
}

// ReadCandidateFile returns the contents of <work dir>/<rel>. `rel` must already be
// sanitized to a relative path by the caller.
func (c *Client) ReadCandidateFile(ctx context.Context, id, rel string) ([]byte, error) {
	return c.ExecOutput(ctx, id, []string{"cat", candidateDir + "/" + rel})
}

// WriteCandidateFile writes content to <work dir>/<rel>, creating parent dirs. The
// path is passed as a positional arg ($1) — never interpolated into the shell — so
// a candidate file name can't inject commands.
func (c *Client) WriteCandidateFile(ctx context.Context, id, rel string, content []byte) error {
	full := candidateDir + "/" + rel
	return c.ExecWithInput(ctx, id,
		[]string{"sh", "-c", `mkdir -p "$(dirname "$1")" && cat > "$1"`, "sh", full}, content)
}

// DeleteCandidateFile removes <work dir>/<rel> (file or directory). `rel` must
// already be sanitized to a relative path by the caller.
func (c *Client) DeleteCandidateFile(ctx context.Context, id, rel string) error {
	_, err := c.ExecOutput(ctx, id, []string{"rm", "-rf", "--", candidateDir + "/" + rel})
	return err
}

// RunScorer runs a one-shot, network-isolated scoring container that mounts the
// submission tar (a /app/src tar stream) and runs the harness. It streams the
// candidate source into the container, runs the harness command, and returns the
// combined stdout. The container is always removed.
func (c *Client) RunScorer(ctx context.Context, image string, srcTar []byte, cmd []string, memMB, pids int64, timeout time.Duration) ([]byte, error) {
	pidsLimit := pids
	resp, err := c.cli.ContainerCreate(ctx,
		&container.Config{
			Image:      image,
			Cmd:        cmd,
			Tty:        false,
			WorkingDir: "/app",
		},
		&container.HostConfig{
			NetworkMode: "none",
			AutoRemove:  false,
			Resources: container.Resources{
				Memory:    memMB * 1024 * 1024,
				PidsLimit: &pidsLimit,
			},
			CapDrop:     []string{"ALL"},
			SecurityOpt: []string{"no-new-privileges"},
		}, nil, nil, "")
	if err != nil {
		return nil, fmt.Errorf("scorer create: %w", err)
	}
	defer c.Remove(context.Background(), resp.ID)

	// Overlay the candidate's /app/src into the container before starting.
	if err := c.cli.CopyToContainer(ctx, resp.ID, "/app", bytes.NewReader(srcTar), container.CopyToContainerOptions{}); err != nil {
		return nil, fmt.Errorf("inject submission: %w", err)
	}
	if err := c.cli.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		return nil, fmt.Errorf("scorer start: %w", err)
	}

	runCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	statusCh, errCh := c.cli.ContainerWait(runCtx, resp.ID, container.WaitConditionNotRunning)
	select {
	case err := <-errCh:
		if err != nil {
			return nil, fmt.Errorf("scorer wait: %w", err)
		}
	case <-statusCh:
	case <-runCtx.Done():
		_ = c.cli.ContainerKill(context.Background(), resp.ID, "KILL")
		return nil, fmt.Errorf("scorer timed out after %s", timeout)
	}

	logs, err := c.cli.ContainerLogs(ctx, resp.ID, container.LogsOptions{ShowStdout: true, ShowStderr: false})
	if err != nil {
		return nil, fmt.Errorf("scorer logs: %w", err)
	}
	defer logs.Close()
	var out bytes.Buffer
	if _, err := stdcopy.StdCopy(&out, io.Discard, logs); err != nil {
		return nil, fmt.Errorf("demux logs: %w", err)
	}
	return out.Bytes(), nil
}

// TarFromBytes builds a tar stream containing src/<files...> rooted so that
// CopyToContainer("/app", ...) lands them at /app/src. Used by the scorer when
// reading a snapshot from disk. (Kept here so callers stay tar-agnostic.)
func TarSingleDir(prefix string, files map[string][]byte) ([]byte, error) {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	for name, data := range files {
		hdr := &tar.Header{Name: prefix + "/" + name, Mode: 0o644, Size: int64(len(data))}
		if err := tw.WriteHeader(hdr); err != nil {
			return nil, err
		}
		if _, err := tw.Write(data); err != nil {
			return nil, err
		}
	}
	if err := tw.Close(); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
