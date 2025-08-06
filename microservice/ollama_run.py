import ollama
import json
import re
import nltk
from nltk import word_tokenize, pos_tag
from rapidfuzz import process, fuzz
import phonenumbers
import asyncio
import re
from fastapi.concurrency import run_in_threadpool
from deep_translator import GoogleTranslator

nltk.data.path.append("C:/Users/dell/AppData/Roaming/nltk_data")

client = ollama.Client()  

def load_name_list(filepath="names.txt"):
    with open(filepath, "r", encoding="utf-8") as f:
        return set(line.strip().title() for line in f if line.strip())

    

name_list = load_name_list()

def load_urdu_name_dict_from_json(filepath="urdu_name_dict.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)  

urdu_name_dict = load_urdu_name_dict_from_json()

translator = GoogleTranslator(source='ur', target='en')

correction_keywords = ["sorry", "change", "update", "replace", "correct", "edit"]

fields = {
    "email": ["email", "mail"],
    "phone": ["phone", "number", "contact"],
    "cnic": ["cnic", "id card", "identity"],
    "bank": ["bank", "bank name"],
    "name": ["name"],
    "complain_type": ["complain category", "complaint type", "issue", "problem"]
}

def detect_correction_command(user_input: str):
    user_input_lower = user_input.lower()
    if "bank" in user_input_lower:
        return "bank"
    if any(kw in user_input_lower for kw in correction_keywords):
        for field_key, field_aliases in fields.items():
            if any(alias in user_input_lower for alias in field_aliases):
                return field_key
    return None

def clean_llm_name(name: str) -> str:

    if not name or not isinstance(name, str):
        return None

    match = re.search(r"User Name:\s*(.+)", name, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Remove markdown, asterisks, extra whitespace
    name = re.sub(r'\*+', '', name).strip()
    name = re.sub(r'\s+', ' ', name)

    # Disqualify if more than 3 words
    if len(name.split()) > 3:
        return None

    # Disqualify if it contains line breaks or code blocks
    if '\n' in name or '```' in name:
        return None

    # Reject known LLM apologies or hallucinations
    fallback_phrases = [
        "i am an ai",
        "i am designed",
        "as an ai",
        "i cannot",
        "my knowledge base",
        "please provide",
        "i'm unable",
        "i do not have access",
    ]
    for phrase in fallback_phrases:
        if phrase in name.lower():
            return None

    return name

# Non-name fillers
NON_NAMES = {
    "hello", "hi", "thanks", "yes", "no", "okay", "ok", "goodbye", "please",
    "my", "myself", "your", "you", "i", "me", "we", "us", "they", "them", "it", 
    "its", "this", "that"
}




def find_closest_name(text, threshold=85):
    words = re.findall(r'\b[A-Z][a-z]+\b', text.title())
    found_names = []

    for word in words:
        match, score, _ = process.extractOne(word, name_list)
        if score >= threshold:
            found_names.append(match)

    return " ".join(found_names) if found_names else None



def call_ollama_to_extract_name(text):
    import ollama
    response = ollama.chat(
        model="gemma:2b-instruct",
        messages=[
            {"role": "system", "content": "Extract only the person's name. Return JSON like: {\"name\": \"...\"}"},
            {"role": "user", "content": text}
        ]
    )
    try:
        content = response['message']['content']
        clean_json = re.sub(r"```json|```", "", content).strip()
        data = json.loads(clean_json)
        return data.get("name")
    except Exception as e:
        print(f"Ollama error: {e}")
        return None

def extract_names_urdu(text):
    CONNECTORS_URDU = {"بن", "بنت", "ابن", "عبد", "ابو", "ال"}
    words = text.split()
    full_name_urdu = []

    i = 0
    while i < len(words):
        if words[i] in urdu_name_dict:
            full_name_urdu.append(words[i])
            i += 1
            # Look ahead for possible connector + next name
            if i < len(words) and words[i] in CONNECTORS_URDU:
                connector = words[i]
                i += 1
                if i < len(words) and words[i] in urdu_name_dict:
                    full_name_urdu.append(connector)
                    full_name_urdu.append(words[i])
                    i += 1
        else:
            i += 1

    if full_name_urdu:
        # Convert Urdu names to English using the dictionary
        full_name_english = [
            urdu_name_dict[word] if word in urdu_name_dict else word
            for word in full_name_urdu
        ]
        return " ".join(full_name_english)

    # Fallback to LLM (e.g., Ollama)
    name = call_ollama_to_extract_name(text)
    if name:
        print(f"🧠 Extracted via Ollama (Urdu): {name}")
        cache_new_name(name)

        return name

    print("❌ Urdu name not found")
    return None


# Main hybrid extractor
def extract_names(text):
    CONNECTORS = {"ul", "uz", "ur", "bin", "bint", "ibn", "abd", "abu"}
    words = text.title().split()
    full_name = []

    i = 0
    while i < len(words):
        if words[i] in name_list:
            full_name.append(words[i])
            i += 1
            # Look ahead for possible connector + next name
            if i < len(words) and words[i].lower() in CONNECTORS:
                connector = words[i]
                i += 1
                if i < len(words) and words[i] in name_list:
                    full_name.append(connector)
                    full_name.append(words[i])
                    i += 1
        else:
            i += 1

  
    if full_name:
       return " ".join(full_name)

    
    name = call_ollama_to_extract_name(text)
    if name:
        print(f"🧠 Extracted via Ollama: {name}")
        # Optionally cache
        translated = GoogleTranslator(source='ur', target='en').translate(name)
        translated = translated.title().strip()
        cache_new_name(name)
        return name
    
    print("❌ Name not found")
    return None

# Optional: Cache new names found by Ollama
def cache_new_name(name, filepath="names.txt", translated = "null"):
# If name not already present
    if name not in urdu_name_dict:
        try:

            urdu_name_dict[name] = translated
            print(f"✅ Added: {name} → {translated}")

            # Save updated dictionary
            with open("urdu_name_dict.json", "w", encoding="utf-8") as f:
                json.dump(urdu_name_dict, f, ensure_ascii=False, indent=2)

            
        except Exception as e:
            print(f"❌ Translation error: {e}")


    if name not in name_list:
        with open(filepath, "a", encoding="utf-8") as f:
            for part in name.split():
                if part not in name_list:
                    f.write(part + "\n")
                    name_list.add(part)







def extract_cnic(text: str):
    match = re.search(r'\b\d{5}-\d{7}-\d{1}\b|\b\d{13}\b', text)
    return match.group() if match else None





def extract_phone(text: str, default_region: str = "PK"):
    raw_numbers = re.findall(r'\+?\d{10,15}', text)
    valid_numbers = []

    for raw in raw_numbers:
        try:
            # Smart region parsing
            if len(raw) == 10 and raw.startswith("3"):
                raw = "0" + raw

            region = None if raw.startswith('+') or raw.startswith('00') else default_region
            parsed = phonenumbers.parse(raw, region)

            if phonenumbers.is_valid_number(parsed):
                formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                valid_numbers.append(formatted)
        except:
            continue

    return valid_numbers[0] if valid_numbers else None


BANK_ALIASES = {
    "HBL": "Habib Bank Limited",
    "UBL": "United Bank Limited",
    "MCB": "MCB Bank Limited",
    "ABL": "Allied Bank Limited",
    "AKBL": "Askari Bank",
    "BAH": "Bank Al Habib",
    "BAF": "Bank Alfalah",
    "JS": "JS Bank",
    "SONERI": "Soneri Bank",
    "HABIBMETRO": "HabibMetro Bank",
    "FBL": "Faysal Bank"
}

BANKS = list(set(BANK_ALIASES.values()) | {
    "Habib Bank Limited",
    "United Bank Limited",
    "MCB Bank Limited",
    "Allied Bank Limited",
    "Askari Bank",
    "Bank Al Habib",
    "Bank Alfalah",
    "JS Bank",
    "Soneri Bank",
    "HabibMetro Bank",
    "Faysal Bank"
})


COMPLAINT_KEYWORDS = {
    "Delay in receiving remittance": ["delay", "late", "wait", "not arrived"],
    "Remittance not credited": ["not credited", "not received", "missing", "didn't get"],
    "Wrong amount received": ["wrong amount", "less", "more", "incorrect amount"],
    "Wrong beneficiary details": ["wrong beneficiary", "different person", "wrong account"],
    "Exchange rate issue": ["exchange rate", "conversion", "rate issue"],
    "Deduction without reason": ["deduction", "cut", "reduced", "charge", "fee"],
    "No alert received": ["no alert", "no sms", "not informed"],
    "Remittance held/blockage": ["held", "block", "pending", "stuck"],
    "Remittance rejected": ["rejected", "failed", "declined"],
    "Other": []
}


def extract_complaint_type(text: str):
    text = text.lower()

    # Direct number match (1-10)
    if text.strip().isdigit():
        index = int(text.strip())
        if 1 <= index <= len(COMPLAINT_KEYWORDS):
            return list(COMPLAINT_KEYWORDS.keys())[index - 1]

    # Search for keywords
    best_match = None
    highest_score = 0
    for complaint, keywords in COMPLAINT_KEYWORDS.items():
        for keyword in keywords:
            score = fuzz.partial_ratio(keyword, text)
            if score > highest_score:
                highest_score = score
                best_match = complaint

    print(best_match)
    print(highest_score)
    return best_match if highest_score >= 85 else "unknown"


def extract_bank(text: str) -> str | None:
    threshold = 70
    words = word_tokenize(text)
    tagged = pos_tag(words)
    cleaned_words = [w.lower() for w in words]

    # Check for abbreviations (exact match, case-insensitive)
    for word in cleaned_words:
        upper_word = word.upper()
        if upper_word in BANK_ALIASES:
            print(f"Matched abbreviation: {upper_word} → {BANK_ALIASES[upper_word]}")
            return BANK_ALIASES[upper_word]

    # Try fuzzy match on all words (e.g., "habeeb", "alflah")
    for word in cleaned_words:
        match = process.extractOne(word, BANKS, scorer=fuzz.partial_ratio)
        if match and match[1] >= threshold:
            print(f"Fuzzy matched: {word} → {match[0]} (score: {match[1]})")
            return match[0]

    # Try proper noun candidates only
    candidates = [word for word, tag in tagged if tag.startswith("NN")]
    for candidate in candidates:
        match = process.extractOne(candidate, BANKS, scorer=fuzz.partial_ratio)
        if match and match[1] >= threshold:
            print(f"Fuzzy matched (POS): {candidate} → {match[0]} (score: {match[1]})")
            return match[0]

    return None




    
def extract_email(text: str) -> str | None:
    text = text.lower()

    # Normalize common spoken variants *with space tolerance*
    text = re.sub(r"\s*\bat\b\s*", "@", text)
    text = re.sub(r"\s*\bdot\b\s*", ".", text)

    # Fix domains with no dot (e.g., gmailcom → gmail.com)
    text = re.sub(r"(@\w+)(com|net|org|edu)\b", r"\1.\2", text)

    # Extract the email
    match = re.search(r"[a-zA-Z0-9._%+-]+@gmail\.com", text)
    return match.group() if match else None





async def complain_description_handler(complain: str):
    # First: Check if it's a detailed complaint
    result = await complain_found(complain=complain)


    if result == False:
        return None

    if len(complain.split(" ")) < 30:
        return complain
    # Second: Now summarize the complaint
    loop = asyncio.get_event_loop()

    def run_chat():
        return client.chat(
            model="gemma:2b-Instruct",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that shortens a customer complaint into 2 short lines."
                    )
                },
                {"role": "user", "content": complain}
            ]
        )

    response = await loop.run_in_executor(None, run_chat)
    content = response["message"]["content"]

    # Optional: Clean up prefix if model adds it
    if content.lower().startswith("customer complaint:"):
        summary = content[len("customer complaint:"):].strip()
    else:
        summary = content

    print("Raw summary response:", summary)
    return summary





async def complain_found(complain: str):
    loop = asyncio.get_event_loop()

    def run_chat():
        return len(complain.split(" ")) > 1

        

    response = await loop.run_in_executor(None, run_chat)

    return response





async def extract_all_details(info: str):
    
    return {

        "name": extract_names(info),
        "cnic": extract_cnic(info),
        "phone": extract_phone(info),
        "bank": extract_bank(info),
        "complain_type": extract_complaint_type(info)
    }





async def detail_extract(info: str):
    loop = asyncio.get_event_loop()

    def run_extraction():
        return client.chat(
            model="phi3:mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an information extraction assistant.\n"
                        "Extract: name, CNIC (13 digits), phone (e.g. 03XXXXXXXXX), and bank name (HBL, Al-Habib, Habib Metro, Meezan, National, State).\n"
                        "Return strictly valid JSON. If a field is missing, set its value to null.\n"
                        "Format:\n"
                        '{\n  "translated": "...",\n  "name": "...",\n  "cnic": "...",\n  "phone": "...",\n  "bank": "..." \n}'
                    )
                },
                {
                    "role": "user",
                    "content": info
                }
            ]
        )

    response = await loop.run_in_executor(None, run_extraction)

    content = response["message"]["content"]
    print("Raw response:", content)

    # Clean markdown-style formatting if present
    cleaned = re.sub(r"```(?:json)?|```", "", content).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        return {
            "error": "Failed to parse JSON",
            "raw": content,
            "cleaned": cleaned,
            "details": str(e)
        }







async def translator_func(text: str):
  
    loop = asyncio.get_event_loop()

    
    def run_translation():
        translation = translator.translate(text)
        print(translation)
        return translation

    response = await loop.run_in_executor(None, run_translation)
    return response






def build_assistant_prompt( state: dict):
        filled = {k: v for k, v in state.items() if v}
        missing = [k for k in state if not state[k]]

        complain_type_instruction = (
            
            "Here are the valid types: {', '.join(COMPLAIN_TYPES)}.\n"
            
        )

        return (
            "You are a friendly complaint assistant that supports English.\n"
            "Extract: {missing} details\n"
            "Return strictly valid JSON. If a field is missing, set its value to null.\n"
            f"Already provided: {filled}\n"
            f"Missing fields: {missing}\n"
            f"{complain_type_instruction}\n"
            "After extracting the details from the user's message, determine which fields are still missing (i.e., null in the output JSON). Ask a friendly follow-up question for only one missing field."
            "Ask for only the missing fields in a conversational way. If all are present, summarize and confirm the complaint."
        )

 

async def run_assistant(text: str, remaining_fields: dict, prompt: str = None):
    state = remaining_fields.copy()

    system_prompt = build_assistant_prompt(state) if not prompt else prompt

    final_prompt = (
        f"{system_prompt}\n\n"
        "Respond only in the following JSON format:\n"
        '{\n'
        '  "message": "<your friendly reply>",\n'
        '  "state": {\n'
        '     "is_registered_user": "...",\n'
        '    "name": "...",\n'
        '    "CNIC": "...",\n'
        '    "phone": "...",\n'
        '    "email": "...",\n'
        '    "bank_name": "...",\n'
        '    "complaint_type": "...",\n'
        '    "complaint_description": "..." \n'
        '  }\n'
        '}\n'
        "Even if some fields are missing, include them with null values.\n"
        "Do not add explanations outside the JSON."
    )

    try:
        # Offload blocking Ollama call to threadpool
        response = await run_in_threadpool(ollama.chat,
            model='gemma:2b-instruct',
            messages=[
                {"role": "system", "content": final_prompt},
                {"role": "user", "content": text}
            ]
        )

        raw = response['message']['content']
        print(raw)


        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        result = json.loads(raw)
        return {
            "message": result.get("message", "I'm here to help."),
            "state": result.get("state", state)
        }

    except json.JSONDecodeError:
        return {
            "message": "Sorry, I couldn't understand your details. Could you repeat?",
            "state": state
        }

    except Exception as e:
        return {
            "message": f"An error occurred: {str(e)}",
            "state": state
        }
