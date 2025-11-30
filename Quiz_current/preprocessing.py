# --------------------------------------------------------------
# preprocessing.py
# Automated Quiz Generator - Final Robust Version with TextRank (Sumy)
# --------------------------------------------------------------
# 🧠 Features:
# - Extracts text from PDF using pdfplumber
# - Cleans, tokenizes, and lemmatizes text
# - Uses TextRank (Sumy) to rank sentences by importance
# - Saves cleaned + ranked sentences for question generation
# --------------------------------------------------------------

import pdfplumber
import nltk
import re
import os
import math
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.stem import WordNetLemmatizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer

# --- Download required NLTK data ---
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

# --- Step 1: Extract text from PDF ---
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                # Remove headers/footers or page numbers
                page_text = re.sub(r'Page\s*\d+', '', page_text)
                text += page_text + " "
                print(f"✅ Extracted page {i+1}/{len(pdf.pages)}")
    return text


# --- Helper: Rank sentences by method ---
def rank_sentences(raw_text: str, method: str = "textrank"):
    method = (method or "textrank").strip().lower()
    try:
        parser = PlaintextParser.from_string(raw_text, Tokenizer("english"))
        total_sent = max(1, len(sent_tokenize(raw_text)))
        # Heuristic: pick ~top 15-20% (more selective) or at least 5
        target_count = max(5, min(total_sent // 5, 25))  # More selective: top 20% max 25 sentences

        if method == "lexrank":
            summarizer = LexRankSummarizer()
            summary_sentences = summarizer(parser.document, sentences_count=target_count)
            return [str(s) for s in summary_sentences]
        elif method == "tfidf":
            # Simple TF-IDF scoring per sentence
            sentences = [s.strip() for s in sent_tokenize(raw_text) if len(s.strip().split()) > 4]
            if not sentences:
                return []
            sw = set(stopwords.words('english'))
            tokenized = [[w.lower() for w in word_tokenize(s) if re.match(r"[a-zA-Z]+", w)] for s in sentences]
            tokenized_nostop = [[w for w in toks if w not in sw] for toks in tokenized]
            # DF
            df = {}
            for toks in set(map(tuple, tokenized_nostop)):
                unique = set(toks)
                for w in unique:
                    df[w] = df.get(w, 0) + 1
            N = len(sentences)
            # Score sentences
            scores = []
            for idx, toks in enumerate(tokenized_nostop):
                if not toks:
                    scores.append((0.0, idx))
                    continue
                tf = {}
                for w in toks:
                    tf[w] = tf.get(w, 0) + 1
                length = float(len(toks))
                s_score = 0.0
                for w, cnt in tf.items():
                    idf = math.log((N + 1) / (1 + df.get(w, 1))) + 1.0
                    s_score += (cnt / length) * idf
                scores.append((s_score, idx))
            scores.sort(reverse=True)
            top_idx = [i for _, i in scores[:target_count]]
            top_idx.sort()
            return [sentences[i] for i in top_idx]
        else:
            # Default: TextRank
            summarizer = TextRankSummarizer()
            summary_sentences = summarizer(parser.document, sentences_count=target_count)
            return [str(s) for s in summary_sentences]
    except Exception as e:
        print(f"⚠ Sentence ranking failed ({method}): {e}. Falling back to TextRank.")
        try:
            parser = PlaintextParser.from_string(raw_text, Tokenizer("english"))
            summarizer = TextRankSummarizer()
            total_sent = max(1, len(sent_tokenize(raw_text)))
            target_count = max(5, min(total_sent // 5, 25))  # More selective: top 20% max 25 sentences
            summary_sentences = summarizer(parser.document, sentences_count=target_count)
            return [str(s) for s in summary_sentences]
        except Exception as e2:
            print(f"⚠ Fallback TextRank failed: {e2}")
            return []


# --- Step 2: Clean and preprocess text ---
def preprocess_text(raw_text):
    # Clean up unwanted characters
    text = re.sub(r'\n+', ' ', raw_text)
    text = re.sub(r'Page\s*\d+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r"[^a-zA-Z0-9.,!?;:'\"()\-\s]", '', text)
    text = text.lower()

    # Sentence tokenization
    sentences = sent_tokenize(text)
    sentences = [s.strip() for s in sentences if len(s.split()) > 4]

    # --- Fallback segmentation ---
    if len(sentences) == 0:
        print("⚠ No sentences found using NLTK. Trying fallback segmentation...")
        sentences = re.split(r'[.;:\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip().split()) > 4]

    # Lemmatization
    lemmatizer = WordNetLemmatizer()
    lemmatized_sentences = []
    for s in sentences:
        words = word_tokenize(s)
        lemmas = [lemmatizer.lemmatize(w) for w in words]
        lemmatized_sentences.append(" ".join(lemmas))

    # --- Sentence ranking (method-selectable) ---
    print("\n⚙️ Applying sentence ranking for importance...")
    rank_method = os.getenv("RANK_METHOD", "textrank").strip().lower()
    try:
        ranked_sentences_raw = rank_sentences(text, method=rank_method)
        if not ranked_sentences_raw or len(ranked_sentences_raw) == 0:
            print(f"⚠ Ranking returned no sentences. Using top 15% of all sentences as fallback.")
            # Fallback: use top sentences by length and content quality
            ranked_sentences = sorted(lemmatized_sentences, key=lambda s: (len(s.split()), len(set(word_tokenize(s)))), reverse=True)[:max(5, len(lemmatized_sentences) // 7)]
        else:
            # Map ranked sentences back to lemmatized versions for consistency
            ranked_sentences = []
            ranked_lower = [s.lower().strip() for s in ranked_sentences_raw]
            for lemm_sent in lemmatized_sentences:
                lemm_lower = lemm_sent.lower().strip()
                # Match if ranked sentence is in lemmatized sentence or vice versa
                if any(rank_lower in lemm_lower or lemm_lower in rank_lower or 
                       sum(1 for w in word_tokenize(rank_lower) if w in word_tokenize(lemm_lower)) >= 3
                       for rank_lower in ranked_lower):
                    ranked_sentences.append(lemm_sent)
            # If mapping failed, use ranked sentences directly
            if len(ranked_sentences) < len(ranked_sentences_raw) // 2:
                ranked_sentences = [s.lower().strip() for s in ranked_sentences_raw[:max(5, len(ranked_sentences_raw))]]
        print(f"✅ Selected {len(ranked_sentences)} ranked important sentences using {rank_method.title()}.")
    except Exception as e:
        print(f"⚠ Ranking failed with {rank_method}: {e}")
        # Use top sentences by quality metrics instead of all
        ranked_sentences = sorted(lemmatized_sentences, key=lambda s: (len(s.split()), len(set(word_tokenize(s)))), reverse=True)[:max(5, len(lemmatized_sentences) // 7)]
        print(f"⚠ Using top {len(ranked_sentences)} sentences by quality metrics as fallback.")

    # Preview
    print("\n🔍 Example Ranked Sentences:")
    for i, s in enumerate(ranked_sentences[:5], 1):
        print(f"{i}. {s[:150]}...")

    return lemmatized_sentences, ranked_sentences, text


# --- Step 3: Save outputs ---
def save_outputs(sentences, ranked_sentences, text):
    with open("cleaned_sentences.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sentences))

    with open("ranked_sentences.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(ranked_sentences))

    with open("cleaned_text.txt", "w", encoding="utf-8") as f:
        f.write(text)

    print(f"\n🧩 Saved {len(sentences)} cleaned sentences.")
    print(f"🏆 Saved {len(ranked_sentences)} ranked sentences.")
    print("✅ Files: cleaned_sentences.txt, ranked_sentences.txt, cleaned_text.txt")


# --- Step 4: Run full pipeline ---
if __name__ == "__main__":
    pdf_path = "sample.pdf"  # 🔁 Replace with your actual PDF file
    raw_text = extract_text_from_pdf(pdf_path)

    if len(raw_text.strip()) < 10:
        print("⚠ No readable text found. Try OCR extraction for scanned PDFs.")
    else:
        print(f"\n📘 Extracted {len(raw_text)} characters of text from PDF.")
        sentences, ranked_sentences, cleaned_text = preprocess_text(raw_text)
        save_outputs(sentences, ranked_sentences, cleaned_text)
        print("\n✨ Preprocessing + Ranking complete! Ready for question generation.")
