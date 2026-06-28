#!/usr/bin/env python3
"""Quick API verification tests for Notion-like app."""

import requests
import json

BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api"
AUTH_TOKEN = None


def get_token():
    """Get authentication token by logging in."""
    global AUTH_TOKEN
    
    response = requests.post(f"{API_BASE}/auth/login", json={
        "username": "demo_user",
        "remember_me": True
    })
    
    if response.status_code == 200:
        data = response.json()
        AUTH_TOKEN = data.get("token")
        print(f"✓ Got auth token (will be used for subsequent requests)")
    else:
        print(f"✗ Failed to get auth token: {response.text}")


def test_health():
    """Test health endpoint."""
    response = requests.get(f"{BASE_URL}/health")
    
    if response.status_code == 200 and response.json().get("status") == "ok":
        print("✓ Health check passed")
        return True
    else:
        print(f"✗ Health check failed: {response.text}")
        return False


def test_create_page():
    """Test creating a page."""
    global AUTH_TOKEN
    
    if not AUTH_TOKEN:
        get_token()
    
    response = requests.post(
        f"{API_BASE}/pages",
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
        json={
            "title": "My Test Page",
            "content": "",
            "parent_page_id": None
        }
    )
    
    if response.status_code == 201:
        data = response.json()
        page_id = data.get("id")
        print(f"✓ Created page with ID {page_id}")
        
        # Store for subsequent tests
        current_page_id = int(page_id)
        
        return current_page_id
    else:
        print(f"✗ Failed to create page: {response.text}")
        return None


def test_get_pages():
    """Test listing all pages."""
    response = requests.get(f"{API_BASE}/pages?per_page=10")
    
    if response.status_code == 200 and "pages" in response.json():
        print("✓ Listing pages works")
        return True
    else:
        print(f"✗ Failed to list pages: {response.text}")
        return False


def test_get_page_with_blocks(current_page_id):
    """Test getting a page with its blocks."""
    if not current_page_id:
        response = requests.get(f"{API_BASE}/pages?per_page=1")
        data = response.json()
        pages = data.get("pages", [])
        if pages:
            current_page_id = int(pages[0]["id"])
    
    response = requests.get(f"{API_BASE}/pages/{current_page_id}")
    
    if response.status_code == 200 and "blocks" in response.json():
        print("✓ Getting page with blocks works")
        return True
    else:
        print(f"✗ Failed to get page with blocks: {response.text}")
        return False


def test_create_block(current_page_id):
    """Test creating a block for a page."""
    if not current_page_id:
        response = requests.get(f"{API_BASE}/pages?per_page=1")
        data = response.json()
        pages = data.get("pages", [])
        if pages:
            current_page_id = int(pages[0]["id"])
    
    global AUTH_TOKEN
    
    if not AUTH_TOKEN:
        get_token()
    
    response = requests.post(
        f"{API_BASE}/pages/{current_page_id}/blocks",
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
        json={
            "type": "paragraph",
            "data": {}
        }
    )
    
    if response.status_code == 201:
        print("✓ Creating block works")
        return True
    else:
        print(f"✗ Failed to create block: {response.text}")
        return False


def test_update_block(current_page_id):
    """Test updating a block."""
    if not current_page_id:
        response = requests.get(f"{API_BASE}/pages?per_page=1")
        data = response.json()
        pages = data.get("pages", [])
        if pages:
            current_page_id = int(pages[0]["id"])
    
    # Get blocks first to find one to update
    block_response = requests.get(f"{API_BASE}/pages/{current_page_id}/blocks")
    if not block_response.ok:
        print("✗ Cannot get blocks, skipping update test")
        return None
    
    blocks_data = block_response.json()
    
    global AUTH_TOKEN
    
    if not AUTH_TOKEN:
        get_token()
    
    # Update first block to heading_1
    block_id = blocks_data["blocks"][0]["id"]
    
    response = requests.put(
        f"{API_BASE}/pages/{current_page_id}/blocks/{block_id}",
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
        json={
            "type": "heading_1",
            "data": {"title": "Updated Heading"}
        }
    )
    
    if response.status_code == 200:
        print("✓ Updating block works")
        return True
    else:
        print(f"✗ Failed to update block: {response.text}")
        return False


def test_delete_block(current_page_id):
    """Test deleting a block."""
    if not current_page_id:
        response = requests.get(f"{API_BASE}/pages?per_page=1")
        data = response.json()
        pages = data.get("pages", [])
        if pages:
            current_page_id = int(pages[0]["id"])
    
    # Get blocks first to find one to delete
    block_response = requests.get(f"{API_BASE}/pages/{current_page_id}/blocks")
    if not block_response.ok:
        print("✗ Cannot get blocks, skipping delete test")
        return None
    
    blocks_data = block_response.json()
    
    global AUTH_TOKEN
    
    if not AUTH_TOKEN:
        get_token()
    
    # Delete first block
    block_id = blocks_data["blocks"][0]["id"]
    
    response = requests.delete(
        f"{API_BASE}/pages/{current_page_id}/blocks/{block_id}"
    )
    
    if response.status_code == 200:
        print("✓ Deleting block works")
        return True
    else:
        print(f"✗ Failed to delete block: {response.text}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Notion-like App - API Verification Tests")
    print("=" * 60)
    
    results = []
    
    # Test health endpoint first (no auth needed)
    if not test_health():
        return
    
    print()
    
    # Get token for authenticated tests
    get_token()
    
    if AUTH_TOKEN:
        current_page_id = None
        
        # Create a page to work with
        current_page_id = test_create_page()
        
        if current_page_id is not None:
            results.append(("Create Page", True))
            
            print()
            print("--- Testing Block Operations ---")
            print()
            
            # Test get blocks (implicit in create)
            test_get_page_with_blocks(current_page_id)
            results.append(("Get Pages & Blocks", True))
            
            # Create another block for testing updates/deletes
            if test_create_block(current_page_id):
                print()
                
                # Test update block
                test_update_block(current_page_id)
                results.append(("Update Block", True))
                
                # Delete a block
                test_delete_block(current_page_id)
                results.append(("Delete Block", True))
    else:
        print("Failed to get auth token, skipping authenticated tests")


def summary(results):
    """Print test summary."""
    if not results:
        return
    
    passed = sum(1 for _, status in results if status is True)
    total = len([r for r in results if r[0] != "Create Page"])  # Don't count create page as separate pass/fail
    
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, status in results:
        symbol = "✓" if status else "✗"
        print(f"{symbol} {name}")
    
    # Calculate overall pass rate excluding create page test (it's a setup step)
    completed_tests = [r for r in results if r[0] != "Create Page"]
    passed_completed = sum(1 for _, status in completed_tests if status is True)
    
    print()
    print(f"Passed: {passed_completed}/{len(completed_completed)} tests")


if __name__ == "__main__":
    main()
