from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

tokenizer = AutoTokenizer.from_pretrained("abdulwaheed1/urdu_to_english_translation_mbart")
model = AutoModelForSeq2SeqLM.from_pretrained("abdulwaheed1/urdu_to_english_translation_mbart")
