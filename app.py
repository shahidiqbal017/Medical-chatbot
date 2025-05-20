from flask import Flask, request, jsonify, render_template
import re
import pandas as pd
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from datetime import datetime # For the custom Jinja filter

# --- NLTK Resource Management ---
def ensure_nltk_resources():
    """Checks for NLTK resources and downloads them if missing."""
    resources_to_check = {
        "wordnet": "corpora/wordnet.zip",
        "omw-1.4": "corpora/omw-1.4.zip",
        "stopwords": "corpora/stopwords.zip",
        "punkt": "tokenizers/punkt.zip",
        "english.pickle": "tokenizers/punkt/PY3/english.pickle"
    }
    all_resources_available = True
    for resource_id_or_name, resource_path in resources_to_check.items():
        actual_download_id = resource_id_or_name
        if resource_id_or_name == "english.pickle":
            actual_download_id = "punkt"

        try:
            nltk.data.find(resource_path)
            print(f"NLTK resource for '{resource_id_or_name}' (from package '{actual_download_id}') found at '{resource_path}'.")
        except LookupError:
            print(f"NLTK resource '{resource_id_or_name}' (part of '{actual_download_id}') not found. Attempting to download/update '{actual_download_id}'...")
            try:
                nltk.download(actual_download_id, quiet=False)
                print(f"NLTK package '{actual_download_id}' downloaded/updated successfully.")
                try:
                    nltk.data.find(resource_path)
                    print(f"NLTK resource for '{resource_id_or_name}' now found after download.")
                except LookupError:
                    print(f"ERROR: NLTK resource '{resource_id_or_name}' still not found after attempting to download '{actual_download_id}'.")
                    all_resources_available = False
            except Exception as e:
                print(f"ERROR: Failed to download NLTK package '{actual_download_id}'. Error: {e}")
                print("Please try downloading it manually in a Python interpreter:")
                print(f">>> import nltk")
                print(f">>> nltk.download('{actual_download_id}')")
                all_resources_available = False
    return all_resources_available

# Call at startup to ensure NLTK resources are available
if not ensure_nltk_resources():
    print("CRITICAL NLTK SETUP ERROR: Not all required NLTK resources could be made available. The application may not function correctly.")
    # Consider exiting if critical:
    # import sys
    # sys.exit("Exiting due to missing NLTK resources.")

app = Flask(__name__)

# --- Custom Jinja2 Filter for Initial Timestamp ---
def format_datetime_for_initial_message(value):
    """Formats the current time as HH:MM for the initial static message."""
    now = datetime.now()
    return now.strftime("%H:%M")

app.jinja_env.filters['timeformat'] = format_datetime_for_initial_message # Register the filter

# --- Global NLP Variables (Initialize after app and NLTK setup) ---
lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))


# --- Text Preprocessing Functions ---
def preprocess_text_for_user_input(text):
    """Processes user's input text for matching."""
    text = str(text).lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = text.replace('_', ' ')      # Replace underscores with spaces
    tokens = word_tokenize(text)       # NLTK's word tokenizer
    processed_tokens = [
        lemmatizer.lemmatize(word) for word in tokens if word not in stop_words and len(word) > 1
    ]
    return processed_tokens

def preprocess_kb_symptom_entry(symptom_text):
    """Processes symptom entries from CSV files for KB and severity mapping."""
    symptom_text = str(symptom_text).strip().lower().replace('_', ' ')
    tokens = word_tokenize(symptom_text)
    lemmatized_tokens = [lemmatizer.lemmatize(word) for word in tokens if len(word) > 0]
    return " ".join(lemmatized_tokens)


# --- Data Loading and Knowledge Base Creation ---
def load_knowledge_base_from_csvs():
    knowledge_base_list = []
    symptom_weights = {}
    try:
        df_dataset = pd.read_csv('Data/dataset.csv', na_filter=False)
        df_desc = pd.read_csv('Data/symptom_Description.csv', na_filter=False)
        df_precautions = pd.read_csv('Data/symptom_precaution.csv', na_filter=False)
        df_severity = pd.read_csv('Data/Symptom-severity.csv', na_filter=False) # Ensure exact filename match
    except FileNotFoundError as e:
        print(f"ERROR: One or more CSV files not found: {e}")
        return [], {}
    except pd.errors.EmptyDataError as e:
        print(f"ERROR: One or more CSV files are empty or improperly formatted: {e}")
        return [], {}

    # 1. Process Symptoms
    symptom_cols = [f'Symptom_{i}' for i in range(1, 18)]
    disease_symptoms_map = {}
    for index, row in df_dataset.iterrows():
        disease = str(row['Disease']).strip()
        if not disease: continue
        if disease not in disease_symptoms_map:
            disease_symptoms_map[disease] = set()
        for col in symptom_cols:
            raw_symptom = str(row[col]).strip()
            if raw_symptom:
                processed_symptom = preprocess_kb_symptom_entry(raw_symptom)
                if processed_symptom:
                    disease_symptoms_map[disease].add(processed_symptom)
    for disease in disease_symptoms_map:
        disease_symptoms_map[disease] = list(disease_symptoms_map[disease])

    # 2. Process Descriptions
    disease_descriptions = {}
    for index, row in df_desc.iterrows():
        disease = str(row['Disease']).strip()
        if disease:
            disease_descriptions[disease] = str(row['Description']).strip()

    # 3. Process Precautions
    disease_precautions = {}
    precaution_cols = [f'Precaution_{i}' for i in range(1, 5)]
    for index, row in df_precautions.iterrows():
        disease = str(row['Disease']).strip()
        if not disease: continue
        precautions_for_row = [str(row[col]).strip() for col in precaution_cols if str(row[col]).strip()]
        if precautions_for_row:
            disease_precautions[disease] = precautions_for_row

    # 4. Process Symptom Severity
    for index, row in df_severity.iterrows():
        raw_symptom = str(row['Symptom']).strip()
        weight_val = row['weight']
        if raw_symptom and pd.notna(weight_val) and str(weight_val).strip() != "":
            processed_symptom_key = preprocess_kb_symptom_entry(raw_symptom)
            if processed_symptom_key:
                try:
                    symptom_weights[processed_symptom_key] = int(weight_val)
                except ValueError:
                    print(f"Warning: Could not convert weight '{weight_val}' to int for symptom '{raw_symptom}'")

    # 5. Combine into the final knowledge base structure
    all_diseases_combined = set(disease_symptoms_map.keys()) | set(disease_descriptions.keys()) | set(disease_precautions.keys())
    for disease_name in all_diseases_combined:
        if not disease_name: continue
        knowledge_base_list.append({
            "disease_name": disease_name,
            "symptoms_processed": disease_symptoms_map.get(disease_name, []),
            "description": disease_descriptions.get(disease_name, "Description not available."),
            "precautions": disease_precautions.get(disease_name, [])
        })
    return knowledge_base_list, symptom_weights

knowledge_base, symptom_weights = load_knowledge_base_from_csvs()

if not knowledge_base:
    print("CRITICAL WARNING: Knowledge base is empty or could not be loaded. Chatbot may not function as expected.")
if not symptom_weights:
    print("WARNING: Symptom severity weights are empty or could not be loaded. Symptom scoring will use default weights.")


# --- Symptom Matching Logic ---
def find_matching_conditions(user_processed_tokens, kb, weights):
    matched_conditions = []
    if not kb: return []
    user_symptoms_set = set(user_processed_tokens)

    for condition_entry in kb:
        kb_symptom_phrases = condition_entry.get("symptoms_processed", [])
        if not kb_symptom_phrases: continue

        current_score = 0
        matched_kb_phrases_for_condition = set()

        for kb_phrase in kb_symptom_phrases:
            kb_phrase_tokens = set(kb_phrase.split())
            if not kb_phrase_tokens: continue

            # Check if all tokens of the KB phrase are present in the user's input tokens
            if kb_phrase_tokens.issubset(user_symptoms_set):
                current_score += weights.get(kb_phrase, 1) # Use weight of the phrase
                matched_kb_phrases_for_condition.add(kb_phrase)

        if matched_kb_phrases_for_condition:
            matched_conditions.append({
                "condition": condition_entry,
                "score": current_score,
                "matched_symptoms_in_kb": sorted(list(matched_kb_phrases_for_condition))
            })

    matched_conditions.sort(key=lambda x: x["score"], reverse=True)

    # Debugging output for development
    print("\n--- Top Matched Conditions (find_matching_conditions) ---")
    for i, match_info in enumerate(matched_conditions[:3]): # Print top 3 for brevity
        print(f"Rank {i+1}: Disease: {match_info['condition']['disease_name']}")
        print(f"  Score: {match_info['score']}")
        print(f"  Matched KB Symptoms: {match_info['matched_symptoms_in_kb']}")
        # For more detailed weight debugging during development:
        # for s_kb in match_info['matched_symptoms_in_kb']:
        #     print(f"    - '{s_kb}' (Weight: {weights.get(s_kb, 1)})")
    print("-----------------------------------------------------------\n")
    return matched_conditions


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', "").strip()
    top_disease_name_for_eval = None # For structured "accuracy" evaluation output

    if not user_message:
        return jsonify({'reply': "I didn't receive a message.", 'top_disease_suggestion': top_disease_name_for_eval})

    user_message_lower_stripped = user_message.lower()
    greetings = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "sup", "yo"]
    
    # You can customize this initial instruction note.
    initial_bot_instruction_note = "<small><strong>Note:</strong> I am an AI assistant. The information provided is based on general patterns and should not be considered a medical diagnosis. Always consult a qualified healthcare provider for medical concerns.</small>"


    if user_message_lower_stripped in greetings:
         bot_reply = f"Hello! How can I help you today? Please describe your symptoms.<br>{initial_bot_instruction_note}"
         return jsonify({'reply': bot_reply, 'top_disease_suggestion': top_disease_name_for_eval})

    processed_user_tokens = preprocess_text_for_user_input(user_message)
    print(f"User message: '{user_message}' -> Processed tokens: {processed_user_tokens}")

    if not processed_user_tokens:
        response_text = f"I couldn't understand your symptoms. Please describe your symptoms more clearly."
        # Removed disclaimer for lab evaluation focus
        return jsonify({'reply': response_text, 'top_disease_suggestion': top_disease_name_for_eval})

    possible_conditions = find_matching_conditions(processed_user_tokens, knowledge_base, symptom_weights)
    
    if possible_conditions:
        top_match = possible_conditions[0]
        condition_info = top_match['condition']
        top_disease_name_for_eval = condition_info['disease_name']

        matched_kb_symptoms_display = ', '.join(f"<em>'{s}'</em>" for s in top_match['matched_symptoms_in_kb'])
        if not matched_kb_symptoms_display:
             matched_kb_symptoms_display = "the symptoms you described"
        else:
            matched_kb_symptoms_display = f"symptoms like {matched_kb_symptoms_display}"

        response_text = f"Based on {matched_kb_symptoms_display}, one possibility could be <strong>{condition_info['disease_name']}</strong>. <br><br>"
        response_text += f"<strong>Description:</strong> {condition_info.get('description', 'N/A')}<br><br>"
        
        precautions_list = condition_info.get('precautions', [])
        if precautions_list:
            response_text += "<strong>Some general precautions include:</strong><ul>"
            for prec in precautions_list:
                if prec and str(prec).strip(): # Ensure precaution is not empty/whitespace
                    response_text += f"<li>{prec}</li>"
            response_text += "</ul>"
        # Disclaimer is intentionally removed for lab evaluation as requested
    else:
        response_text = "I couldn't find a clear match for your symptoms in my current knowledge base." # You might rephrase "It's best to consult a doctor..." if needed
        # Disclaimer is intentionally removed

    # Append the instructional note if not a greeting
    if not (user_message_lower_stripped in greetings):
        response_text += f"<br><br>{initial_bot_instruction_note}"
            
    return jsonify({'reply': response_text, 'top_disease_suggestion': top_disease_name_for_eval})

if __name__ == '__main__':
    if not knowledge_base:
        print("WARNING: Chatbot starting with an EMPTY knowledge base due to loading errors. Functionality will be impacted.")
    app.run(debug=True, use_reloader=False) # use_reloader=False can sometimes help with NLTK in dev environments