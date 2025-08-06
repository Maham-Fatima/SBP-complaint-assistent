import os
from fastapi import FastAPI, UploadFile, File, Query,  HTTPException
from ollama_run import extract_names_urdu,detect_correction_command, extract_complaint_type,complain_description_handler, detail_extract, extract_all_details, extract_names, translator_func, extract_cnic, extract_phone, extract_bank, extract_email
from pydantic import BaseModel
from speechtotext import transcribe
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import asyncio
import re

class BotRequest(BaseModel):
    info: str
    remaining_fields: Dict[str, Optional[str]]
    previous_question: Optional[str]

class Complaint(BaseModel):
    complain: str

class Info(BaseModel):
    info: str

app = FastAPI()

# Allow frontend access (adjust origin if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def spell_digits(s):
    return ' '.join(s) if s else 'not provided'


def spell_out_email(email):
    if "@" in email:
        user, domain = email.split("@", 1)
        spelled_user = ' '.join(user)
        return f"{spelled_user} at {domain}"
    return email



@app.post("/translate/")
async def translate(body: Info):
    print(body.info)
    return await translator_func(text=body.info)



@app.post("/transcribe/")
async def stt(file: UploadFile = File(...), audio: str = Query("en", description="Language hint for transcription")):
    return await transcribe(file, audio)


@app.post("/extract/")
async def extract_info(body: Info):
    info = detail_extract(info=body.info)
    return info



@app.post("/summary/")
async def summary_generate(body: Complaint):
    summary = await complain_description_handler(complain=body.complain)
    return summary

@app.post("/extract-name/")
async def extract_name_info(body: Info):
    details = extract_names(text=body.info)
    print("Extracted name:", details)
    return details

@app.post("/extract-name-urdu/")
async def extract_name_info(body: Info):
    details = extract_names_urdu(text=body.info)
    print("Extracted name urdu:", details)
    return details

@app.post("/extract-cnic/")
async def extract_cnic_info(body: Info):
    print("Extracting CNIC from:", body.info)
    details = extract_cnic(text=body.info)
    print("Extracted CNIC:", details)
    return details

@app.post("/extract-phone/")
async def extract_phone_info(body: Info):
    print("Extracting phone from:", body.info)
    details = extract_phone(text=body.info)
    print("Extracted phone:", details)
    return details

@app.post("/extract-email/")
async def extract_email_info(body: Info):
    print("Extracting email from:", body.info)
    details = extract_email(text=body.info)
    print("Extracted email:", details)
    return details


@app.post("/extract-details/")
async def extract_detail(body:Info):
    print("Extracting details from:", body.info)
    details = extract_all_details(info=body.info)
    return details


@app.post("/bot/")
async def bot(request: BotRequest):
    
    user_input = request.info
    state = request.remaining_fields
    previous_question = request.previous_question or ""
    print("User input:", user_input)
    print("Previous question:", previous_question)
    print("Current state:", state)
    greetings = ["hello", "hi", "salam", "asalam-o-alaikum", "aoa"]
    complaint_keywords = ["issue", "complaint", "problem", "file", "report", "complain"]
    try:
       
        if not state["name"]:
            name = extract_names(user_input)
            print(name)
            state["name"] = name if name else None
        if not state["cnic"]:
            state["cnic"] = extract_cnic(user_input)    
        if not state["email"]:
            state["email"] = extract_email(user_input) 
        if not state["phone"]:
            state["phone"] = extract_phone(user_input) 
        if not state["complaint_type"] or state["complaint_type"] == "unknown":
            state["complaint_type"] = extract_complaint_type(user_input) 
        if "complain" in user_input or "describe your complaint" in previous_question or any(word in user_input.lower() for word in complaint_keywords):
            print(type(user_input))
            if not state["description"]:
                state["description"] = user_input
            else:
                state["description"] = state["description"] + user_input
  
        
        # Handle registration flow
        yes_words = ["yes", "y", "yeah", "ok", "okay"]
        no_words = ["no", "n", "not yet", "new"]


        patternyes = r"\b(" + "|".join(re.escape(yes) for yes in yes_words) + r")\b"
        patternno = r"\b(" + "|".join(re.escape(no) for no in no_words) + r")\b"
        if not state.get("is_registered_user"):
            if "registered user" in previous_question.lower():
                if re.search(patternyes, user_input.lower()):
                
                    state["is_registered_user"] = "True"
                    if not state["cnic"]:
                        return {"message": "Please provide your CNIC number.", "state": state}
                
                elif re.search(patternno, user_input.lower()):
                    missing_fields = []
                    state["is_registered_user"] = "False"
                    if not state.get("name"):
                        missing_fields.append("full name")
                    if not state.get("phone"):
                        missing_fields.append("phone number")
                    if not state.get("email"):
                        missing_fields.append("email")
                    if not state.get("cnic"):
                        missing_fields.append("CNIC")

                    if missing_fields:
                        print(state)
                        return {
                            "message": f"Please provide the following details: {', '.join(missing_fields)}.",
                            "state": state
                        }


            if "already registered" in user_input.lower() or "registered user" in user_input.lower():
                if not state["cnic"]:
                    state["is_registered_user"] = "True"
                    return {"message": "Please provide your CNIC number.", "state": state}   
            elif "not registered" in user_input.lower() or "new user" in user_input.lower():
                state["is_registered_user"] = "False"
                missing_fields = []

                if not state.get("name"):
                    missing_fields.append("full name")
                if not state.get("phone"):
                    missing_fields.append("phone number")
                if not state.get("email"):
                    missing_fields.append("email")
                if not state.get("cnic"):
                    missing_fields.append("CNIC")

                if missing_fields:
                    return {
                        "message": f"Please provide the following details: {', '.join(missing_fields)}.",
                        "state": state
                    }
            else:
                 return {
                        "message": "Are you already a registered user?",
                        "state": state
                    }


                    

       

       
    except asyncio.CancelledError:
        print("Request was cancelled — likely due to shutdown or client disconnect")
        raise HTTPException(status_code=499, detail="Client Closed Request")  # Nginx-style client abort
    except Exception as e:
        print("Unexpected error during extraction:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    

    # Greeting
   

    pattern = r"\b(" + "|".join(re.escape(greet) for greet in greetings) + r")\b"
   

    if re.search(pattern, user_input.lower()) or not state.get("is_registered_user"):
        reg_status = state.get("is_registered_user")
        reg_msg = (
            "You're already registered." if reg_status else
            "You're not registered yet." if reg_status == "False" else
            "Are you already a registered user?"
        )
        
            
        return {
            "message": f"Good to see you! How can I assist you today?{reg_msg}",
            "state": state
        }
    


     # handle complain 
   
    # if any(word in user_input.lower() for word in complaint_keywords):
    #     if not state.get("is_registered_user") or state.get("is_registered_user") == False:
    #         return {"message": "Have you registered?", "state": state}



    
    correction_field = detect_correction_command(user_input)
    if correction_field:
        if correction_field == "description":
            state[correction_field] = complain_description_handler(user_input)
            return {
                "message": f"Okay, I've updated your {correction_field}. Anything else you want to change?",
                "state": state
            }

        # Force re-extraction for just that field
        if correction_field == 'name':
            extracted = extract_names(user_input)

        elif correction_field == 'phone':
            extracted = extract_phone(user_input)

        elif correction_field == 'cnic':
            extracted = extract_cnic(user_input)

        elif correction_field == 'email':
            extracted = extract_email(user_input)

        elif correction_field == 'bank':
            extracted = extract_bank(user_input)

        elif correction_field == 'complaint_type':
            extracted = extract_complaint_type(user_input)           
      
        if extracted and extracted != "unknown":
            state[correction_field] = extracted
            return {
                "message": f"Okay, I've updated your {correction_field}. Anything else you want to change?",
                "state": state
            }
        else:
            return {
                "message": f"I understood you want to update your {correction_field}, but I couldn't find the new value. Please provide it.",
                "state": state
            }
       

    if not state.get("cnic"):
            match = extract_cnic(user_input)
            if match:
                state["cnic"] = match
            else:
                return {
                    "message" : ("Please tell your CNIC" ), "state" : state
                }

    if state.get("cnic") and state["is_registered_user"] == "True":
        state["name"] = "already provided"
        state["phone"] = "already provided"
        state["email"] = "already provided"


    if not state.get("name") and state["is_registered_user"] == "False":
            match = extract_names(user_input)
            if match:
                state["name"] = match
            else:
                return {
                    "message" : ("Please spell your full name" ), "state" : state
                }

    if not state.get("phone") and state["is_registered_user"] == "False":
        return {"message": "Please provide your correct phone", "state": state}

    if not state.get("phone") and "share your phone number" in previous_question:
        return {"message": "Please provide your correct phone", "state": state}



    if not state.get("email") and state["is_registered_user"] == "False":
        match = extract_email(user_input)
        if match:
            state["email"] = match
        else:
            return {"message": "Please spell your email address.", "state": state}

    if not state.get("email") and "spell your email address" in previous_question :
        return {"message": "I am expecting your email address spelling.", "state": state}
    


    # Hardcoded options for bank and complaint type
    if not state.get("bank"):
        match = extract_bank(user_input)
        if match:
            state["bank"] = match
        else:

            return {
                            "message": (
                "Which bank is your complaint related to? Please choose from: "
                "Habib Bank Limited. "
                "United Bank Limited. "
                "MCB Bank Limited. "
                "Allied Bank Limited. "
                "Askari Bank. "
                "Al Habib. "
                "Bank Alfalah. "
                "JS. "
                "Soneri. "
                "HabibMetro. "
                "Faysal Bank."
            ),

                "state": state
        }
    if not state["bank"] and "which bank" in previous_question.lower():
        return {
                "message": (
                "Sorry did not get bank name which bank? Please choose from: "
                "Habib Bank Limited, "
                "United Bank Limited, "
                "MCB Bank Limited, "
                "Allied Bank Limited, "
                "Askari , "
                "Bank Al Habib, "
                " Alfalah, "
                "JS Bank, "
                "Soneri , "
                "HabibMetro, "
                "Faysal Bank."
            ),

                "state": state
        }


    if not state.get("complaint_type") or state["complaint_type"] == "unknown" or state["complaint_type"] == "Other":
        if state["complaint_type"] == "Other":
            if "tell your complaint type" in previous_question:
                state["complaint_type"] == user_input
            return {
                "message": (
                    "Please tell your complaint type?\n"
                    
                ),
                "state": state
            }
        match = extract_complaint_type(user_input)

        if match and match != "unknown":
            state["complaint_type"] = match
        else:    
            return {
                "message": (
                    "Please select your complaint type from the following options:"
                    "1 Delay in receiving remittance. 2 Remittance not credited. 3 Wrong amount received."
                    "4 Wrong beneficiary details. 5 Exchange rate issue. 6 Deduction without reason."
                    "7 No alert received. 8 Remittance held/blockage. 9 Remittance rejected. 10 Other"
                ),
                "state": state
            }

   

    state["description"] = await complain_description_handler(state.get("description"))
    
    if not state.get("description"):
        return {"message": "Please describe your complaint briefly.", "state": state}
    
    



    # All fields filled, confirm
    if all(v for k, v in state.items() if k != "is_registered_user"):
        

        if "Do you confirm your complaint" in previous_question or "change anything else" in previous_question:
            if re.search(patternyes, user_input.lower()):
               return {
                    "message": "Thank you! Your complain has been finalized",
                    "state": state
               }

        return {
            "message" : (
    "Here is what we have:\n"
    f"- Your name is spelled as {' '.join(state.get('name', '').split()) if state.get('name') else 'not provided'}\n"
    f"- Your phone number is {spell_digits(state.get('phone'))}\n"
    f"- Your email is spelled as {spell_out_email(state.get('email')) if state.get('email') else 'not provided'}\n"
    f"- Your CNIC is {spell_digits(state.get('cnic'))}\n"
    f"- Your bank name is {state.get('bank', 'not provided')}\n"
    f"- Complaint category: {state.get('complaint_type', 'not provided')}\n"
    f"- Complaint description: {state.get('description', 'not provided')}, Do you confirm your complaint or want to change anything else?"),
            "state": state
        }
    
    

    # Fallback to continue if something still missing
    return {"message": "I can't hear what you are trying to say?", "state": state}


# listen to user 
# extract using regex and just ask nlp for for name extract only
# hard code logic for new extracted fields to confirm input
# hard code logic for asking if user is already registered or not
# hard code for yes ask cnic and for no ask details
# then use regex to extract details all remaining , if cnic is not in there , fill provided and again ask if registered or not to work on your request
# hard code logic to ask for remaining fields like list of banks, list of complain categories if remaining
# only question how create brief complain summary from whole conversation, chcek relevant details, find name
