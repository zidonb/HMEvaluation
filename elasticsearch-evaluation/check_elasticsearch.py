import requests
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

ES_URL = "https://my-elasticsearch-project-ec7710.es.us-central1.gcp.elastic.cloud"
ES_API_KEY = "a1J2VmE1d0JsN1hBRFhpS255YXo6dXZWNjV6VkFZV2l3RXVVRUFCbDQ3UQ=="

# ============================================================================
# CHECK ELASTICSEARCH
# ============================================================================

def check_connection():
    """Check if we can connect to Elasticsearch"""
    url = f"{ES_URL}/"
    
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"ApiKey {ES_API_KEY}"
            },
            verify=True,
            timeout=10
        )
        
        response.raise_for_status()
        data = response.json()
        
        print("✅ Connection successful!")
        print(f"   Cluster: {data.get('cluster_name', 'Unknown')}")
        print(f"   Version: {data.get('version', {}).get('number', 'Unknown')}")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False


def list_all_indices():
    """List all indices in Elasticsearch"""
    url = f"{ES_URL}/_cat/indices?format=json&v"
    
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"ApiKey {ES_API_KEY}"
            },
            verify=True,
            timeout=10
        )
        
        response.raise_for_status()
        indices = response.json()
        
        return indices
        
    except Exception as e:
        print(f"❌ Error listing indices: {str(e)}")
        return []


def check_index_exists(index_name):
    """Check if a specific index exists"""
    url = f"{ES_URL}/{index_name}"
    
    try:
        response = requests.head(
            url,
            headers={
                "Authorization": f"ApiKey {ES_API_KEY}"
            },
            verify=True,
            timeout=10
        )
        
        return response.status_code == 200
        
    except Exception as e:
        return False


def get_index_info(index_name):
    """Get detailed info about an index"""
    url = f"{ES_URL}/{index_name}/_stats"
    
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"ApiKey {ES_API_KEY}"
            },
            verify=True,
            timeout=10
        )
        
        response.raise_for_status()
        data = response.json()
        
        total_docs = data.get('_all', {}).get('primaries', {}).get('docs', {}).get('count', 0)
        return total_docs
        
    except Exception as e:
        print(f"Error getting index info: {str(e)}")
        return None


# ============================================================================
# MAIN
# ============================================================================

print("="*70)
print("ELASTICSEARCH CLUSTER INSPECTION")
print("="*70)
print(f"URL: {ES_URL}")
print("="*70)
print()

# 1. Check connection
print("1. Testing connection...")
if not check_connection():
    print("\n❌ Cannot connect to Elasticsearch. Exiting.")
    exit(1)
print()

# 2. List all indices
print("2. Listing all indices...")
indices = list_all_indices()

if len(indices) > 0:
    print(f"   Found {len(indices)} indices:\n")
    print(f"   {'Index Name':<40} {'Docs Count':<15} {'Size'}")
    print("   " + "-"*65)
    for idx in indices:
        index_name = idx.get('index', 'Unknown')
        docs_count = idx.get('docs.count', '0')
        store_size = idx.get('store.size', '0')
        print(f"   {index_name:<40} {docs_count:<15} {store_size}")
else:
    print("   ⚠️  No indices found!")
print()

# 3. Check if tax-decisions exists
print("3. Checking if 'tax-decisions' index exists...")
if check_index_exists('tax-decisions'):
    print("   ✅ 'tax-decisions' index EXISTS")
    
    doc_count = get_index_info('tax-decisions')
    if doc_count is not None:
        print(f"   📊 Documents in index: {doc_count}")
        if doc_count == 0:
            print("   ⚠️  Index exists but is EMPTY")
else:
    print("   ❌ 'tax-decisions' index DOES NOT EXIST")
    print("   💡 You need to create it and run ingestion")

print()
print("="*70)
print("INSPECTION COMPLETE")
print("="*70)