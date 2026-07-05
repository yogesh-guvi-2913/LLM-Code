package flash

import (
	"context"
	"net/http"
	"net/url"
	"time"
)

// APIKeyService manages the org's API keys.
type APIKeyService struct{ c *Client }

// APIKey is one credential's metadata. The raw key exists only in
// CreatedAPIKey.Key at mint time; thereafter only the display prefix is shown.
type APIKey struct {
	ID         string     `json:"id"`
	Name       string     `json:"name"`
	Prefix     string     `json:"prefix"`
	CreatedAt  time.Time  `json:"created_at"`
	LastUsedAt *time.Time `json:"last_used_at,omitempty"`
}

// CreatedAPIKey is the mint response — Key is shown exactly once.
type CreatedAPIKey struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Prefix string `json:"prefix"`
	Key    string `json:"key"`
}

// Create mints a new named key. Store the returned Key — it is unrecoverable.
func (s *APIKeyService) Create(ctx context.Context, name string) (*CreatedAPIKey, error) {
	var out CreatedAPIKey
	if err := s.c.do(ctx, http.MethodPost, "/v1/api-keys", map[string]string{"name": name}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// List returns the org's live keys.
func (s *APIKeyService) List(ctx context.Context) ([]APIKey, error) {
	var out struct {
		Keys []APIKey `json:"keys"`
	}
	err := s.c.do(ctx, http.MethodGet, "/v1/api-keys", nil, &out)
	return out.Keys, err
}

// Revoke disables a key immediately. Revoking the key this client is using is
// refused by the server (409) — mint a replacement first.
func (s *APIKeyService) Revoke(ctx context.Context, id string) error {
	return s.c.do(ctx, http.MethodDelete, "/v1/api-keys/"+url.PathEscape(id), nil, nil)
}
