import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

ES_URL = "https://my-elasticsearch-project-ec7710.es.us-central1.gcp.elastic.cloud"
ES_API_KEY = "a1J2VmE1d0JsN1hBRFhpS255YXo6dXZWNjV6VkFZV2l3RXVVRUFCbDQ3UQ=="
ES_INDEX = "tax-decisions"

# ============================================================================
# LIST ALL DOCUMENTS
# ============================================================================

def list_all_documents():
    """List all document file names in Elasticsearch"""
    url = f"{ES_URL}/{ES_INDEX}/_search"
    
    query = {
        "size": 10000,  # Get up to 10,000 documents
        "query": {
            "match_all": {}
        },
        "_source": ["fileName"]  # Only return fileName field
    }
    
    try:
        response = requests.post(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"ApiKey {ES_API_KEY}"
            },
            json=query,
            verify=True,
            timeout=60
        )
        
        response.raise_for_status()
        data = response.json()
        
        files = []
        if "hits" in data and "hits" in data["hits"]:
            for hit in data["hits"]["hits"]:
                if "_source" in hit and "fileName" in hit["_source"]:
                    files.append(hit["_source"]["fileName"])
        
        return files
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return []


# ============================================================================
# MAIN
# ============================================================================

print("="*70)
print("ELASTICSEARCH - LIST ALL DOCUMENTS")
print("="*70)
print(f"Index: {ES_INDEX}")
print(f"URL: {ES_URL}")
print("="*70)
print()

print("Fetching documents...")
all_files = list_all_documents()

print(f"\nFound {len(all_files)} documents in Elasticsearch\n")

if len(all_files) > 0:
    print("All files:")
    print("-" * 70)
    for i, file in enumerate(all_files, 1):
        print(f"{i:3d}. {file}")
    print("-" * 70)
else:
    print("No documents found!")

print(f"\nTotal: {len(all_files)} documents")