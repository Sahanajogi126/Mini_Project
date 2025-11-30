import time
from question_generation import generate_mcq, generate_fill, generate_true_false, generate_short_answers

# Load sentences
with open('ranked_sentences.txt', 'r', encoding='utf-8') as f:
    sentences = [line.strip() for line in f if line.strip()]

print(f"Loaded {len(sentences)} sentences for perf test.")

start = time.perf_counter()
mcq = generate_mcq(sentences)
mcq_time = time.perf_counter() - start
print(f"MCQ time: {mcq_time:.4f}s -> {len(mcq)} questions")

start = time.perf_counter()
fill = generate_fill(sentences)
fill_time = time.perf_counter() - start
print(f"Fill-in time: {fill_time:.4f}s -> {len(fill)} questions")

start = time.perf_counter()
tf = generate_true_false(sentences)
tf_time = time.perf_counter() - start
print(f"TF time: {tf_time:.4f}s -> {len(tf)} questions")

start = time.perf_counter()
short = generate_short_answers(sentences)
short_time = time.perf_counter() - start
print(f"Short Answer time: {short_time:.4f}s -> {len(short)} questions")

print('\nSummary (seconds):')
print(f'MCQ: {mcq_time:.4f}, Fill: {fill_time:.4f}, TF: {tf_time:.4f}, Short: {short_time:.4f}')
