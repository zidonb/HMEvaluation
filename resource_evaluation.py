from nuclia import sdk
import pandas as pd

# Your Nuclia configuration
KNOWLEDGE_BOX_URL = "https://aws-il-central-1-1.rag.progress.cloud/api/v1/kb/ab6c2313-4339-4fb4-b324-00ecadf7af19"
API_KEY = "eyJhbGciOiJSUzI1NiIsImtpZCI6InNhIiwidHlwIjoiSldUIn0.eyJpc3MiOiJodHRwczovL2F3cy1pbC1jZW50cmFsLTEtMS5yYWcucHJvZ3Jlc3MuY2xvdWQvIiwiaWF0IjoxNzcwNTU5MjY5LCJzdWIiOiI4NTg1MDA0MC03N2NhLTRjNTctYjBjMi1iNTc5ODRmMjlkY2MiLCJqdGkiOiI5ZDNjNWViMC0yYTgwLTRkNjgtOWI5NC00YTJjYjQzMjgwNzQiLCJleHAiOjE4MDIwOTUyNjQsImtleSI6IjZkNjM4YTQxLWMyMzQtNDIzMC05MGI0LWI5ZWFmOTUxZTFiOSIsImtpZCI6IjI3NjhjNzMyLTZkN2UtNGNiNy1hNzhiLWM4MWU2YjNhOWI0MCJ9.oBXsZ6k6Bdh4l8c0Pg-XukhSgi7TdAkqsZjCBFS2-au0fkl33-P_tx6HaJDyPnmucOfj5ZqrxrGMhVCZiitQ97XPIcm_Jop95H6_gBlbUFzAg67k-p8DJftURqinf_EZkRRtwc0Jkz6noL-DQXF1G91rLE8dtXuamrWfdQw-nAyMT5bafQpli5JjiZ3lKhPmTL3JN4mfSp-9QkyI2za_JSukjz5p2-E-Mc1oWE-7LkDpLSQfU4CDIPDp4RxKODpglfztN3xodmb8-Y8te1YN7zpHHCVEx2wWkNSJ2Nnia5x_IqCQZjFCkxHr4DFfbz7sLkXFi4xLTlZf0NH5ghEFavoGASOXah03lIP7FOpdU3ZWaHag3jpwKWXMm7xzWcUVJr-uTYs2_rB1Ot9LTEo5K_dnGvpaVYnQaA37srWEKyS1A4wPcuRcCHTGOrJJtZGZYvAM13AVPb_3M2_IpPiLadYKB82Rsy0WtlcFxLjkHTQbNj7ZdLrWNXt_KF5iq-k9QoSkMoRr02hAcUmZeYcTBC_kPyR-1RO73uYn7JEd58TDze13itRxhMvdepcRP5qf0eYzN78w7czxJtyIrquvgoICvBGtA-W0vWQCr3mUDKrbx9oNsWlmC1YemPVo15Pi-35mgwsZx5qDS-W0zCdttNnb7Quw5u-nJ6qxgGwVGKk"

# Authenticate
sdk.NucliaAuth().kb(url=KNOWLEDGE_BOX_URL, token=API_KEY)

# Read the Excel file
df = pd.read_excel('mapping.xlsx')

# Prepare results storage
results = []
total_rr = 0
total_hit_at_3 = 0
total_hit_overall = 0
K = 3  # for Hit@K metric

print("Starting evaluation...\n")

# Iterate through each row
for idx, row in df.iterrows():
    document_name = row['Document_Name']
    question = row['Question']
    expected_answer = row['Answer']
    
    print(f"Processing {idx + 1}/{len(df)}: {document_name}")
    
    # Ask Nuclia
    response = sdk.NucliaSearch().ask(
        query={
            "query": question,
            "rephrase": True,
        }
    )
    
    # Get the answer
    answer = response.answer
    if isinstance(answer, bytes):
        answer = answer.decode("utf-8")
    
    # Get retrieved resources and extract slugs
    retrieved_resources = []
    if hasattr(response, 'find_result') and response.find_result:
        if hasattr(response.find_result, 'resources'):
            # resources is a dict: {resource_id: FindResource}
            for resource_id, resource in response.find_result.resources.items():
                if hasattr(resource, 'slug'):
                    retrieved_resources.append(resource.slug)

    # Remove file extension from document name for comparison
    document_name_without_ext = document_name.replace('.pdf', '').replace('.docx', '').replace('.doc', '')

    # Find if document_name is in retrieved_resources and at what position
    position = None
    for i, resource_slug in enumerate(retrieved_resources):
        # Check if document name (without extension) matches the slug
        if document_name_without_ext.lower() in resource_slug.lower():
            position = i + 1  # 1-indexed position
            break
    
    # Calculate metrics
    if position:
        reciprocal_rank = 1.0 / position
        hit_at_k = 1 if position <= K else 0
        hit_overall = 1  # Found anywhere in results
        match_info = f"{position}{'st' if position == 1 else 'nd' if position == 2 else 'rd' if position == 3 else 'th'} match"
    else:
        reciprocal_rank = 0.0
        hit_at_k = 0
        hit_overall = 0  # Not found
        match_info = "Not found"

    total_rr += reciprocal_rank
    total_hit_at_3 += hit_at_k
    total_hit_overall += hit_overall
    
    # Store results
    result = {
        'Document_Name': document_name,
        'Question': question,
        'Expected_Answer': expected_answer,
        'Nuclia_Answer': answer,
        'Position': position if position else 'Not found',
        'Reciprocal_Rank': reciprocal_rank,
        'RR_Percentage': f"{reciprocal_rank * 100:.1f}%",
        'Hit@3': 'Yes' if hit_at_k else 'No',
        'Match_Info': match_info,
        'Retrieved_Resources': ', '.join(retrieved_resources[:5])  # Store top 5 resource slugs
    }
    results.append(result)
    
    # Print progress
    print(f"  {document_name}: MRR: {reciprocal_rank:.2f} ({reciprocal_rank*100:.0f}%) | Hit@3: {'Yes' if hit_at_k else 'No'} | {match_info}")

# Calculate final metrics
num_questions = len(df)
mrr = total_rr / num_questions
hit_at_3_rate = (total_hit_at_3 / num_questions) * 100
hit_overall_rate = (total_hit_overall / num_questions) * 100

# Print summary
print("\n" + "="*60)
print(f"SUMMARY ({num_questions} questions evaluated)")
print("="*60)
print(f"Mean Reciprocal Rank (MRR): {mrr:.2f} ({mrr*100:.1f}%)")
print(f"Hit@3 Rate: {hit_at_3_rate:.1f}% ({total_hit_at_3}/{num_questions})")
print(f"Hit Rate (Overall): {hit_overall_rate:.1f}% ({total_hit_overall}/{num_questions})")
print("="*60)

# Create results DataFrame
results_df = pd.DataFrame(results)

# Add summary rows
summary_data = {
    'Document_Name': ['', 'SUMMARY'],
    'Question': ['', f'{num_questions} questions evaluated'],
    'Expected_Answer': ['', ''],
    'Nuclia_Answer': ['', ''],
    'Position': ['', ''],
    'Reciprocal_Rank': ['', mrr],
    'RR_Percentage': ['', f"{mrr*100:.1f}%"],
    'Hit@3': ['', f"{hit_at_3_rate:.1f}%"],
    'Match_Info': ['', f"MRR: {mrr:.2f}, Hit@3: {total_hit_at_3}/{num_questions}"],
    'retrieved_resources': ['', '']
}
summary_df = pd.DataFrame(summary_data)
results_df = pd.concat([results_df, summary_df], ignore_index=True)

# Write to Excel
output_filename = 'evaluation_results.xlsx'
results_df.to_excel(output_filename, index=False)

print(f"\nResults saved to: {output_filename}")