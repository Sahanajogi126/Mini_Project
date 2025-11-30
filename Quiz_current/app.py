from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, Response
import os
import json
from threading import Thread
import time

# Import our modules
import extract_text
import question_generator
import pdf_exporter
import form_builder

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
FORMS_FOLDER = "forms"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FORMS_FOLDER, exist_ok=True)

# Initialize form builder with forms folder
form_builder.set_forms_folder(FORMS_FOLDER)

# Store session data (in production, use proper session management)
session_data = {}

# --- Ensure templates/viewer.html exists (auto-create if missing) ---
_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(_templates_dir, exist_ok=True)
_viewer_path = os.path.join(_templates_dir, "viewer.html")
if not os.path.exists(_viewer_path):
    _viewer_html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Generated Quiz</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html,body{height:100%;margin:0;background:#fff;font-family:Arial,Helvetica,sans-serif}
    .pdf-wrap{width:100%;height:100vh;display:flex;justify-content:center;align-items:flex-start}
    iframe{width:100%;height:100vh;border:0}
  </style>
</head>
<body>
  <div class="pdf-wrap">
    <iframe id="pdfFrame" src="{{ url_for('viewer_pdf') }}"></iframe>
  </div>
</body>
</html>"""
    with open(_viewer_path, "w", encoding="utf-8") as _f:
        _f.write(_viewer_html)


def _run_generation_pipeline(question_types: list, difficulty: str, num_questions: int):
    """Run the complete question generation pipeline"""
    try:
        print(f"🚀 Starting generation: types={question_types}, difficulty={difficulty}, num={num_questions}")
        
        # Step 1: Extract text
        pdf_path = os.path.join(UPLOAD_FOLDER, "sample.pdf")
        text_path = os.path.join(UPLOAD_FOLDER, "pasted_text.txt")
        
        text = extract_text.get_text_from_input(pdf_path=pdf_path, text_path=text_path)
        print(f"✅ Extracted {len(text)} characters of text")
        
        if len(text.strip()) < 50:
            raise ValueError("Input text too short (< 50 characters)")
        
        # Step 2: Generate questions
        generator = question_generator.QuestionGenerator(difficulty=difficulty)
        questions = generator.generate_questions(
            text=text,
            question_types=question_types,
            num_questions=num_questions
        )
        
        if not questions:
            raise ValueError("No questions generated")
        
        print(f"✅ Generated {len(questions)} questions")
        
        # Step 3: Export to PDF
        pdf_exporter.export_questions_to_pdf(questions, "Generated_Quiz.pdf")
        print(f"✅ PDF exported")
        
        # Step 4: Create Google Form
        form_result = form_builder.create_google_form(questions, "Generated Quiz")
        form_id = form_result["form_id"]
        form_link = form_result["form_link"]
        
        # Save form HTML with proper API endpoint
        form_html = form_builder.generate_form_html(questions, form_id)
        form_file = os.path.join(FORMS_FOLDER, f"{form_id}.html")
        with open(form_file, "w", encoding="utf-8") as f:
            f.write(form_html)
        
        # Store form data in session (using absolute URL for form link)
        session_data["form_id"] = form_id
        session_data["form_link"] = form_link
        session_data["questions"] = questions
        
        # Also save form data to file for persistence
        form_data_file = os.path.join(FORMS_FOLDER, f"{form_id}.json")
        with open(form_data_file, "w", encoding="utf-8") as f:
            json.dump({"form_id": form_id, "questions": questions}, f, indent=2)
        
        print(f"✅ Form created: {form_id}")
        
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/prepare", methods=["POST"])
def prepare():
    input_mode = request.form.get("input_mode", "file")
    filepath = os.path.join(UPLOAD_FOLDER, "sample.pdf")

    # Handle file upload mode
    if input_mode == "file":
        file = request.files.get("pdf")
        if not file or file.filename == "":
            return "No file uploaded!", 400
        file.save(filepath)
        print(f"✅ Uploaded: {filepath}")
        # Remove any pasted text file if present
        try:
            pasted_path = os.path.join(UPLOAD_FOLDER, "pasted_text.txt")
            if os.path.exists(pasted_path):
                os.remove(pasted_path)
        except Exception:
            pass

    # Handle text mode
    elif input_mode == "text":
        text_content = request.form.get("text_content", "").strip()
        if not text_content:
            return "No text content provided!", 400
        pasted_path = os.path.join(UPLOAD_FOLDER, "pasted_text.txt")
        with open(pasted_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        print(f"✅ Saved pasted text: {len(text_content)} characters")
        # Remove uploaded PDF if present
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
    else:
        return "Invalid input mode!", 400

    # Remove previous output if exists
    try:
        if os.path.exists("Generated_Quiz.pdf"):
            os.remove("Generated_Quiz.pdf")
    except Exception:
        pass

    # Clear session data
    session_data.clear()

    # Go to choose step
    return redirect(url_for("choose"))


@app.route("/start", methods=["POST"])
def start_generation():
    selected_type = request.form.get("question_type", "")
    difficulty = request.form.get("difficulty", "medium")
    num_questions = int(request.form.get("num_questions", 10))
    
    # Parse question types
    if not selected_type:
        question_types = ["mcq", "fill_blanks", "true_false", "short_answer"]
    elif "," in selected_type:
        question_types = [t.strip().lower() for t in selected_type.split(",")]
    else:
        question_types = [selected_type.strip().lower()]
    
    # Normalize type names
    type_map = {
        "mcq": "mcq",
        "fill": "fill_blanks", "fill_blanks": "fill_blanks",
        "fill-in-the-blanks": "fill_blanks", "fill in the blanks": "fill_blanks",
        "tf": "true_false", "true_false": "true_false",
        "true/false": "true_false", "truefalse": "true_false", "true or false": "true_false",
        "short": "short_answer", "short_answer": "short_answer", "short answer": "short_answer"
    }
    question_types = [type_map.get(t, t) for t in question_types]
    
    # Validate difficulty
    if difficulty not in ["easy", "medium", "hard"]:
        difficulty = "medium"
    
    # Validate num_questions
    num_questions = max(5, min(50, num_questions))
    
    print(f"📋 Generation params: types={question_types}, difficulty={difficulty}, num={num_questions}")
    
    # Store in session
    session_data["question_types"] = question_types
    session_data["difficulty"] = difficulty
    session_data["num_questions"] = num_questions
    
    # Start generation in background thread
    Thread(target=_run_generation_pipeline, args=(question_types, difficulty, num_questions), daemon=True).start()
    
    return redirect(url_for("processing"))


@app.route("/result")
def result():
    if not os.path.exists("Generated_Quiz.pdf"):
        return "Quiz generation failed! Please try again.", 500
    
    # Get form link from session or find latest form
    form_link = session_data.get("form_link", None)
    if not form_link:
        # Try to find the latest form file
        form_files = [f for f in os.listdir(FORMS_FOLDER) if f.endswith(".json")]
        if form_files:
            # Get the most recent form
            form_files.sort(key=lambda x: os.path.getmtime(os.path.join(FORMS_FOLDER, x)), reverse=True)
            latest_form_id = form_files[0].replace(".json", "")
            form_link = f"/form/{latest_form_id}"
    
    return render_template("result.html", form_link=form_link)


@app.route("/choose")
def choose():
    return render_template("choose.html")


@app.route("/processing")
def processing():
    return render_template("processing.html")


@app.route("/status")
def status():
    ready = os.path.exists("Generated_Quiz.pdf")
    return jsonify({"ready": ready})


@app.route("/download")
def download():
    pdf_path = os.path.abspath("Generated_Quiz.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype="application/pdf", as_attachment=True)
    return "PDF not found", 404


@app.route("/view_pdf")
def view_pdf():
    pdf_path = os.path.join(UPLOAD_FOLDER, "sample.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype="application/pdf")
    return "PDF not found", 404


@app.route("/view_generated")
def view_generated():
    pdf_path = os.path.abspath("Generated_Quiz.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype="application/pdf", as_attachment=False)
    return "Generated quiz not found", 404


@app.route("/viewer_pdf")
def viewer_pdf():
    if os.path.exists("Generated_Quiz.pdf"):
        return send_file("Generated_Quiz.pdf", mimetype="application/pdf", as_attachment=False)
    return "Generated quiz not found", 404


@app.route("/form/<form_id>")
def view_form(form_id):
    """View the generated quiz form"""
    form_file = os.path.join(FORMS_FOLDER, f"{form_id}.html")
    if os.path.exists(form_file):
        with open(form_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        return Response(html_content, mimetype="text/html")
    return "Form not found", 404


@app.route("/api/score", methods=["POST"])
def score_quiz():
    """API endpoint for scoring quiz responses"""
    try:
        data = request.get_json()
        form_id = data.get("form_id")
        responses = data.get("responses", {})
        
        if not form_id:
            return jsonify({"error": "form_id is required"}), 400
        
        # Submit response and get score
        result = form_builder.submit_quiz_response(form_id, responses)
        
        if "error" in result:
            return jsonify(result), 404
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/answers/<form_id>")
def get_answers(form_id):
    """API endpoint to get correct answers for a form"""
    try:
        answers = form_builder.get_form_answers(form_id)
        if answers:
            return jsonify(answers)
        return jsonify({"error": "Form not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
