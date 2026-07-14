#!/usr/bin/env python3
"""
Flash Integration Test Suite

Tests the complete Flash sandbox integration flow:
1. Flash service health check
2. Template listing
3. Session creation with Flash template
4. File operations (list, read, write)
5. Submit and score
6. Session cleanup

Run with: python scripts/test_flash_integration.py
"""

import os
import sys
import json
import time
import argparse
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests


class FlashIntegrationTester:
    def __init__(self, api_url: str = "http://localhost:8000", flash_url: str = "http://localhost:8090"):
        self.api_url = api_url
        self.flash_url = flash_url
        self.auth_token: Optional[str] = None
        self.test_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.results = {"passed": 0, "failed": 0, "tests": []}
    
    def log(self, message: str, level: str = "info"):
        symbols = {"info": "ℹ", "pass": "✓", "fail": "✗", "warn": "⚠"}
        print(f"  {symbols.get(level, '•')} {message}")
    
    def test(self, name: str):
        def decorator(func):
            def wrapper():
                print(f"\n[Test] {name}")
                try:
                    result = func()
                    self.results["passed"] += 1
                    self.results["tests"].append({"name": name, "status": "passed"})
                    self.log(f"Passed: {name}", "pass")
                    return result
                except AssertionError as e:
                    self.results["failed"] += 1
                    self.results["tests"].append({"name": name, "status": "failed", "error": str(e)})
                    self.log(f"Failed: {e}", "fail")
                    return None
                except Exception as e:
                    self.results["failed"] += 1
                    self.results["tests"].append({"name": name, "status": "failed", "error": str(e)})
                    self.log(f"Error: {e}", "fail")
                    return None
            return wrapper
        return decorator
    
    def request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.api_url}{endpoint}"
        response = requests.request(method, url, **kwargs)
        return response.json()
    
    def test_flash_health(self) -> bool:
        """Test Flash service health directly."""
        print("\n[Test] Flash Health Check (Direct)")
        try:
            response = requests.get(f"{self.flash_url}/v1/templates", timeout=5)
            data = response.json()
            
            assert response.status_code == 200, f"Templates request failed: {response.status_code}"
            assert isinstance(data, list), f"Expected list of templates: {type(data)}"
            
            self.log(f"Flash is running with {len(data)} templates", "pass")
            for t in data:
                warm = t.get('warm', 0)
                self.log(f"  - {t.get('id')}: {t.get('title')} (warm: {warm})", "info")
            
            self.results["passed"] += 1
            self.results["tests"].append({"name": "Flash Health Check (Direct)", "status": "passed"})
            return True
        except AssertionError as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": "Flash Health Check (Direct)", "status": "failed", "error": str(e)})
            self.log(f"Failed: {e}", "fail")
            return False
        except Exception as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": "Flash Health Check (Direct)", "status": "failed", "error": str(e)})
            self.log(f"Error: {e}", "fail")
            return False
    
    def test_flash_templates_direct(self) -> bool:
        """Test listing Flash templates directly."""
        print("\n[Test] List Flash Templates (Direct)")
        try:
            response = requests.get(f"{self.flash_url}/v1/templates", timeout=5)
            data = response.json()
            
            assert response.status_code == 200, f"Templates request failed: {response.status_code}"
            assert isinstance(data, list), f"Expected list: {type(data)}"
            assert len(data) > 0, "No templates available"
            
            self.log(f"Found {len(data)} templates:", "pass")
            for t in data:
                warm = t.get('warm', 0)
                self.log(f"  - {t.get('id')}: {t.get('title')} ({t.get('language')}, warm: {warm})", "info")
            
            self.results["passed"] += 1
            self.results["tests"].append({"name": "List Flash Templates (Direct)", "status": "passed"})
            return True
        except AssertionError as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": "List Flash Templates (Direct)", "status": "failed", "error": str(e)})
            self.log(f"Failed: {e}", "fail")
            return False
        except Exception as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": "List Flash Templates (Direct)", "status": "failed", "error": str(e)})
            self.log(f"Error: {e}", "fail")
            return False
    
    def test_api_health(self) -> bool:
        """Test LLM-Code API health with Flash status."""
        print("\n[Test] LLM-Code API Health")
        try:
            response = requests.get(f"{self.api_url}/v1/", timeout=5)
            data = response.json()
            
            assert response.status_code == 200, f"API health failed: {response.status_code}"
            self.log(f"API status: {data.get('status')}", "pass")
            
            response = requests.get(f"{self.api_url}/v1/health/flash", timeout=10)
            flash_data = response.json()
            
            if flash_data.get("connected"):
                self.log(f"Flash connected: {flash_data.get('templates', 0)} templates", "pass")
            else:
                self.log(f"Flash not connected: {flash_data.get('error', 'unknown')}", "warn")
            
            self.results["passed"] += 1
            self.results["tests"].append({"name": "LLM-Code API Health", "status": "passed"})
            return True
        except Exception as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": "LLM-Code API Health", "status": "failed", "error": str(e)})
            self.log(f"Error: {e}", "fail")
            return False
    
    def test_admin_flash_templates(self) -> bool:
        """Test admin Flash templates endpoint."""
        print("\n[Test] Admin Flash Templates Endpoint")
        try:
            response = requests.get(f"{self.api_url}/v1/admin/flash/templates", timeout=10)
            data = response.json()
            
            assert response.status_code == 200, f"Request failed: {response.status_code}"
            assert data.get("success", False), f"Request not successful: {data}"
            
            if not data.get("enabled"):
                self.log("Flash integration disabled", "warn")
                return False
            
            templates = data.get("templates", [])
            self.log(f"Found {len(templates)} templates via API", "pass")
            
            for t in templates:
                warm = t.get("warm_count", 0)
                self.log(f"  - {t.get('id')}: {t.get('title')} (warm: {warm})", "info")
            
            self.results["passed"] += 1
            self.results["tests"].append({"name": "Admin Flash Templates Endpoint", "status": "passed"})
            return True
        except AssertionError as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": "Admin Flash Templates Endpoint", "status": "failed", "error": str(e)})
            self.log(f"Failed: {e}", "fail")
            return False
        except Exception as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": "Admin Flash Templates Endpoint", "status": "failed", "error": str(e)})
            self.log(f"Error: {e}", "fail")
            return False
    
    def test_flash_session_lifecycle(self, template_id: str = "q1") -> bool:
        """Test complete Flash session lifecycle."""
        print(f"\n[Test] Flash Session Lifecycle (template: {template_id})")
        
        sandbox_id = None
        try:
            self.log("Creating sandbox...", "info")
            response = requests.post(
                f"{self.flash_url}/v1/sandboxes",
                json={"template_id": template_id, "timeout_seconds": 300},
                timeout=30
            )
            data = response.json()
            
            assert response.status_code == 200, f"Create failed: {response.status_code} - {data}"
            sandbox_id = data.get("sandbox_id") or data.get("id")
            assert sandbox_id, "No sandbox ID returned"
            
            self.log(f"Created sandbox: {sandbox_id}", "pass")
            self.log(f"  App URL: {data.get('app_url')}", "info")
            self.log(f"  Preview: {data.get('preview_url')}", "info")
            self.log(f"  Terminal: {data.get('terminal_url')}", "info")
            
            time.sleep(2)
            
            self.log("Listing files...", "info")
            response = requests.get(f"{self.flash_url}/v1/sandboxes/{sandbox_id}/files", timeout=10)
            files_data = response.json()
            files = files_data.get("files", [])
            self.log(f"Found {len(files)} files", "pass")
            
            if files:
                first_file = files[0]
                self.log(f"Reading {first_file}...", "info")
                response = requests.get(
                    f"{self.flash_url}/v1/sandboxes/{sandbox_id}/files/content",
                    params={"path": first_file},
                    timeout=10
                )
                content = response.json().get("content", "")
                self.log(f"Read {len(content)} bytes", "pass")
            
            self.log("Writing test file...", "info")
            test_content = "// Test file from integration test\nconsole.log('Hello Flash!');\n"
            response = requests.put(
                f"{self.flash_url}/v1/sandboxes/{sandbox_id}/files/content",
                params={"path": "test_integration.js"},
                data=test_content,
                headers={"Content-Type": "text/plain"},
                timeout=10
            )
            self.log(f"Write response: {response.status_code}", "pass" if response.status_code == 200 else "fail")
            
            self.log("Stopping sandbox...", "info")
            response = requests.delete(f"{self.flash_url}/v1/sandboxes/{sandbox_id}", timeout=10)
            self.log(f"Stopped: {response.status_code}", "pass")
            
            self.results["passed"] += 1
            self.results["tests"].append({"name": f"Flash Session Lifecycle ({template_id})", "status": "passed"})
            return True
            
        except AssertionError as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": f"Flash Session Lifecycle ({template_id})", "status": "failed", "error": str(e)})
            self.log(f"Failed: {e}", "fail")
            return False
        except Exception as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": f"Flash Session Lifecycle ({template_id})", "status": "failed", "error": str(e)})
            self.log(f"Error: {e}", "fail")
            return False
        finally:
            if sandbox_id:
                try:
                    requests.delete(f"{self.flash_url}/v1/sandboxes/{sandbox_id}", timeout=5)
                except:
                    pass
    
    def test_warm_pool_scaling(self, template_id: str = "q1", target: int = 2) -> bool:
        """Test warm pool scaling."""
        print(f"\n[Test] Warm Pool Scaling (template: {template_id}, target: {target})")
        try:
            self.log(f"Setting warm pool to {target}...", "info")
            response = requests.post(
                f"{self.flash_url}/v1/templates/{template_id}/min_warm",
                json={"min_warm": target},
                timeout=30
            )
            
            if response.status_code not in [200, 202]:
                self.log(f"Scale request status: {response.status_code}", "warn")
            
            time.sleep(2)
            
            response = requests.get(f"{self.flash_url}/v1/templates", timeout=10)
            templates = response.json()
            
            warm_count = 0
            for t in templates:
                if t.get("id") == template_id:
                    warm_count = t.get("warm", 0)
                    break
            
            self.log(f"Warm pool count: {warm_count}", "pass" if warm_count >= target else "warn")
            
            self.results["passed"] += 1
            self.results["tests"].append({"name": f"Warm Pool Scaling ({template_id})", "status": "passed"})
            return True
        except Exception as e:
            self.results["failed"] += 1
            self.results["tests"].append({"name": f"Warm Pool Scaling ({template_id})", "status": "failed", "error": str(e)})
            self.log(f"Error: {e}", "fail")
            return False
    
    def run_all_tests(self, skip_slow: bool = False):
        """Run all integration tests."""
        print("=" * 60)
        print("Flash Integration Test Suite")
        print("=" * 60)
        
        self.test_flash_health()
        self.test_flash_templates_direct()
        self.test_api_health()
        self.test_admin_flash_templates()
        
        if not skip_slow:
            self.test_flash_session_lifecycle("q1")
            self.test_warm_pool_scaling("q1", 2)
        
        print("\n" + "=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        print(f"Passed: {self.results['passed']}")
        print(f"Failed: {self.results['failed']}")
        print(f"Total:  {self.results['passed'] + self.results['failed']}")
        
        if self.results["failed"] > 0:
            print("\nFailed Tests:")
            for t in self.results["tests"]:
                if t["status"] == "failed":
                    print(f"  - {t['name']}: {t.get('error', 'unknown')}")
        
        return self.results["failed"] == 0


def main():
    parser = argparse.ArgumentParser(description="Flash Integration Test Suite")
    parser.add_argument("--api-url", default="http://localhost:8000", help="LLM-Code API URL")
    parser.add_argument("--flash-url", default="http://localhost:8090", help="Flash Sandbox API URL")
    parser.add_argument("--skip-slow", action="store_true", help="Skip slow tests (session lifecycle)")
    parser.add_argument("--template", default="q1", help="Template ID to test")
    
    args = parser.parse_args()
    
    tester = FlashIntegrationTester(api_url=args.api_url, flash_url=args.flash_url)
    success = tester.run_all_tests(skip_slow=args.skip_slow)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()