# ---------------------------------------------------------
# output_quiz.py - adds Short Answer section (Final Version)
# ---------------------------------------------------------
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from textwrap import wrap
import os
import re

def detect_source_file():
    if os.path.exists("randomized_questions.txt"):
        print("📄 Using randomized_questions.txt as source.")
        return "randomized_questions.txt"
    elif os.path.exists("generated_questions.txt"):
        print("📄 Using generated_questions.txt as source.")
        return "generated_questions.txt"
    else:
        print("⚠ No question file found.")
        exit()

def group_by_type(content):
    blocks = re.split(r"\n\s*\n", content)
    grouped = {"MCQ": [], "Fill": [], "TF": [], "Short": []}

    for b in blocks:
        b_lower = b.lower()
        if "(mcq)" in b_lower:
            grouped["MCQ"].append(b.strip())
        elif "(fill" in b_lower and "blank" in b_lower:
            grouped["Fill"].append(b.strip())
        elif "(true" in b_lower and ("false" in b_lower or "true/false" in b_lower):
            grouped["TF"].append(b.strip())
        elif "(short answer" in b_lower:
            grouped["Short"].append(b.strip())

    return grouped

def draw_section_title(c, title, y, width):
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, title)
    c.setFont("Helvetica", 12)
    return y - 25

def export_quiz_to_pdf(grouped, filename="Generated_Quiz.pdf", show_section_titles=None):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    y = height - 80
    left_margin = 60
    line_spacing = 16
    max_width = 90

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 50, "AUTOMATED QUIZ GENERATOR")
    c.setFont("Helvetica", 12)

    sections = [
        ("Part A – Multiple Choice Questions", grouped["MCQ"]),
        ("Part B – Fill in the Blanks", grouped["Fill"]),
        ("Part C – True or False", grouped["TF"]),
        ("Part D – Short Answer Questions", grouped["Short"])
    ]

    # Use parameter if explicitly provided, otherwise fall back to env var
    if show_section_titles is None:
        show_section_titles = os.getenv("SHOW_SECTION_TITLES", "0").strip() not in ("0", "false", "False", "no", "No")

    for title, questions in sections:
        if not questions:
            continue
        if show_section_titles:
            y = draw_section_title(c, title, y, width)
        for i, q in enumerate(questions, 1):
            q_text = re.sub(r"Answer:.*", "", q).strip()
            # Remove leading type label like (MCQ) or (True/False)
            q_text = re.sub(r"^\s*\([^)]*\)\s*", "", q_text)
            
            # For short answer questions, remove "Context:" lines
            if title == "Part D – Short Answer Questions":
                lines_temp = q_text.splitlines()
                q_text = "\n".join([line for line in lines_temp if not line.strip().lower().startswith("context:")])
                q_text = q_text.strip()

            # Render respecting explicit newlines (so options remain vertical)
            lines = q_text.splitlines() if "\n" in q_text else [q_text]
            first_line = True
            for raw_line in lines:
                wrapped = wrap(raw_line, max_width) or [""]
                for idx, line in enumerate(wrapped):
                    prefix = f"{i}) " if first_line and idx == 0 else "   "
                    c.drawString(left_margin, y, prefix + line)
                    y -= line_spacing
                first_line = False

            ans_match = re.search(r"Answer:\s*(.*)", q)
            if ans_match:
                ans = ans_match.group(1)
                c.setFont("Helvetica-Oblique", 11)
                c.drawString(left_margin + 15, y, f"Answer: {ans}")
                c.setFont("Helvetica", 12)
                y -= line_spacing
            y -= 10

            if y < 100:
                c.showPage()
                y = height - 80
                c.setFont("Helvetica", 12)

    c.save()
    print(f"✅ Quiz exported successfully to {filename}")

if __name__ == "__main__":
    src = detect_source_file()
    with open(src, "r", encoding="utf-8") as f:
        content = f.read().strip()
    grouped = group_by_type(content)
    export_quiz_to_pdf(grouped)
