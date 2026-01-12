#!/usr/bin/env python3
import requests
import json
import time

API_URL = "http://localhost:8000/api/v1"
API_KEY = "sk_live_123456" # Replace with valid key if needed, or rely on mock auth if available

def test_get_json_response():
    print(f"\n--- Testing GET /take with response_type=json ---")
    
    # We need a valid API key for this to work generally, 
    # but we can try hitting it and see 401 response which implies endpoint exists at least.
    # If we have a key, we get 200.
    
    params = {
        "url": "https://example.com",
        "response_type": "json",
        "access_key": API_KEY 
    }
    
    try:
        resp = requests.get(f"{API_URL}/renders/take", params=params, timeout=10)
        
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print("Response JSON keys:", data.keys())
            if "url" in data and "screenshot_url" in data:
                print("✅ Success: JSON response received with URL")
            else:
                print("❌ Failed: API returned JSON but missing 'url' key")
        elif resp.status_code == 401:
            print("ℹ️ Auth failed (Expected if no valid key). Endpoint signature seems compatible though.")
        else:
            print(f"❌ Failed: Unexpected status code {resp.status_code}")
            print("Response:", resp.text)
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def test_capture_beyond_viewport_param():
    print(f"\n--- Testing GET /take with capture_beyond_viewport=true ---")
    
    params = {
        "url": "https://example.com",
        "capture_beyond_viewport": "true",
        "access_key": API_KEY
    }
    
    try:
        resp = requests.get(f"{API_URL}/renders/take", params=params, timeout=10)
        print(f"Status Code: {resp.status_code}")
        # We can't easily verify the EFFECT of this param without analyzing the image
        # But we can verify it doesn't cause a 422 Validation Error
        if resp.status_code == 200:
             print("✅ Success: Request with capture_beyond_viewport accepted")
        elif resp.status_code == 422:
             print("❌ Failed: 422 Unprocessable Entity - Param might not be defined in Schema")
             print(resp.json())
        else:
             print(f"ℹ️ Status: {resp.status_code} (Auth failed or other error)")

    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    print("Verifying API features on localhost:8000...")
    test_get_json_response()
    test_capture_beyond_viewport_param()
