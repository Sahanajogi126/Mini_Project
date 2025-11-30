"""
form_builder.py - Google Forms Integration Module
Creates Google Forms programmatically and provides scoring API.
"""
import json
import uuid
from typing import List, Dict, Optional
import os


class GoogleFormBuilder:
    """Builder for Google Forms (simulated for offline use)"""
    
    def __init__(self, forms_folder="forms"):
        self.forms_data = {}  # Store form data locally
        self.responses_data = {}  # Store responses for scoring
        self.forms_folder = forms_folder
        os.makedirs(forms_folder, exist_ok=True)
        self._load_forms_from_disk()
    
    def _load_forms_from_disk(self):
        """Load form data from disk if available"""
        if not os.path.exists(self.forms_folder):
            return
        
        for filename in os.listdir(self.forms_folder):
            if filename.endswith(".json"):
                form_id = filename.replace(".json", "")
                try:
                    with open(os.path.join(self.forms_folder, filename), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.forms_data[form_id] = {
                            "id": form_id,
                            "title": "Generated Quiz",
                            "questions": data.get("questions", []),
                            "created_at": data.get("created_at", "")
                        }
                except Exception as e:
                    print(f"⚠️ Error loading form {form_id}: {e}")
    
    def create_form(self, questions: List[Dict], title: str = "Generated Quiz") -> Dict:
        """
        Create a Google Form (simulated).
        In a real implementation, this would use Google Forms API.
        
        Args:
            questions: List of question dictionaries
            title: Form title
            
        Returns:
            Dictionary with form_id and form_link
        """
        form_id = str(uuid.uuid4())
        
        # Store form data
        form_data = {
            "id": form_id,
            "title": title,
            "questions": questions,
            "created_at": str(uuid.uuid4())  # Simulated timestamp
        }
        
        self.forms_data[form_id] = form_data
        
        # Save to disk for persistence
        try:
            form_data_file = os.path.join(self.forms_folder, f"{form_id}.json")
            with open(form_data_file, "w", encoding="utf-8") as f:
                json.dump({"form_id": form_id, "questions": questions, "created_at": form_data["created_at"]}, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving form to disk: {e}")
        
        # Generate a local form link (in real implementation, this would be a Google Forms URL)
        # For offline use, we'll serve the form via Flask route
        form_link = f"/form/{form_id}"
        
        print(f"✅ Created form: {form_id}")
        print(f"📝 Form link: {form_link}")
        
        return {
            "form_id": form_id,
            "form_link": form_link,
            "form_data": form_data
        }
    
    def get_form_questions(self, form_id: str) -> Optional[List[Dict]]:
        """Get questions for a form"""
        if form_id in self.forms_data:
            return self.forms_data[form_id]["questions"]
        return None
    
    def submit_response(self, form_id: str, responses: Dict) -> Dict:
        """
        Submit a quiz response.
        
        Args:
            form_id: Form identifier
            responses: Dictionary mapping question indices to answers
            
        Returns:
            Score and feedback
        """
        if form_id not in self.forms_data:
            return {"error": "Form not found"}
        
        questions = self.forms_data[form_id]["questions"]
        correct_answers = {}
        user_answers = {}
        score = 0
        total = len(questions)
        
        # Calculate score
        for i, q in enumerate(questions):
            correct_answer = q.get('answer', '').strip().lower()
            user_answer = responses.get(str(i), '').strip().lower()
            
            correct_answers[i] = q.get('answer', '')
            user_answers[i] = responses.get(str(i), '')
            
            # Check if answer is correct
            if user_answer == correct_answer:
                score += 1
        
        # Store response
        response_id = str(uuid.uuid4())
        self.responses_data[response_id] = {
            "form_id": form_id,
            "score": score,
            "total": total,
            "responses": responses,
            "correct_answers": correct_answers
        }
        
        return {
            "response_id": response_id,
            "score": score,
            "total": total,
            "percentage": round((score / total * 100), 2) if total > 0 else 0,
            "correct_answers": correct_answers,
            "user_answers": user_answers
        }
    
    def get_correct_answers(self, form_id: str) -> Optional[Dict]:
        """Get correct answers for a form"""
        if form_id not in self.forms_data:
            return None
        
        questions = self.forms_data[form_id]["questions"]
        answers = {}
        
        for i, q in enumerate(questions):
            answers[i] = {
                "question": q.get('question', ''),
                "answer": q.get('answer', ''),
                "type": q.get('type', ''),
                "options": q.get('options', [])
            }
        
        return answers


# Global instance (will be initialized with forms folder)
_form_builder = None
_default_forms_folder = "forms"

def _get_form_builder():
    """Get or create the global form builder instance"""
    global _form_builder, _default_forms_folder
    if _form_builder is None:
        _form_builder = GoogleFormBuilder(forms_folder=_default_forms_folder)
    return _form_builder

def set_forms_folder(folder_path: str):
    """Set the forms folder path (call before first use)"""
    global _default_forms_folder, _form_builder
    _default_forms_folder = folder_path
    if _form_builder is not None:
        _form_builder = GoogleFormBuilder(forms_folder=folder_path)


def create_google_form(questions: List[Dict], title: str = "Generated Quiz") -> Dict:
    """
    Create a Google Form from questions.
    
    Args:
        questions: List of question dictionaries
        title: Form title
        
    Returns:
        Dictionary with form_id and form_link
    """
    return _get_form_builder().create_form(questions, title)


def submit_quiz_response(form_id: str, responses: Dict) -> Dict:
    """
    Submit quiz responses and get score.
    
    Args:
        form_id: Form identifier
        responses: Dictionary mapping question indices to answers
        
    Returns:
        Score and feedback dictionary
    """
    return _get_form_builder().submit_response(form_id, responses)


def get_form_answers(form_id: str) -> Optional[Dict]:
    """Get correct answers for a form"""
    return _get_form_builder().get_correct_answers(form_id)


def get_form_questions(form_id: str) -> Optional[List[Dict]]:
    """Get questions for a form"""
    return _get_form_builder().get_form_questions(form_id)


# HTML form generator for offline use
def generate_form_html(questions: List[Dict], form_id: str) -> str:
    """
    Generate HTML form for offline quiz taking.
    
    Args:
        questions: List of question dictionaries
        form_id: Form identifier
        
    Returns:
        HTML string
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Quiz Form</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .question {{
                background: white;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .question h3 {{
                margin-top: 0;
            }}
            .options {{
                margin: 10px 0;
            }}
            .options label {{
                display: block;
                padding: 8px;
                margin: 5px 0;
                background: #f9f9f9;
                border-radius: 4px;
                cursor: pointer;
            }}
            .options input[type="radio"] {{
                margin-right: 10px;
            }}
            input[type="text"] {{
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
            }}
            button {{
                background: #6c63ff;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                margin-top: 20px;
            }}
            button:hover {{
                background: #5a52e5;
            }}
        </style>
    </head>
    <body>
        <h1>Quiz Form</h1>
        <form id="quizForm" onsubmit="submitQuiz(event)">
    """
    
    for i, q in enumerate(questions):
        q_type = q.get('type', '')
        question_text = q.get('question', '')
        
        html += f'<div class="question">'
        html += f'<h3>Question {i+1}: {question_text}</h3>'
        
        if q_type == 'MCQ' and q.get('options'):
            html += '<div class="options">'
            option_labels = ['A', 'B', 'C', 'D']
            for opt_idx, option in enumerate(q.get('options', [])):
                label = option_labels[opt_idx] if opt_idx < len(option_labels) else chr(ord('A') + opt_idx)
                html += f'''
                <label>
                    <input type="radio" name="q{i}" value="{option}">
                    {label}) {option}
                </label>
                '''
            html += '</div>'
        elif 'True/False' in q_type:
            html += '<div class="options">'
            html += f'<label><input type="radio" name="q{i}" value="True"> True</label>'
            html += f'<label><input type="radio" name="q{i}" value="False"> False</label>'
            html += '</div>'
        else:
            html += f'<input type="text" name="q{i}" placeholder="Enter your answer">'
        
        html += '</div>'
    
    html += f'''
            <button type="submit">Submit Quiz</button>
        </form>
        
        <div id="results" style="display:none; margin-top: 30px; padding: 20px; background: white; border-radius: 8px;">
            <h2>Results</h2>
            <div id="score"></div>
            <div id="answers"></div>
            <div style="margin-top: 20px; text-align: center;">
                <a href="/" style="display: inline-block; background: linear-gradient(90deg, #6c63ff 0%, #ff63c3 100%);
                   color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; 
                   font-size: 16px; font-weight: 600; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(108, 99, 255, 0.3);"
                   onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(108, 99, 255, 0.4)';"
                   onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(108, 99, 255, 0.3)';">
                    Generate Another Quiz
                </a>
            </div>
        </div>
        
        <script>
            function submitQuiz(event) {{
                event.preventDefault();
                const form = document.getElementById('quizForm');
                const formData = new FormData(form);
                const responses = {{}};
                
                for (let i = 0; i < {len(questions)}; i++) {{
                    const answer = formData.get(`q${{i}}`);
                    if (answer) {{
                        responses[i] = answer;
                    }}
                }}
                
                fetch('/api/score', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        form_id: '{form_id}',
                        responses: responses
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('results').style.display = 'block';
                    document.getElementById('score').innerHTML = 
                        `<h3>Score: ${{data.score}}/${{data.total}} (${{data.percentage}}%)</h3>`;
                    
                    let answersHtml = '<h4>Correct Answers:</h4><ul>';
                    for (let i in data.correct_answers) {{
                        answersHtml += `<li>Question ${{parseInt(i)+1}}: ${{data.correct_answers[i]}}</li>`;
                    }}
                    answersHtml += '</ul>';
                    document.getElementById('answers').innerHTML = answersHtml;
                    
                    // Scroll to results section
                    document.getElementById('results').scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error submitting quiz. Please try again.');
                }});
            }}
        </script>
    </body>
    </html>
    '''
    
    return html


if __name__ == "__main__":
    # Test form creation
    test_questions = [
        {
            "type": "MCQ",
            "question": "What is machine learning?",
            "options": ["A subset of AI", "A programming language", "A database"],
            "answer": "A subset of AI"
        }
    ]
    
    result = create_google_form(test_questions, "Test Quiz")
    print(f"Form created: {result['form_id']}")
    print(f"Form link: {result['form_link']}")

