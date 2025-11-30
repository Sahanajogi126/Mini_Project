# ---------------------------------------------------------
# randomization.py - supports Short Answer (Final Version)
# ---------------------------------------------------------
import random
import re
import os

def load_questions(file_path="generated_questions.txt"):
    if not os.path.exists(file_path):
        print("⚠ 'generated_questions.txt' not found.")
        return [], [], [], []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    blocks = re.split(r"\n\s*\n", content)
    mcq, fill, tf, short = [], [], [], []

    for block in blocks:
        b = block.strip().lower()
        if "(mcq)" in b:
            mcq.append(block.strip())
        elif "(fill" in b and "blank" in b:
            fill.append(block.strip())
        elif "(true" in b and ("false" in b or "true/false" in b):
            tf.append(block.strip())
        elif "(short answer" in b:
            short.append(block.strip())

    return mcq, fill, tf, short

def randomize_within_types(mcq, fill, tf, short):
    print(f"📘 Before shuffle: {len(mcq)} MCQ | {len(fill)} Fill | {len(tf)} TF | {len(short)} Short")
    random.shuffle(mcq)
    random.shuffle(fill)
    random.shuffle(tf)
    random.shuffle(short)
    return mcq + fill + tf + short

def save_randomized(questions, output_path="randomized_questions.txt"):
    if not questions:
        print("⚠ No questions to save.")
        return
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(questions))
    print(f"✅ Saved randomized questions to {output_path}")

if __name__ == "__main__":
    mcq, fill, tf, short = load_questions()

    if not (mcq or fill or tf or short):
        print("⚠ No valid questions detected.")
    else:
        shuffled = randomize_within_types(mcq, fill, tf, short)
        print(f"🧩 After shuffle: {len(mcq)} MCQ | {len(fill)} Fill | {len(tf)} TF | {len(short)} Short")
        save_randomized(shuffled)
