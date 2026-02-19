import requests
import pandas as pd
from sentence_transformers import SentenceTransformer
import torch

# ============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================================

# Elasticsearch credentials
ES_URL = "https://my-elasticsearch-project-ec7710.es.us-central1.gcp.elastic.cloud"
ES_API_KEY = "a1J2VmE1d0JsN1hBRFhpS255YXo6dXZWNjV6VkFZV2l3RXVVRUFCbDQ3UQ=="
ES_INDEX = "tax-decisions"

# Embedding model
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"

# Search parameters
SEARCH_SIZE = 20  # Number of documents to retrieve
NUM_CANDIDATES = 100
K = 25
K_METRIC = 3  # For Hit@3 calculation

# ============================================================================
# LOAD EMBEDDING MODEL
# ============================================================================

print("Loading embedding model...")
embedding_model = SentenceTransformer(
    model_name_or_path=EMBEDDING_MODEL,
    device="cuda" if torch.cuda.is_available() else "cpu"
)
print(f"Model loaded on: {'GPU' if torch.cuda.is_available() else 'CPU'}\n")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_embeddings(text):
    """Create embeddings for text using the model."""
    embeddings = embedding_model.encode(text, convert_to_tensor=False)
    return embeddings.tolist()


def search_elasticsearch(query: str):
    """
    Search Elasticsearch with vector similarity.
    Replicates the logic from app_search.py
    """
    # Create query embeddings
    query_embeddings = create_embeddings(query)
    
    # Build Elasticsearch query
    elasticsearch_query = {
        "size": SEARCH_SIZE,
        "knn": {
            "query_vector": query_embeddings,
            "field": "chunks.vector",
            "k": K,
            "num_candidates": NUM_CANDIDATES
        },
        "rescore": {
            "window_size": K,
            "query": {
                "rescore_query": {
                    "nested": {
                        "path": "chunks",
                        "query": {
                            "script_score": {
                                "query": {
                                    "match_all": {}
                                },
                                "script": {
                                    "source": "cosineSimilarity(params.query_vector, 'chunks.vector') + 1.0",
                                    "params": {
                                        "query_vector": query_embeddings
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Send query to Elasticsearch
    url = f"{ES_URL}/{ES_INDEX}/_search"
    
    try:
        response = requests.post(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"ApiKey {ES_API_KEY}"
            },
            json=elasticsearch_query,
            verify=True,
            timeout=60
        )
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"    ERROR querying Elasticsearch: {str(e)}")
        return None


# ============================================================================
# MAIN EVALUATION
# ============================================================================

print("="*70)
print("ELASTICSEARCH RAG EVALUATION")
print("="*70)
print(f"Elasticsearch: {ES_URL}")
print(f"Index: {ES_INDEX}")
print(f"Search size: {SEARCH_SIZE}")
print(f"Embedding model: {EMBEDDING_MODEL}")
print("="*70)
print()

# Read the Excel file (from QnA sheet)
print("Reading Excel file...")
df = pd.read_excel('mapping.xlsx', sheet_name='QnA')
print(f"Loaded {len(df)} questions\n")

# Prepare results storage
results = []
total_rr = 0
total_hit_at_3 = 0
total_hit_overall = 0

print("Starting evaluation...\n")

# Iterate through each row
for idx, row in df.iterrows():
    document_name = row['Document_Name']
    category = row['Category']
    question_level = row['Question Level']
    question = row['Question']
    expected_answer = row['Answer']
    
    print(f"[{idx + 1}/{len(df)}] {document_name}")
    print(f"  Question: {question[:80]}...")
    
    try:
        # Search Elasticsearch
        response_data = search_elasticsearch(question)
        
        if response_data is None:
            raise Exception("No response from Elasticsearch")
        
        # Extract file names from hits
        retrieved_files = []
        if "hits" in response_data and "hits" in response_data["hits"]:
            for hit in response_data["hits"]["hits"]:
                if "_source" in hit and "fileName" in hit["_source"]:
                    file_name = hit["_source"]["fileName"]
                    retrieved_files.append(file_name)
        
        # DEBUG: Print first result to understand format
        if idx == 0 and len(retrieved_files) > 0:
            print(f"\n  DEBUG - First file name from Elasticsearch:")
            print(f"    Raw value: {repr(retrieved_files[0])}")
            print(f"    Expected: {repr(document_name)}\n")
        
        total_resources_returned = len(retrieved_files)
        
        # Remove file extension from document name for comparison
        document_name_without_ext = document_name.replace('.pdf', '').replace('.docx', '').replace('.doc', '')
        
        # Find if document_name is in retrieved_files and at what position
        position = None
        for i, file_name in enumerate(retrieved_files):
            # Extract just the filename from potential path
            if '\\' in file_name:
                file_name_only = file_name.split('\\')[-1]
            elif '/' in file_name:
                file_name_only = file_name.split('/')[-1]
            else:
                file_name_only = file_name
            
            # Remove extension for comparison
            file_name_without_ext = file_name_only.replace('.pdf', '').replace('.docx', '').replace('.doc', '')
            
            # Check if document name matches
            if document_name_without_ext.lower() in file_name_without_ext.lower():
                position = i + 1  # 1-indexed position
                break
        
        # Calculate metrics
        if position:
            reciprocal_rank = 1.0 / position
            hit_at_k = 1 if position <= K_METRIC else 0
            hit_overall = 1
            match_info = f"{position}{'st' if position == 1 else 'nd' if position == 2 else 'rd' if position == 3 else 'th'} match"
        else:
            reciprocal_rank = 0.0
            hit_at_k = 0
            hit_overall = 0
            match_info = "Not found"
        
        total_rr += reciprocal_rank
        total_hit_at_3 += hit_at_k
        total_hit_overall += hit_overall
        
        # Store results
        result = {
            'Document_Name': document_name,
            'Category': category,
            'Question_Level': question_level,
            'Question': question,
            'Expected_Answer': expected_answer,
            'Position': position if position else 'Not found',
            'Total_Resources_Returned': total_resources_returned,
            'Reciprocal_Rank': reciprocal_rank,
            'RR_Percentage': f"{reciprocal_rank * 100:.1f}%",
            'Hit@3': 'Yes' if hit_at_k else 'No',
            'Hit_Overall': 'Yes' if hit_overall else 'No',
            'Match_Info': match_info,
            'Retrieved_Files': ', '.join([f.split('\\')[-1].split('/')[-1] for f in retrieved_files[:10]])
        }
        results.append(result)
        
        # Print progress
        print(f"  Result: MRR: {reciprocal_rank:.2f} | Hit@3: {'Yes' if hit_at_k else 'No'} | {match_info} | Total: {total_resources_returned}")
        print()
        
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        print()
        
        # Store error result
        result = {
            'Document_Name': document_name,
            'Category': category,
            'Question_Level': question_level,
            'Question': question,
            'Expected_Answer': expected_answer,
            'Position': 'Error',
            'Total_Resources_Returned': 0,
            'Reciprocal_Rank': 0.0,
            'RR_Percentage': '0.0%',
            'Hit@3': 'No',
            'Hit_Overall': 'No',
            'Match_Info': f'Error: {str(e)}',
            'Retrieved_Files': ''
        }
        results.append(result)

# Calculate final metrics
num_questions = len(df)
mrr = total_rr / num_questions if num_questions > 0 else 0
hit_at_3_rate = (total_hit_at_3 / num_questions) * 100 if num_questions > 0 else 0
hit_overall_rate = (total_hit_overall / num_questions) * 100 if num_questions > 0 else 0

# Print summary
print("\n" + "="*70)
print(f"EVALUATION SUMMARY ({num_questions} questions)")
print("="*70)
print(f"Mean Reciprocal Rank (MRR): {mrr:.3f} ({mrr*100:.1f}%)")
print(f"Hit@3 Rate: {hit_at_3_rate:.1f}% ({total_hit_at_3}/{num_questions})")
print(f"Hit Rate (Overall): {hit_overall_rate:.1f}% ({total_hit_overall}/{num_questions})")
print("="*70)

# Create results DataFrame
results_df = pd.DataFrame(results)

# Add summary rows
summary_data = {
    'Document_Name': ['', 'SUMMARY'],
    'Category': ['', 'ALL'],
    'Question_Level': ['', 'ALL'],
    'Question': ['', f'{num_questions} questions evaluated'],
    'Expected_Answer': ['', ''],
    'Position': ['', ''],
    'Total_Resources_Returned': ['', ''],
    'Reciprocal_Rank': ['', mrr],
    'RR_Percentage': ['', f"{mrr*100:.1f}%"],
    'Hit@3': ['', f"{hit_at_3_rate:.1f}%"],
    'Hit_Overall': ['', f"{hit_overall_rate:.1f}%"],
    'Match_Info': ['', f"MRR: {mrr:.3f}, Hit@3: {total_hit_at_3}/{num_questions}, Hit Overall: {total_hit_overall}/{num_questions}"],
    'Retrieved_Files': ['', '']
}
summary_df = pd.DataFrame(summary_data)
results_df = pd.concat([results_df, summary_df], ignore_index=True)

# Write to Excel
output_filename = 'elasticsearch_evaluation_results.xlsx'
results_df.to_excel(output_filename, index=False)

print(f"\nResults saved to: {output_filename}")
print("Done!")