import os
import hashlib
import random
from typing import List, Dict, Tuple
import time

# Local module imports
import preprocessing
import question_generation as qg
import output_quiz as oq
import randomization as rz


def write_generated_questions(questions: List[dict], path: str = "generated_questions.txt") -> None:
    """Write questions to file with proper formatting"""
    option_labels = ['A)', 'B)', 'C)', 'D)']
    with open(path, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(f"({q['type']}) {q['question']}\n")
            if q.get('type') == "MCQ" and q.get('options'):
                for idx, opt in enumerate(q['options']):
                    label = option_labels[idx] if idx < len(option_labels) else chr(ord('A') + idx) + ')'
                    f.write(f"  {label} {opt}\n")
            f.write(f"Answer: {q['answer']}\n\n")


def batch_generate_questions(sentences: List[str], question_types: List[str], batch_size: int = 50) -> List[dict]:
    """
    Generate questions in batches for better performance.
    Processes sentences in chunks to reduce overhead.
    """
    all_questions = []
    total_batches = (len(sentences) + batch_size - 1) // batch_size
    
    print(f"⚡ Processing {len(sentences)} sentences in {total_batches} batches of {batch_size}")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(sentences))
        batch = sentences[start_idx:end_idx]
        
        batch_questions = []
        
        # Generate questions for this batch
        if "mcq" in question_types:
            batch_questions.extend(qg.generate_mcq(batch))
        if "fill_blanks" in question_types:
            batch_questions.extend(qg.generate_fill(batch))
        if "true_false" in question_types:
            batch_questions.extend(qg.generate_true_false(batch))
        if "short_answer" in question_types:
            batch_questions.extend(qg.generate_short_answers(batch))
        
        all_questions.extend(batch_questions)
        
        if (batch_num + 1) % 5 == 0 or batch_num == total_batches - 1:
            print(f"  ✓ Completed {batch_num + 1}/{total_batches} batches ({len(all_questions)} questions so far)")
    
    return all_questions


def smart_sentence_selection(sentences: List[str], max_sentences: int = 20) -> List[str]:
    """
    Intelligently select sentences for question generation.
    Prioritizes diverse, well-formed sentences.
    """
    if len(sentences) <= max_sentences:
        return sentences
    
    # Score sentences based on quality metrics
    scored = []
    for s in sentences:
        words = s.split()
        score = 0
        
        # Length score (prefer medium-length sentences)
        if 8 <= len(words) <= 25:
            score += 2
        elif 6 <= len(words) <= 30:
            score += 1
        
        # Variety score (unique words)
        unique_ratio = len(set(words)) / len(words) if words else 0
        score += unique_ratio * 2
        
        # Complexity score (has nouns, verbs)
        if any(word[0].isupper() for word in words[1:]):  # Has proper nouns
            score += 1
        
        scored.append((score, s))
    
    # Sort by score and take top N
    scored.sort(reverse=True, key=lambda x: x[0])
    selected = [s for _, s in scored[:max_sentences]]
    
    print(f"🎯 Selected top {len(selected)} highest-quality sentences from {len(sentences)} total")
    return selected


def main():
    start_time = time.perf_counter()
    
    # Configuration
    uploads_dir = "uploads"
    pdf_path = os.path.join(uploads_dir, "sample.pdf")
    pasted_path = os.path.join(uploads_dir, "pasted_text.txt")
    selected = os.getenv("QUESTION_TYPE", "").strip().lower()
    
    # Performance optimizations
    os.environ.setdefault("RANK_METHOD", "tfidf")  # Fastest ranking method
    SENTENCE_CAP = int(os.getenv("TOP_SENTENCES", "20"))  # Default 20 sentences
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))  # Batch processing size
    USE_SMART_SELECTION = os.getenv("SMART_SELECTION", "1") == "1"
    
    print("="*60)
    print("🚀 ULTRA-FAST QUIZ GENERATION PIPELINE")
    print("="*60)
    print(f"Config: RANK_METHOD={os.getenv('RANK_METHOD', 'tfidf')}, "
          f"TOP_SENTENCES={SENTENCE_CAP}, BATCH_SIZE={BATCH_SIZE}")
    print("="*60)
    
    # 1) Preprocessing
    print("\n📄 Step 1: Loading and preprocessing text...")
    prep_start = time.perf_counter()
    
    raw_text: str
    if os.path.exists(pasted_path):
        with open(pasted_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        print(f"   ✓ Loaded pasted text ({len(raw_text):,} chars)")
        
        # Trim extremely large inputs
        MAX_CHARS = 20000
        if len(raw_text) > MAX_CHARS:
            print(f"   ⚡ Trimming to {MAX_CHARS:,} characters for speed")
            raw_text = raw_text[:MAX_CHARS]
    else:
        if not os.path.exists(pdf_path):
            raise RuntimeError(f"No input file found at {pdf_path} or {pasted_path}")
        raw_text = preprocessing.extract_text_from_pdf(pdf_path)
        print(f"   ✓ Extracted from PDF ({len(raw_text):,} chars)")
    
    if len(raw_text.strip()) < 50:
        raise RuntimeError("Input text too short (< 50 characters)")
    
    sentences, ranked_sentences, cleaned_text = preprocessing.preprocess_text(raw_text)
    preprocessing.save_outputs(sentences, ranked_sentences, cleaned_text)
    
    prep_time = time.perf_counter() - prep_start
    print(f"   ⏱️  Preprocessing: {prep_time:.2f}s")
    
    # 2) Sentence selection
    print("\n🎯 Step 2: Selecting sentences for questions...")
    select_start = time.perf_counter()
    
    use_sentences = ranked_sentences if ranked_sentences else sentences
    
    if not use_sentences:
        raise RuntimeError("No valid sentences found")
    
    # Cap sentences for performance
    if len(use_sentences) > SENTENCE_CAP:
        if USE_SMART_SELECTION:
            use_sentences = smart_sentence_selection(use_sentences, SENTENCE_CAP)
        else:
            print(f"   ⚡ Using top {SENTENCE_CAP} sentences (fast mode)")
            use_sentences = use_sentences[:SENTENCE_CAP]
    
    print(f"   ✓ Using {len(use_sentences)} sentences for generation")
    
    select_time = time.perf_counter() - select_start
    print(f"   ⏱️  Selection: {select_time:.2f}s")
    
    # Deterministic randomness
    try:
        seed_str = cleaned_text[:10000] if cleaned_text else ""
        seed_val = int(hashlib.md5(seed_str.encode("utf-8", errors="ignore")).hexdigest(), 16) % (10**8)
        random.seed(seed_val)
    except Exception:
        pass
    
    # 3) Question generation
    print("\n❓ Step 3: Generating questions...")
    gen_start = time.perf_counter()
    
    # Parse question types
    selected_types = []
    if "," in selected:
        selected_types = [t.strip().lower() for t in selected.split(",")]
    elif selected in ("", "all"):
        selected_types = ["mcq", "fill_blanks", "true_false", "short_answer"]
    else:
        selected_types = [selected.strip().lower()]
    
    # Normalize type names
    type_map = {
        "mcq": "mcq",
        "fill": "fill_blanks", "fill_blanks": "fill_blanks", 
        "fill-in-the-blanks": "fill_blanks", "fill in the blanks": "fill_blanks",
        "tf": "true_false", "true_false": "true_false", 
        "true/false": "true_false", "truefalse": "true_false", "true or false": "true_false",
        "short": "short_answer", "short_answer": "short_answer", "short answer": "short_answer"
    }
    normalized_types = [type_map.get(t, t) for t in selected_types]
    
    # Generate with batching for large inputs
    if len(use_sentences) > BATCH_SIZE:
        questions = batch_generate_questions(use_sentences, normalized_types, BATCH_SIZE)
    else:
        questions = []
        if "mcq" in normalized_types:
            questions.extend(qg.generate_mcq(use_sentences))
        if "fill_blanks" in normalized_types:
            questions.extend(qg.generate_fill(use_sentences))
        if "true_false" in normalized_types:
            questions.extend(qg.generate_true_false(use_sentences))
        if "short_answer" in normalized_types:
            questions.extend(qg.generate_short_answers(use_sentences))
    
    # Fallback if no questions generated
    if not questions:
        print("   ⚠️  No questions with selected types, generating all types...")
        questions = (
            qg.generate_mcq(use_sentences)
            + qg.generate_fill(use_sentences)
            + qg.generate_true_false(use_sentences)
            + qg.generate_short_answers(use_sentences)
        )
    
    gen_time = time.perf_counter() - gen_start
    print(f"   ✓ Generated {len(questions)} total questions")
    print(f"   ⏱️  Generation: {gen_time:.2f}s ({len(questions)/gen_time:.1f} q/s)")
    
    # Clear cache to free memory
    qg.clear_cache()
    
    # Save questions
    write_generated_questions(questions)
    
    # 4) Randomization
    print("\n🔀 Step 4: Randomizing questions...")
    rand_start = time.perf_counter()
    
    multi_type = len(normalized_types) > 1 or len({q['type'] for q in questions}) > 1
    
    source_content: str
    if multi_type:
        mcq, fill, tf, short = rz.load_questions("generated_questions.txt")
        shuffled = rz.randomize_within_types(mcq, fill, tf, short)
        rz.save_randomized(shuffled, "randomized_questions.txt")
        with open("randomized_questions.txt", "r", encoding="utf-8") as f:
            source_content = f.read().strip()
    else:
        with open("generated_questions.txt", "r", encoding="utf-8") as f:
            source_content = f.read().strip()
    
    rand_time = time.perf_counter() - rand_start
    print(f"   ⏱️  Randomization: {rand_time:.2f}s")
    
    # 5) PDF generation
    print("\n📄 Step 5: Generating PDF...")
    pdf_start = time.perf_counter()
    
    grouped = oq.group_by_type(source_content)
    oq.export_quiz_to_pdf(grouped, filename="Generated_Quiz.pdf", show_section_titles=True)
    
    pdf_time = time.perf_counter() - pdf_start
    print(f"   ⏱️  PDF generation: {pdf_time:.2f}s")
    
    # Final summary
    total_time = time.perf_counter() - start_time
    
    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETE")
    print("="*60)
    print(f"Total time: {total_time:.2f}s")
    print(f"  • Preprocessing: {prep_time:.2f}s ({prep_time/total_time*100:.1f}%)")
    print(f"  • Selection: {select_time:.2f}s ({select_time/total_time*100:.1f}%)")
    print(f"  • Generation: {gen_time:.2f}s ({gen_time/total_time*100:.1f}%)")
    print(f"  • Randomization: {rand_time:.2f}s ({rand_time/total_time*100:.1f}%)")
    print(f"  • PDF output: {pdf_time:.2f}s ({pdf_time/total_time*100:.1f}%)")
    print(f"\n📊 Generated {len(questions)} questions at {len(questions)/total_time:.1f} q/s")
    print("="*60)


if __name__ == "__main__":
    main()