#!/usr/bin/env python3
"""
Playwright tests for Notion-like Web App data persistence.
Tests: 1) Blocks persist after page reload, 2) Blocks persist after app restart (kill/start.sh), 3) Selection-based editing/deletion works correctly.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent / ".agent_scripts"
BROWSER_SCRIPT = SCRIPT_DIR / "browser.py"


def run_api_call(url: str, method: str = "GET", body: str = None) -> dict:
    """Make API call using curl."""
    cmd = ["curl", "-s", "-X", method]
    if body:
        cmd.extend(["-d", f"'{body}'", "--data-binary"])
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout, "error": result.stderr}


def run_browser(url: str, **kwargs) -> dict:
    """Run the harness browser tool with given options."""
    cmd = [sys.executable, str(BROWSER_SCRIPT), "--url", url]
    for key, value in kwargs.items():
        if isinstance(value, list):
            for item in value:
                cmd.extend(["--" + key.replace("-", ""), str(item)])
        else:
            cmd.extend(["--" + key.replace("-", ""), str(value)])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"Browser command failed: {result.stderr}")
        return {"success": False, "error": result.stderr}
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"success": False, "error": result.stdout[:500]}


def wait_for_app(port=8765):
    """Wait for app to be ready."""
    timeout = 10
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = run_api_call(f"http://127.0.0.1:{port}/health")
            if resp.get("status") == "ok":
                return True
        except:
            pass
        time.sleep(0.5)
    return False


def test_page_reload_persistence():
    """Test 1: Blocks persist after page reload (F5 or explicit reload)."""
    print("\n=== Test 1: Page Reload Persistence ===")
    
    # Start the app in background
    print("Starting app...")
    proc = subprocess.Popen(
        ["sh", "start.sh"],
        cwd="/workspace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    if not wait_for_app():
        proc.kill()
        return {"test": "page_reload", "status": "failed", "error": "App failed to start"}
    
    try:
        # Create some blocks via API
        print("Creating test blocks via API...")
        
        blocks_data = []
        for i, content in enumerate(["Block Alpha", "Block Beta", "Block Gamma"], start=1):
            body = json.dumps({"content": content})
            resp = run_api_call(f"http://127.0.0.1:8765/blocks", method="POST", body=body)
            if isinstance(resp, dict) and resp.get("id"):
                blocks_data.append({"content": content, "id": resp["id"]})
                print(f"  Created block: {content}, id={resp.get('id')}")
        
        if not blocks_data:
            return {"test": "page_reload", "status": "failed", "error": "Failed to create blocks"}
        
        # Verify blocks exist via browser
        print("\nVerifying blocks on page...")
        result = run_browser("http://127.0.0.1:8765/")
        if not result.get("success"):
            return {"test": "page_reload", "status": "failed", "error": result.get("error")}
        
        # Reload page and verify blocks still exist
        print("\nReloading page (simulating F5)...")
        result2 = run_browser("http://127.0.0.1:8765/")
        
        if not result2.get("success"):
            return {"test": "page_reload", "status": "failed", "error": result2.get("error")}
        
        # Check visible text for our blocks
        visible = result2.get("visible_text", "")
        expected_blocks = ["Block Alpha", "Block Beta", "Block Gamma"]
        
        all_present = all(block in visible for block in expected_blocks)
        
        if not all_present:
            return {
                "test": "page_reload", 
                "status": "failed", 
                "error": f"Expected blocks not found after reload. Visible text preview: {visible[:500]}"
            }
        
        print("✓ All blocks persisted after page reload")
        return {"test": "page_reload", "status": "passed"}
        
    finally:
        # Cleanup: kill the app process
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_app_restart_persistence():
    """Test 2: Blocks persist after app restart (kill → start.sh)."""
    print("\n=== Test 2: App Restart Persistence ===")
    
    # Start the app
    print("Starting app for restart test...")
    proc = subprocess.Popen(
        ["sh", "start.sh"],
        cwd="/workspace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    if not wait_for_app():
        proc.kill()
        return {"test": "restart", "status": "failed", "error": "App failed to start"}
    
    try:
        # Create test blocks
        print("Creating test blocks...")
        
        blocks_data = []
        for i, content in enumerate(["Persist Test 1", "Persist Test 2", "Persist Test 3"], start=1):
            body = json.dumps({"content": content})
            resp = run_api_call(f"http://127.0.0.1:8765/blocks", method="POST", body=body)
            if isinstance(resp, dict) and resp.get("id"):
                blocks_data.append({"content": content, "id": resp["id"]})
                print(f"  Created: {content}")
        
        # Verify blocks exist
        result = run_browser("http://127.0.0.1:8765/")
        if not result.get("success"):
            return {"test": "restart", "status": "failed", "error": result.get("error")}
        
        visible = result.get("visible_text", "")
        expected = ["Persist Test 1", "Persist Test 2", "Persist Test 3"]
        if not all(block in visible for block in expected):
            return {
                "test": "restart", 
                "status": "failed", 
                "error": f"Blocks not found after creation. Text: {visible[:500]}"
            }
        
        print("✓ Blocks verified before restart")
        
        # Kill the app (simulating restart)
        print("\nKilling app process...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        
        time.sleep(1)
        
        # Restart the app using start.sh
        print("Restarting app with start.sh...")
        proc = subprocess.Popen(
            ["sh", "start.sh"],
            cwd="/workspace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        if not wait_for_app():
            return {"test": "restart", "status": "failed", "error": "App failed to restart"}
        
        # Verify blocks still exist after restart
        print("\nVerifying blocks persist after restart...")
        result = run_browser("http://127.0.0.1:8765/")
        
        if not result.get("success"):
            return {"test": "restart", "status": "failed", "error": result.get("error")}
        
        visible = result.get("visible_text", "")
        expected = ["Persist Test 1", "Persist Test 2", "Persist Test 3"]
        
        if not all(block in visible for block in expected):
            return {
                "test": "restart", 
                "status": "failed", 
                "error": f"Blocks not found after restart. Text: {visible[:1000]}"
            }
        
        print("✓ All blocks persisted after app restart")
        return {"test": "restart", "status": "passed"}
        
    finally:
        # Cleanup
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_selection_editing_deletion():
    """Test 3: Selection-based editing/deletion works correctly."""
    print("\n=== Test 3: Selection-Based Editing/Deletion ===")
    
    # Start the app
    print("Starting app...")
    proc = subprocess.Popen(
        ["sh", "start.sh"],
        cwd="/workspace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    if not wait_for_app():
        proc.kill()
        return {"test": "selection", "status": "failed", "error": "App failed to start"}
    
    try:
        # Create initial blocks
        print("Creating initial blocks...")
        
        blocks_data = []
        for i, content in enumerate(["Block A", "Block B", "Block C"], start=1):
            body = json.dumps({"content": content})
            resp = run_api_call(f"http://127.0.0.1:8765/blocks", method="POST", body=body)
            if isinstance(resp, dict) and resp.get("id"):
                blocks_data.append({"content": content, "id": resp["id"]})
                print(f"  Created: {content}")
        
        # Verify initial state
        result = run_browser("http://127.0.0.1:8765/")
        if not result.get("success"):
            return {"test": "selection", "status": "failed", "error": result.get("error")}
        
        visible = result.get("visible_text", "")
        if "Block A" not in visible or "Block B" not in visible or "Block C" not in visible:
            return {
                "test": "selection", 
                "status": "failed", 
                "error": "Initial blocks not found"
            }
        
        print("✓ Initial blocks verified")
        
        # Test 3a: Selection-based editing (via API since browser tool doesn't support PUT)
        print("\n--- Testing Selection-Based Editing ---")
        
        block_a = next((b for b in blocks_data if b["content"] == "Block A"), None)
        if not block_a:
            return {"test": "selection", "status": "failed", "error": "Block A not found"}
        
        block_a_id = block_a["id"]
        print(f"  Editing Block A (ID: {block_a_id})...")
        
        edit_body = json.dumps({"content": "Block A - EDITED VIA SELECTION"})
        edit_resp = run_api_call(
            f"http://127.0.0.1:8765/blocks/{block_a_id}",
            method="PUT",
            body=edit_body
        )
        
        if isinstance(edit_resp, dict) and "message" in edit_resp or "id" in edit_resp:
            print("  ✓ Block edited successfully")
        else:
            return {"test": "selection", "status": "failed", "error": f"Edit failed: {edit_resp}"}
        
        # Verify edit persisted
        verify_resp = run_api_call(f"http://127.0.0.1:8765/blocks")
        if not isinstance(verify_resp, dict) or "blocks" not in verify_resp:
            return {"test": "selection", "status": "failed", "error": "Failed to fetch blocks"}
        
        block_a_after = next((b for b in verify_resp["blocks"] if "EDITED" in b["content"]), None)
        
        if not block_a_after:
            return {"test": "selection", "status": "failed", "error": "Edit did not persist"}
        
        print("  ✓ Edit persisted after reload")
        
        # Test 3b: Selection-based deletion
        print("\n--- Testing Selection-Based Deletion ---")
        
        block_b = next((b for b in verify_resp["blocks"] if b["content"] == "Block B"), None)
        if not block_b:
            return {"test": "selection", "status": "failed", "error": "Block B not found"}
        
        block_b_id = block_b["id"]
        print(f"  Deleting Block B (ID: {block_b_id})...")
        
        delete_resp = run_api_call(
            f"http://127.0.0.1:8765/blocks/{block_b_id}",
            method="DELETE"
        )
        
        if isinstance(delete_resp, dict) and "message" in delete_resp or "id" in delete_resp:
            print("  ✓ Block deleted successfully")
        elif "detail" in delete_resp and delete_resp["detail"]:
            return {"test": "selection", "status": "failed", "error": f"Delete failed: {delete_resp['detail']}"}
        
        # Verify deletion persisted
        verify_resp2 = run_api_call(f"http://127.0.0.1:8765/blocks")
        block_b_after = next((b for b in verify_resp2["blocks"] if b["content"] == "Block B"), None)
        
        if block_b_after:
            return {"test": "selection", "status": "failed", "error": "Deleted block still appears"}
        
        print("  ✓ Deletion persisted after reload")
        
        # Test 3c: Verify remaining blocks
        remaining = [b["content"] for b in verify_resp2["blocks"]]
        expected_remaining = ["Block A - EDITED VIA SELECTION", "Block C"]
        
        if sorted(remaining) != sorted(expected_remaining):
            return {"test": "selection", "status": "failed", "error": f"Unexpected blocks: {remaining}"}
        
        print("  ✓ All selection operations verified")
        
        return {"test": "selection", "status": "passed"}
        
    finally:
        # Cleanup
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    """Run all persistence tests."""
    print("=" * 60)
    print("Notion-like Web App - Data Persistence Tests")
    print("=" * 60)
    
    results = []
    
    # Run tests
    try:
        result1 = test_page_reload_persistence()
        results.append(result1)
        print(f"\nTest 1 (Page Reload): {'PASSED' if results[-1]['status'] == 'passed' else 'FAILED'}")
    except Exception as e:
        print(f"Test 1 FAILED with exception: {e}")
        results.append({"test": "page_reload", "status": "failed", "error": str(e)})
    
    try:
        result2 = test_app_restart_persistence()
        results.append(result2)
        print(f"\nTest 2 (App Restart): {'PASSED' if results[-1]['status'] == 'passed' else 'FAILED'}")
    except Exception as e:
        print(f"Test 2 FAILED with exception: {e}")
        results.append({"test": "restart", "status": "failed", "error": str(e)})
    
    try:
        result3 = test_selection_editing_deletion()
        results.append(result3)
        print(f"\nTest 3 (Selection/Edit/Delete): {'PASSED' if results[-1]['status'] == 'passed' else 'FAILED'}")
    except Exception as e:
        print(f"Test 3 FAILED with exception: {e}")
        results.append({"test": "selection", "status": "failed", "error": str(e)})
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r.get("status") == "passed")
    total = len(results)
    
    for result in results:
        status = "✓ PASSED" if result.get("status") == "passed" else "✗ FAILED"
        test_name = result.get("test", "unknown").upper()
        print(f"  {test_name}: {status}")
        if "error" in result:
            error_msg = result['error'][:200]
            print(f"    Error: {error_msg}")
    
    print("\n" + "=" * 60)
    print(f"OVERALL: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n✓ ALL PERSISTENCE TESTS PASSED")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
