#!/usr/bin/env python3
"""
Test script for Sentindex API.

Tests all major endpoints and functionality.
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta


class SentindexAPITester:
    """Test client for Sentindex API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def test_health(self):
        """Test health endpoint."""
        print("Testing health endpoint...")
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            print(f"✓ Health check passed: {data['status']}")
            return True
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return False
    
    async def test_root(self):
        """Test root endpoint."""
        print("Testing root endpoint...")
        try:
            response = await self.client.get(f"{self.base_url}/")
            response.raise_for_status()
            data = response.json()
            print(f"✓ Root endpoint: {data['name']} v{data['version']}")
            return True
        except Exception as e:
            print(f"✗ Root endpoint failed: {e}")
            return False
    
    async def test_metrics(self):
        """Test metrics endpoint."""
        print("Testing metrics endpoint...")
        try:
            response = await self.client.get(f"{self.base_url}/metrics")
            response.raise_for_status()
            print("✓ Metrics endpoint accessible")
            return True
        except Exception as e:
            print(f"✗ Metrics endpoint failed: {e}")
            return False
    
    async def test_latest_index(self, index_name: str = "gold_silver_oil_crypto"):
        """Test latest index endpoint."""
        print(f"Testing latest index endpoint for {index_name}...")
        try:
            response = await self.client.get(f"{self.base_url}/v1/index/{index_name}/latest")
            if response.status_code == 404:
                print(f"⚠ Index {index_name} not found (expected if no data yet)")
                return True
            response.raise_for_status()
            data = response.json()
            print(f"✓ Latest index: {data['index_value']} ({data['method']})")
            return True
        except Exception as e:
            print(f"✗ Latest index failed: {e}")
            return False
    
    async def test_index_history(self, index_name: str = "gold_silver_oil_crypto"):
        """Test index history endpoint."""
        print(f"Testing index history endpoint for {index_name}...")
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            params = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "limit": 100
            }
            
            response = await self.client.get(
                f"{self.base_url}/v1/index/{index_name}/history",
                params=params
            )
            if response.status_code == 404:
                print(f"⚠ Index {index_name} not found (expected if no data yet)")
                return True
            response.raise_for_status()
            data = response.json()
            print(f"✓ Index history: {data['count']} records")
            return True
        except Exception as e:
            print(f"✗ Index history failed: {e}")
            return False
    
    async def test_compute_index(self, index_name: str = "gold_silver_oil_crypto"):
        """Test compute index endpoint."""
        print(f"Testing compute index endpoint for {index_name}...")
        try:
            # Test data
            test_prices = {
                "GOLD": 1900.12,
                "SILVER": 24.31,
                "OIL": 78.45,
                "BTC": 27450.0,
                "ETH": 1850.0
            }
            
            request_data = {
                "index_name": index_name,
                "prices": test_prices,
                "method": "level_normalized"
            }
            
            response = await self.client.post(
                f"{self.base_url}/v1/index/{index_name}/compute",
                json=request_data
            )
            response.raise_for_status()
            data = response.json()
            print(f"✓ Index computed: {data['index_value']}")
            return True
        except Exception as e:
            print(f"✗ Compute index failed: {e}")
            return False
    
    async def test_insights(self, index_name: str = "gold_silver_oil_crypto"):
        """Test insights endpoint."""
        print(f"Testing insights endpoint for {index_name}...")
        try:
            response = await self.client.get(f"{self.base_url}/v1/index/{index_name}/insights")
            if response.status_code == 404:
                print(f"⚠ No insights found for {index_name} (expected if no data yet)")
                return True
            response.raise_for_status()
            data = response.json()
            print(f"✓ Insights retrieved: {len(data.get('insights', {}))} fields")
            return True
        except Exception as e:
            print(f"✗ Insights failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests."""
        print("=" * 50)
        print("Sentindex API Test Suite")
        print("=" * 50)
        
        tests = [
            self.test_health,
            self.test_root,
            self.test_metrics,
            self.test_latest_index,
            self.test_index_history,
            self.test_compute_index,
            self.test_insights
        ]
        
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
            except Exception as e:
                print(f"✗ Test {test.__name__} crashed: {e}")
                results.append(False)
            print()
        
        # Summary
        passed = sum(results)
        total = len(results)
        
        print("=" * 50)
        print(f"Test Results: {passed}/{total} passed")
        print("=" * 50)
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print("⚠ Some tests failed. Check the output above.")
        
        return passed == total
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def main():
    """Main test function."""
    tester = SentindexAPITester()
    
    try:
        success = await tester.run_all_tests()
        exit(0 if success else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
