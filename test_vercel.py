#!/usr/bin/env python3
"""
Test script for the Vercel deployment.
"""

import requests
import json

def test_api():
    base_url = "https://sentindex-js7xg1ihk-avins-projects-94a43281.vercel.app"
    
    print("🧪 Testing Sentindex API on Vercel...")
    print(f"URL: {base_url}")
    print()
    
    # Test 1: Root endpoint
    try:
        print("1️⃣ Testing root endpoint...")
        response = requests.get(f"{base_url}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Root endpoint working: {data['name']} v{data['version']}")
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Root endpoint error: {e}")
    
    print()
    
    # Test 2: Health check
    try:
        print("2️⃣ Testing health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data['status']}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    print()
    
    # Test 3: Index calculation
    try:
        print("3️⃣ Testing index calculation...")
        payload = {
            "index_name": "gold_silver_oil_crypto",
            "prices": {
                "GOLD": 1900.12,
                "SILVER": 24.31,
                "OIL": 78.45,
                "BTC": 27450.0,
                "ETH": 1850.0
            },
            "method": "level_normalized"
        }
        
        response = requests.post(
            f"{base_url}/v1/index/gold_silver_oil_crypto/compute",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Index calculation working: {data['index_value']}")
        else:
            print(f"❌ Index calculation failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Index calculation error: {e}")
    
    print()
    
    # Test 4: Insights endpoint
    try:
        print("4️⃣ Testing insights endpoint...")
        response = requests.get(f"{base_url}/v1/index/gold_silver_oil_crypto/insights", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Insights endpoint working: {data['message']}")
        else:
            print(f"❌ Insights endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Insights endpoint error: {e}")
    
    print()
    print("🎉 API testing complete!")

if __name__ == "__main__":
    test_api()
