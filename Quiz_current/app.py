from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, Response, session, make_response
import os
import json
from threading import Thread
import time
from functools import wraps
from datetime import datetime

# Import our modules
import extract_text
import question_generation as question_generator
import pdf_exporter
import form_builder

# Authentication system
import hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = "uploads"
FORMS_FOLDER = "forms"
USER_DATA_FOLDER = "user_data"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FORMS_FOLDER, exist_ok=True)
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

form_builder.set_forms_folder(FORMS_FOLDER)
session_data = {}


# ============ SIMPLE AUTH DATABASE ============
class AuthDB:
    def __init__(self):
        self.users_file = os.path.join(USER_DATA_FOLDER, "users.json")
        self.sessions_file = os.path.join(USER_DATA_FOLDER, "sessions.json")
        self._init()
    
    def _init(self):
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w') as f:
                json.dump({}, f)
        if not os.path.exists(self.sessions_file):
            with open(self.sessions_file, 'w') as f:
                json.dump({}, f)
    
    def _load_users(self):
        with open(self.users_file, 'r') as f:
            return json.load(f)
    
    def _save_users(self, users):
        with open(self.users_file, 'w') as f:
            json.dump(users, f, indent=2)
    
    def _load_sessions(self):
        with open(self.sessions_file, 'r') as f:
            return json.load(f)
    
    def _save_sessions(self, sessions):
        with open(self.sessions_file, 'w') as f:
            json.dump(sessions, f, indent=2)
    
    def create_user(self, email, password, username=None):
        users = self._load_users()
        if email in users:
            return None
        user_id = hashlib.sha256(email.encode()).hexdigest()[:16]
        users[email] = {
            "user_id": user_id,
            "email": email,
            "username": username or email.split('@')[0],
            "password_hash": generate_password_hash(password),
            "created_at": datetime.now().isoformat(),
            "quizzes": []
        }
        self._save_users(users)
        return user_id
    
    def verify_user(self, email, password):
        users = self._load_users()
        if email not in users:
            return None
        user = users[email]
        if check_password_hash(user['password_hash'], password):
            return user['user_id']
        return None
    
    def create_session(self, user_id, email):
        sessions = self._load_sessions()
        token = secrets.token_urlsafe(32)
        sessions[token] = {
            "user_id": user_id,
            "email": email,
            "created": datetime.now().isoformat()
        }
        self._save_sessions(sessions)
        return token
    
    def verify_session(self, token):
        sessions = self._load_sessions()
        return sessions.get(token)
    
    def delete_session(self, token):
        sessions = self._load_sessions()
        if token in sessions:
            del sessions[token]
            self._save_sessions(sessions)
    
    def add_quiz(self, email, quiz_data):
        users = self._load_users()
        if email in users:
            users[email]['quizzes'].append(quiz_data)
            self._save_users(users)
    
    def get_quizzes(self, email):
        users = self._load_users()
        return users.get(email, {}).get('quizzes', [])

auth_db = AuthDB()


# ============ AUTH DECORATOR ============
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('session_token')
        if not token:
            return redirect(url_for('login_page'))
        user = auth_db.verify_session(token)
        if not user:
            response = make_response(redirect(url_for('login_page')))
            response.set_cookie('session_token', '', expires=0)
            return response
        session['user_id'] = user['user_id']
        session['email'] = user['email']
        return f(*args, **kwargs)
    return decorated


# ============ QUIZ GENERATION PIPELINE ============
def _run_generation_pipeline(question_types, difficulty, num_questions, user_email=None):
    try:
        print(f"🚀 Starting generation: types={question_types}, difficulty={difficulty}, num={num_questions}")
        
        pdf_path = os.path.join(UPLOAD_FOLDER, "sample.pdf")
        text_path = os.path.join(UPLOAD_FOLDER, "pasted_text.txt")
        
        text = extract_text.get_text_from_input(pdf_path=pdf_path, text_path=text_path)
        print(f"✅ Extracted {len(text)} characters")
        
        if len(text.strip()) < 50:
            raise ValueError("Text too short")
        
        generator = question_generator.QuestionGenerator(difficulty=difficulty)
        questions = generator.generate_questions(text, question_types, num_questions)
        
        if not questions:
            raise ValueError("No questions generated")
        
        print(f"✅ Generated {len(questions)} questions")
        
        pdf_exporter.export_questions_to_pdf(questions, "Generated_Quiz.pdf")
        print(f"✅ PDF exported")
        
        form_result = form_builder.create_google_form(questions, "Generated Quiz")
        form_id = form_result["form_id"]
        form_link = form_result["form_link"]
        
        form_html = form_builder.generate_form_html(questions, form_id)
        form_file = os.path.join(FORMS_FOLDER, f"{form_id}.html")
        with open(form_file, "w", encoding="utf-8") as f:
            f.write(form_html)
        
        session_data["form_id"] = form_id
        session_data["form_link"] = form_link
        session_data["questions"] = questions
        
        form_data_file = os.path.join(FORMS_FOLDER, f"{form_id}.json")
        with open(form_data_file, "w", encoding="utf-8") as f:
            json.dump({"form_id": form_id, "questions": questions}, f, indent=2)
        
        print(f"✅ Form created: {form_id}")
        
        if user_email:
            quiz_record = {
                "quiz_id": form_id,
                "title": f"Quiz - {len(questions)} questions",
                "num_questions": len(questions),
                "question_types": question_types,
                "difficulty": difficulty,
                "created_at": datetime.now().isoformat(),
                "form_id": form_id
            }
            auth_db.add_quiz(user_email, quiz_record)
            print(f"✅ Saved to user history")
        
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()


# ============ PUBLIC ROUTES ============
@app.route("/")
def landing():
    token = request.cookies.get('session_token')
    if token and auth_db.verify_session(token):
        return redirect(url_for('dashboard'))
    return render_template("landing.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/signup")
def signup_page():
    return render_template("signup.html")


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    username = data.get('username', '').strip()
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    
    user_id = auth_db.create_user(email, password, username)
    if not user_id:
        return jsonify({"error": "Email already registered"}), 400
    
    token = auth_db.create_session(user_id, email)
    response = make_response(jsonify({"success": True, "redirect": "/dashboard"}))
    response.set_cookie('session_token', token, max_age=30*24*60*60, httponly=True)
    return response


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    user_id = auth_db.verify_user(email, password)
    if not user_id:
        return jsonify({"error": "Invalid email or password"}), 401
    
    token = auth_db.create_session(user_id, email)
    response = make_response(jsonify({"success": True, "redirect": "/dashboard"}))
    response.set_cookie('session_token', token, max_age=30*24*60*60, httponly=True)
    return response


@app.route("/logout")
def logout():
    token = request.cookies.get('session_token')
    if token:
        auth_db.delete_session(token)
    response = make_response(redirect(url_for('landing')))
    response.set_cookie('session_token', '', expires=0)
    return response


# ============ PROTECTED ROUTES ============
@app.route("/dashboard")
@login_required
def dashboard():
    email = session.get('email')
    quizzes = auth_db.get_quizzes(email)
    return render_template("dashboard.html", email=email, quiz_history=quizzes)


@app.route("/index")
@login_required
def index():
    return render_template("index.html")

@app.route("/create_quiz")
@login_required
def create_quiz():
    return redirect("/index")



@app.route("/prepare", methods=["POST"])
@login_required
def prepare():
    input_mode = request.form.get("input_mode", "file")
    filepath = os.path.join(UPLOAD_FOLDER, "sample.pdf")

    if input_mode == "file":
        file = request.files.get("pdf")
        if not file or file.filename == "":
            return "No file uploaded!", 400
        file.save(filepath)
        print(f"✅ Uploaded: {filepath}")
        try:
            pasted_path = os.path.join(UPLOAD_FOLDER, "pasted_text.txt")
            if os.path.exists(pasted_path):
                os.remove(pasted_path)
        except:
            pass

    elif input_mode == "text":
        text_content = request.form.get("text_content", "").strip()
        if not text_content:
            return "No text provided!", 400
        pasted_path = os.path.join(UPLOAD_FOLDER, "pasted_text.txt")
        with open(pasted_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        print(f"✅ Saved text: {len(text_content)} characters")
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass
    else:
        return "Invalid mode!", 400

    try:
        if os.path.exists("Generated_Quiz.pdf"):
            os.remove("Generated_Quiz.pdf")
    except:
        pass

    session_data.clear()
    return redirect(url_for("choose"))


@app.route("/choose")
@login_required
def choose():
    return render_template("choose.html")


@app.route("/start", methods=["POST"])
@login_required
def start_generation():
    selected_type = request.form.get("question_type", "")
    difficulty = request.form.get("difficulty", "medium")
    num_questions = int(request.form.get("num_questions", 10))
    user_email = session.get('email')
    
    if not selected_type:
        question_types = ["mcq", "fill_blanks", "true_false", "short_answer"]
    elif "," in selected_type:
        question_types = [t.strip().lower() for t in selected_type.split(",")]
    else:
        question_types = [selected_type.strip().lower()]
    
    type_map = {
        "mcq": "mcq",
        "fill": "fill_blanks", "fill_blanks": "fill_blanks",
        "fill-in-the-blanks": "fill_blanks", "fill in the blanks": "fill_blanks",
        "tf": "true_false", "true_false": "true_false",
        "true/false": "true_false", "truefalse": "true_false",
        "short": "short_answer", "short_answer": "short_answer"
    }
    question_types = [type_map.get(t, t) for t in question_types]
    
    if difficulty not in ["easy", "medium", "hard"]:
        difficulty = "medium"
    
    num_questions = max(5, min(50, num_questions))
    
    session_data["question_types"] = question_types
    session_data["difficulty"] = difficulty
    session_data["num_questions"] = num_questions
    
    Thread(target=_run_generation_pipeline, 
           args=(question_types, difficulty, num_questions, user_email), 
           daemon=True).start()
    
    return redirect(url_for("processing"))


@app.route("/processing")
@login_required
def processing():
    return render_template("processing.html")


@app.route("/status")
@login_required
def status():
    ready = os.path.exists("Generated_Quiz.pdf")
    return jsonify({"ready": ready})


@app.route("/result")
@login_required
def result():
    if not os.path.exists("Generated_Quiz.pdf"):
        return "Quiz generation failed!", 500
    
    form_link = session_data.get("form_link")
    if not form_link:
        form_files = [f for f in os.listdir(FORMS_FOLDER) if f.endswith(".json")]
        if form_files:
            form_files.sort(key=lambda x: os.path.getmtime(os.path.join(FORMS_FOLDER, x)), reverse=True)
            latest_form_id = form_files[0].replace(".json", "")
            form_link = f"/form/{latest_form_id}"
    
    return render_template("result.html", form_link=form_link)


@app.route("/download")
@login_required
def download():
    if os.path.exists("Generated_Quiz.pdf"):
        return send_file("Generated_Quiz.pdf", as_attachment=True)
    return "PDF not found", 404


@app.route("/view_pdf")
@login_required
def view_pdf():
    pdf_path = os.path.join(UPLOAD_FOLDER, "sample.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype="application/pdf")
    return "PDF not found", 404


@app.route("/view_generated")
@login_required
def view_generated():
    if os.path.exists("Generated_Quiz.pdf"):
        return send_file("Generated_Quiz.pdf", mimetype="application/pdf", as_attachment=False)
    return "Quiz not found", 404


@app.route("/viewer_pdf")
@login_required
def viewer_pdf():
    if os.path.exists("Generated_Quiz.pdf"):
        return send_file("Generated_Quiz.pdf", mimetype="application/pdf", as_attachment=False)
    return "Quiz not found", 404


@app.route("/form/<form_id>")
def view_form(form_id):
    form_file = os.path.join(FORMS_FOLDER, f"{form_id}.html")
    if os.path.exists(form_file):
        with open(form_file, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="text/html")
    return "Form not found", 404


@app.route("/api/score", methods=["POST"])
def score_quiz():
    try:
        data = request.get_json()
        form_id = data.get("form_id")
        responses = data.get("responses", {})
        
        if not form_id:
            return jsonify({"error": "form_id required"}), 400
        
        result = form_builder.submit_quiz_response(form_id, responses)
        if "error" in result:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/answers/<form_id>")
def get_answers(form_id):
    try:
        answers = form_builder.get_form_answers(form_id)
        if answers:
            return jsonify(answers)
        return jsonify({"error": "Form not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)