"""
Test BrightData proxy connection
"""
import os
import asyncio
import aiohttp

PROXY_URL = os.getenv("PROXY_URL")

async def test_proxy():
    print("Testing BrightData proxy connection...")
    print(f"Proxy: {PROXY_URL[:50]}...")
    
    # Test 1: BrightData test endpoint
    print("\n1. Testing BrightData endpoint...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://geo.brdtest.com/welcome.txt",
                proxy=PROXY_URL,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                text = await r.text()
                print(f"   Status: {r.status}")
                print(f"   Response: {text[:100]}")
        except Exception as e:
            print(f"   ERROR: {e}")
    
    # Test 2: Polymarket API through proxy
    print("\n2. Testing Polymarket API through proxy...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://data-api.polymarket.com/traded",
                params={"user": "0x56687bf447db6ffa42ffe2204a05edaa20f55839"},
                proxy=PROXY_URL,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                data = await r.json()
                print(f"   Status: {r.status}")
                print(f"   Response: {data}")
        except Exception as e:
            print(f"   ERROR: {e}")
    
    # Test 3: Multiple concurrent requests (test IP rotation)
    print("\n3. Testing 5 concurrent requests (should get different IPs)...")
    async with aiohttp.ClientSession() as session:
        async def get_ip():
            try:
                async with session.get(
                    "https://lumtest.com/myip.json",
                    proxy=PROXY_URL,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as r:
                    data = await r.json()
                    return data.get("ip", "unknown")
            except Exception as e:
                return f"error: {e}"
        
        tasks = [get_ip() for _ in range(5)]
        ips = await asyncio.gather(*tasks)
        for i, ip in enumerate(ips, 1):
            print(f"   Request {i}: {ip}")
        
        unique_ips = len(set(ips))
        print(f"\n   Unique IPs: {unique_ips}/5 (rotating proxy working: {unique_ips > 1})")
    
    print("\nProxy test complete!")

if __name__ == "__main__":
    asyncio.run(test_proxy())
