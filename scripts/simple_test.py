import requests
import time
import sys

def test_api_endpoints():
    """Test if the API endpoints are accessible"""
    base_url = "http://localhost:8000"
    
    endpoints = [
        "/",  # Root endpoint
        "/documents/list",  # Document listing
        "/diagnostics/vector-index"  # Vector index diagnostics
    ]
    
    print("Testing API endpoints...")
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"\nTesting: {url}")
        
        try:
            start_time = time.time()
            response = requests.get(url)
            elapsed = time.time() - start_time
            
            print(f"Status code: {response.status_code}")
            print(f"Response time: {elapsed:.2f} seconds")
            
            if response.ok:
                try:
                    print(f"Response data: {response.json()}")
                except:
                    print(f"Response text: {response.text[:500]}")  # First 500 chars
            else:
                print(f"Error response: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("Connection failed - server may not be running")
        except Exception as e:
            print(f"Error: {str(e)}")
    
    print("\nAPI test complete.")

if __name__ == "__main__":
    test_api_endpoints()