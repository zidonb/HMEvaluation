import requests
import pandas as pd
import json

# Elasticsearch configuration
ES_APP_URL = "http://YOUR_ES_SERVER:5002"  # UPDATE THIS!
ES_APP_URL = ES_APP_URL.rstrip('/')

# Search parameters (matching Nuclia evaluation)
SEARCH_SIZE = 20  # Number of documents to retrieve
NUM_CANDIDATES = 100
K = 25

# Read the Excel file (from QnA sheet)
df = pd.read_excel('mapping.xlsx', sheet_name='QnA')

# Prepare results storage
results = []
total_rr = 0
total_hit_at_3 = 0
total_hit_overall = 0
K_METRIC = 3  # for Hit@K metric

print("Starting Elasticsearch evaluation...\n")
print(f"Server: {ES_APP_URL}")
print(f"Search size: {SEARCH_SIZE}\n")

# Iterate through each row
for idx, row in df.iterrows():
    document_name = row['Document_Name']
    category = row['Category']
    question_level = row['Question Level']
    question = row['Question']
    expected_answer = row['Answer']
    
    print(f"Processing {idx + 1}/{len(df)}: {document_name}")
    
    try:
        # Call Elasticsearch /search endpoint
        response = requests.post(
            f"{ES_APP_URL}/search",
            json={
                "query": question,
                "size": SEARCH_SIZE,
                "num_candidates": NUM_CANDIDATES,
                "k": K
            },
            timeout=60
        )
        
        response.raise_for_status()
        response_data = response.json()
        
        # Extract file names from hits
        retrieved_files = []
        if "hits" in response_data and "hits" in response_data["hits"]:
            for hit in response_data["hits"]["hits"]:
                if "_source" in hit and "fileName" in hit["_source"]:
                    file_name = hit["_source"]["fileName"]
                    retrieved_files.append(file_name)
        
        # DEBUG: Print first result to understand format
        if idx == 0 and len(retrieved_files) > 0:
            print(f"\n{'='*70}")
            print(f"DEBUG - First file name from Elasticsearch:")
            print(f"  Raw value: {repr(retrieved_files[0])}")
            print(f"  Expected from Excel: {repr(document_name)}")
            print(f"{'='*70}\n")
        
        total_resources_returned = len(retrieved_files)
        
        # Remove file extension from document name for comparison
        document_name_without_ext = document_name.replace('.pdf', '').replace('.docx', '').replace('.doc', '')
        
        # Find if document_name is in retrieved_files and at what position
        position = None
        for i, file_name in enumerate(retrieved_files):
            # Extract just the filename from potential path
            # Handle both forward and backslash paths
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
                print(f"  DEBUG - Match found! Position: {position}, Matched: {file_name}")
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
        
        # Get answer (first document's text for reference)
        es_answer = ""
        if "hits" in response_data and "hits" in response_data["hits"] and len(response_data["hits"]["hits"]) > 0:
            first_hit = response_data["hits"]["hits"][0]
            if "_source" in first_hit:
                # Try to get text from various fields
                es_answer = first_hit["_source"].get("markdownText", 
                           first_hit["_source"].get("text", ""))[:500]  # First 500 chars
        
        # Store results
        result = {
            'Document_Name': document_name,
            'Category': category,
            'Question_Level': question_level,
            'Question': question,
            'Expected_Answer': expected_answer,
            'ES_Answer': es_answer,
            'Position': position if position else 'Not found',
            'Total_Resources_Returned': total_resources_returned,
            'Reciprocal_Rank': reciprocal_rank,
            'RR_Percentage': f"{reciprocal_rank * 100:.1f}%",
            'Hit@3': 'Yes' if hit_at_k else 'No',
            'Hit_Overall': 'Yes' if hit_overall else 'No',
            'Match_Info': match_info,
            'Retrieved_Files': ', '.join(retrieved_files[:10])  # Store top 10 file names
        }
        results.append(result)
        
        # Print progress
        print(f"  {document_name}: MRR: {reciprocal_rank:.2f} ({reciprocal_rank*100:.0f}%) | Hit@3: {'Yes' if hit_at_k else 'No'} | {match_info} | Resources: {total_resources_returned}")
        
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: Network error - {str(e)}")
        # Store error result
        result = {
            'Document_Name': document_name,
            'Category': category,
            'Question_Level': question_level,
            'Question': question,
            'Expected_Answer': expected_answer,
            'ES_Answer': f'ERROR: {str(e)}',
            'Position': 'Error',
            'Total_Resources_Returned': 0,
            'Reciprocal_Rank': 0.0,
            'RR_Percentage': '0.0%',
            'Hit@3': 'No',
            'Hit_Overall': 'No',
            'Match_Info': 'Error',
            'Retrieved_Files': ''
        }
        results.append(result)
        
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        # Store error result
        result = {
            'Document_Name': document_name,
            'Category': category,
            'Question_Level': question_level,
            'Question': question,
            'Expected_Answer': expected_answer,
            'ES_Answer': f'ERROR: {str(e)}',
            'Position': 'Error',
            'Total_Resources_Returned': 0,
            'Reciprocal_Rank': 0.0,
            'RR_Percentage': '0.0%',
            'Hit@3': 'No',
            'Hit_Overall': 'No',
            'Match_Info': 'Error',
            'Retrieved_Files': ''
        }
        results.append(result)

# Calculate final metrics
num_questions = len(df)
mrr = total_rr / num_questions
hit_at_3_rate = (total_hit_at_3 / num_questions) * 100
hit_overall_rate = (total_hit_overall / num_questions) * 100

# Print summary
print("\n" + "="*70)
print(f"ELASTICSEARCH EVALUATION SUMMARY ({num_questions} questions evaluated)")
print("="*70)
print(f"Mean Reciprocal Rank (MRR): {mrr:.2f} ({mrr*100:.1f}%)")
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
    'ES_Answer': ['', ''],
    'Position': ['', ''],
    'Total_Resources_Returned': ['', ''],
    'Reciprocal_Rank': ['', mrr],
    'RR_Percentage': ['', f"{mrr*100:.1f}%"],
    'Hit@3': ['', f"{hit_at_3_rate:.1f}%"],
    'Hit_Overall': ['', f"{hit_overall_rate:.1f}%"],
    'Match_Info': ['', f"MRR: {mrr:.2f}, Hit@3: {total_hit_at_3}/{num_questions}, Hit Overall: {total_hit_overall}/{num_questions}"],
    'Retrieved_Files': ['', '']
}
summary_df = pd.DataFrame(summary_data)
results_df = pd.concat([results_df, summary_df], ignore_index=True)

# Write to Excel
output_filename = 'elasticsearch_evaluation_results.xlsx'
results_df.to_excel(output_filename, index=False)

print(f"\nResults saved to: {output_filename}")