"""
pdf_exporter.py - PDF Export Module
Exports generated questions to a formatted PDF file.
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from textwrap import wrap
from typing import List, Dict
import re


def export_questions_to_pdf(questions: List[Dict], filename: str = "Generated_Quiz.pdf") -> None:
    """
    Export questions to a PDF file.
    
    Args:
        questions: List of question dictionaries
        filename: Output PDF filename
    """
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    y = height - 80
    left_margin = 60
    line_spacing = 16
    max_width = 90
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 50, "AUTOMATED QUIZ GENERATOR")
    c.setFont("Helvetica", 12)
    y -= 30
    
    # Group questions by type
    grouped = {"MCQ": [], "Fill-in-the-Blank": [], "True/False": [], "Short Answer": []}
    for q in questions:
        q_type = q.get('type', '')
        if q_type == "MCQ":
            grouped["MCQ"].append(q)
        elif "Fill" in q_type:
            grouped["Fill-in-the-Blank"].append(q)
        elif "True" in q_type or "False" in q_type:
            grouped["True/False"].append(q)
        elif "Short" in q_type:
            grouped["Short Answer"].append(q)
    
    # Section titles
    sections = [
        ("Part A – Multiple Choice Questions", grouped["MCQ"]),
        ("Part B – Fill in the Blanks", grouped["Fill-in-the-Blank"]),
        ("Part C – True or False", grouped["True/False"]),
        ("Part D – Short Answer Questions", grouped["Short Answer"])
    ]
    
    for title, q_list in sections:
        if not q_list:
            continue
        
        # Section title
        c.setFont("Helvetica-Bold", 14)
        y -= 20
        if y < 100:
            c.showPage()
            y = height - 80
        c.drawCentredString(width / 2, y, title)
        c.setFont("Helvetica", 12)
        y -= 25
        
        # Questions
        for i, q in enumerate(q_list, 1):
            question_text = q.get('question', '')
            
            # Wrap and draw question
            wrapped = wrap(question_text, max_width) or [""]
            for idx, line in enumerate(wrapped):
                prefix = f"{i}) " if idx == 0 else "   "
                if y < 100:
                    c.showPage()
                    y = height - 80
                    c.setFont("Helvetica", 12)
                c.drawString(left_margin, y, prefix + line)
                y -= line_spacing
            
            # Options for MCQ
            if q.get('type') == 'MCQ' and q.get('options'):
                option_labels = ['A)', 'B)', 'C)', 'D)']
                for opt_idx, option in enumerate(q.get('options', [])):
                    label = option_labels[opt_idx] if opt_idx < len(option_labels) else chr(ord('A') + opt_idx) + ')'
                    opt_wrapped = wrap(f"{label} {option}", max_width) or [""]
                    for line in opt_wrapped:
                        if y < 100:
                            c.showPage()
                            y = height - 80
                            c.setFont("Helvetica", 12)
                        c.drawString(left_margin + 15, y, line)
                        y -= line_spacing
            
            # Answer
            answer = q.get('answer', '')
            if answer:
                c.setFont("Helvetica-Oblique", 11)
                ans_wrapped = wrap(f"Answer: {answer}", max_width) or [""]
                for line in ans_wrapped:
                    if y < 100:
                        c.showPage()
                        y = height - 80
                        c.setFont("Helvetica-Oblique", 11)
                    c.drawString(left_margin + 15, y, line)
                    y -= line_spacing
                c.setFont("Helvetica", 12)
            
            y -= 10  # Space between questions
    
    c.save()
    print(f"✅ Quiz exported successfully to {filename}")


if __name__ == "__main__":
    # Test export
    test_questions = [
        {
            "type": "MCQ",
            "question": "What is machine learning?",
            "options": ["A subset of AI", "A programming language", "A database", "A web framework"],
            "answer": "A subset of AI"
        },
        {
            "type": "Fill-in-the-Blank",
            "question": "Neural networks are inspired by _____ networks.",
            "answer": "biological"
        }
    ]
    
    export_questions_to_pdf(test_questions, "test_quiz.pdf")
    print("✅ Test PDF created")

