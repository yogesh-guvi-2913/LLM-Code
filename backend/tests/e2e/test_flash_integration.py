import os
import pytest
import time

pytestmark = pytest.mark.skipif(
    os.getenv("FLASH_E2E", "0") != "1",
    reason="FLASH_E2E=1 not set - skipping live e2e tests"
)


@pytest.mark.e2e_live
class TestSandboxLifecycle:
    def test_start_sandbox_success(self, live_auth_token, live_test_data):
        from fastapi.testclient import TestClient
        from app.main import app
        
        token, user_hash = live_auth_token
        test_id, _ = live_test_data
        
        client = TestClient(app)
        
        response = client.post(
            "/flash/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"testId": test_id}
        )
        
        assert response.status_code == 200, f"Failed: {response.json()}"
        data = response.json()
        
        assert "sandboxId" in data or "sessionId" in data
        sandbox_id = data.get("sandboxId") or data.get("sessionId")
        assert sandbox_id is not None
        
        stop_response = client.post(
            "/flash/stop",
            headers={"Authorization": f"Bearer {token}"},
            json={"testId": test_id}
        )
        assert stop_response.status_code in [200, 404]
    
    def test_start_sandbox_invalid_token(self, live_test_data):
        from fastapi.testclient import TestClient
        from app.main import app
        
        test_id, _ = live_test_data
        client = TestClient(app)
        
        response = client.post(
            "/flash/start",
            headers={"Authorization": "Bearer invalid-token-xyz"},
            json={"testId": test_id}
        )
        
        assert response.status_code in [401, 403]
    
    def test_start_sandbox_invalid_test_id(self, live_auth_token):
        from fastapi.testclient import TestClient
        from app.main import app
        
        token, _ = live_auth_token
        client = TestClient(app)
        
        response = client.post(
            "/flash/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"testId": "non-existent-test-id"}
        )
        
        assert response.status_code in [400, 404]
    
    def test_stop_sandbox_without_start(self, live_auth_token, live_test_data):
        from fastapi.testclient import TestClient
        from app.main import app
        
        token, _ = live_auth_token
        test_id, _ = live_test_data
        client = TestClient(app)
        
        response = client.post(
            "/flash/stop",
            headers={"Authorization": f"Bearer {token}"},
            json={"testId": test_id}
        )
        
        assert response.status_code in [200, 404]


@pytest.mark.e2e_live
class TestSandboxExec:
    def test_exec_simple_command(self, live_sandbox):
        client = live_sandbox["client"]
        token = live_sandbox["token"]
        test_id = live_sandbox["test_id"]
        
        response = client.post(
            "/flash/exec",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "testId": test_id,
                "command": "echo 'hello world'"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.json()}"
        data = response.json()
        
        assert "stdout" in data or "output" in data
        output = data.get("stdout") or data.get("output", "")
        assert "hello world" in output.lower() or "hello" in output.lower()
    
    def test_exec_list_files(self, live_sandbox):
        client = live_sandbox["client"]
        token = live_sandbox["token"]
        test_id = live_sandbox["test_id"]
        
        response = client.post(
            "/flash/exec",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "testId": test_id,
                "command": "ls -la"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.json()}"
        data = response.json()
        
        assert "stdout" in data or "output" in data
    
    def test_exec_invalid_command(self, live_sandbox):
        client = live_sandbox["client"]
        token = live_sandbox["token"]
        test_id = live_sandbox["test_id"]
        
        response = client.post(
            "/flash/exec",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "testId": test_id,
                "command": "nonexistentcommand12345"
            }
        )
        
        assert response.status_code in [200, 400, 500]
        if response.status_code == 200:
            data = response.json()
            assert "stderr" in data or "error" in data


@pytest.mark.e2e_live
class TestSandboxFiles:
    def test_write_and_read_file(self, live_sandbox):
        client = live_sandbox["client"]
        token = live_sandbox["token"]
        test_id = live_sandbox["test_id"]
        
        test_content = f"// Test file {os.urandom(4).hex()}"
        test_path = "/app/test_file.js"
        
        write_response = client.post(
            "/flash/files/write",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "testId": test_id,
                "path": test_path,
                "content": test_content
            }
        )
        
        assert write_response.status_code == 200, f"Write failed: {write_response.json()}"
        
        read_response = client.get(
            "/flash/files/read",
            headers={"Authorization": f"Bearer {token}"},
            params={"testId": test_id, "path": test_path}
        )
        
        assert read_response.status_code == 200, f"Read failed: {read_response.json()}"
        data = read_response.json()
        
        assert "content" in data
        assert data["content"] == test_content
    
    def test_list_files(self, live_sandbox):
        client = live_sandbox["client"]
        token = live_sandbox["token"]
        test_id = live_sandbox["test_id"]
        
        response = client.get(
            "/flash/files/list",
            headers={"Authorization": f"Bearer {token}"},
            params={"testId": test_id, "path": "/app"}
        )
        
        assert response.status_code == 200, f"Failed: {response.json()}"
        data = response.json()
        
        assert "files" in data or "items" in data
        files = data.get("files") or data.get("items", [])
        assert isinstance(files, list)
    
    def test_read_nonexistent_file(self, live_sandbox):
        client = live_sandbox["client"]
        token = live_sandbox["token"]
        test_id = live_sandbox["test_id"]
        
        response = client.get(
            "/flash/files/read",
            headers={"Authorization": f"Bearer {token}"},
            params={"testId": test_id, "path": "/app/nonexistent_file_xyz.js"}
        )
        
        assert response.status_code in [400, 404]


@pytest.mark.e2e_live
class TestAssessmentFlow:
    def test_submit_and_results(self, live_sandbox):
        client = live_sandbox["client"]
        token = live_sandbox["token"]
        test_id = live_sandbox["test_id"]
        
        test_content = f"// Submission test {os.urandom(4).hex()}\nconst express = require('express');\nconst app = express();\napp.get('/api/items', (req, res) => res.json([]));\napp.listen(3000);"
        
        write_response = client.post(
            "/flash/files/write",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "testId": test_id,
                "path": "/app/src/index.js",
                "content": test_content
            }
        )
        assert write_response.status_code == 200
        
        submit_response = client.post(
            "/flash/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"testId": test_id}
        )
        
        assert submit_response.status_code in [200, 202], f"Submit failed: {submit_response.json()}"
        submit_data = submit_response.json()
        
        assert "submissionId" in submit_data or "status" in submit_data
        
        time.sleep(2)
        
        results_response = client.get(
            "/flash/results",
            headers={"Authorization": f"Bearer {token}"},
            params={"testId": test_id}
        )
        
        assert results_response.status_code == 200, f"Results failed: {results_response.json()}"
        results_data = results_response.json()
        
        assert "score" in results_data or "status" in results_data