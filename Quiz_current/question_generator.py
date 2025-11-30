"""
question_generator.py - BERT/DistilBERT-based Question Generation
Uses transformer models to generate human-like, non-AI-detectable questions.
"""
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import random
import re
# Try to import optimized generation routines (faster TF generation)
try:
    import question_generation as qgen_opt
except Exception:
    qgen_opt = None
from typing import List, Dict, Optional
import os


class QuestionGenerator:
    """Question generator using DistilBERT/BERT-based models"""
    
    def __init__(self, difficulty: str = "medium"):
        """
        Initialize the question generator.
        
        Args:
            difficulty: "easy", "medium", or "hard"
        """
        self.difficulty = difficulty
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔧 Using device: {self.device}")
        
        # Load model based on difficulty
        self._load_model()
        
    def _load_model(self):
        """Load appropriate model for question generation"""
        try:
            # Use a question generation model (works offline after first download)
            # Using a smaller, faster model that works well offline
            model_name = "valhalla/t5-small-e2e-qg"  # Works offline after initial download
            
            print(f"📥 Loading model: {model_name}...")
            print("   (First run will download the model - this may take a few minutes)")
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=False)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, local_files_only=False)
            self.model.to(self.device)
            self.model.eval()
            
            # Also load a simpler model for MCQ generation
            try:
                self.qg_pipeline = pipeline(
                    "text2text-generation",
                    model=model_name,
                    tokenizer=model_name,
                    device=0 if self.device == "cuda" else -1
                )
            except Exception as e:
                print(f"   ⚠️ Pipeline creation failed: {e}")
                self.qg_pipeline = None
                
            print("✅ Model loaded successfully")
        except Exception as e:
            print(f"⚠️ Model loading failed: {e}")
            print("⚠️ Falling back to rule-based generation (works offline)")
            self.model = None
            self.tokenizer = None
            self.qg_pipeline = None
    
    def _generate_with_model(self, context: str, answer: str = None) -> Optional[str]:
        """Generate question using the loaded model"""
        if not self.qg_pipeline:
            return None
        
        try:
            # Format input for question generation
            if answer:
                input_text = f"generate question: {context} answer: {answer}"
            else:
                input_text = f"generate question: {context}"
            
            # Generate question
            result = self.qg_pipeline(
                input_text,
                max_length=128,
                num_beams=4,
                early_stopping=True,
                do_sample=True,
                temperature=0.7 if self.difficulty == "easy" else (0.8 if self.difficulty == "medium" else 0.9)
            )
            
            question = result[0]['generated_text'].strip()
            # Clean up the question
            question = re.sub(r'^(question|q):\s*', '', question, flags=re.IGNORECASE)
            question = question.strip('?').strip() + '?'
            return question
        except Exception as e:
            print(f"⚠️ Model generation failed: {e}")
            return None
    
    def _generate_rule_based_mcq(self, sentence: str) -> Optional[Dict]:
        """Fallback rule-based MCQ generation"""
        import nltk
        from nltk import pos_tag, word_tokenize
        
        try:
            words = word_tokenize(sentence)
            tagged = pos_tag(words)
            
            # Find key nouns
            nouns = [w for w, t in tagged if t.startswith('NN') and w.isalpha() and len(w) >= 4]
            if not nouns:
                return None
            
            answer = random.choice(nouns)
            
            # Create question by masking the answer
            pattern = r"\b" + re.escape(answer) + r"\b"
            question = re.sub(pattern, "_____", sentence, count=1, flags=re.IGNORECASE)
            if question == sentence:
                return None
            
            # Generate distractors
            other_nouns = [w for w, t in tagged if t.startswith('NN') and 
                          w.lower() != answer.lower() and w.isalpha() and len(w) >= 4]
            
            if len(other_nouns) < 3:
                # Add generic distractors
                generic = ["concept", "element", "factor", "component", "aspect"]
                distractors = random.sample(generic, min(3, len(generic)))
            else:
                distractors = random.sample(other_nouns, 3)
            
            options = [answer] + distractors
            random.shuffle(options)
            
            return {
                "type": "MCQ",
                "question": question.capitalize(),
                "options": [opt.capitalize() for opt in options],
                "answer": answer.capitalize()
            }
        except Exception as e:
            print(f"⚠️ Rule-based MCQ generation failed: {e}")
            return None
    
    def generate_mcq(self, sentences: List[str], num_questions: int) -> List[Dict]:
        """Generate Multiple Choice Questions"""
        questions = []
        processed = set()  # Avoid duplicates
        
        for sentence in sentences:
            if len(questions) >= num_questions:
                break
            
            sentence = sentence.strip()
            if not sentence or len(sentence.split()) < 5:
                continue
            
            # Try model-based generation first
            question_text = self._generate_with_model(sentence)
            
            if question_text and question_text not in processed:
                # Extract answer from sentence for MCQ
                import nltk
                from nltk import pos_tag, word_tokenize
                try:
                    words = word_tokenize(sentence)
                    tagged = pos_tag(words)
                    nouns = [w for w, t in tagged if t.startswith('NN') and w.isalpha() and len(w) >= 4]
                    
                    if nouns:
                        answer = random.choice(nouns)
                        other_nouns = [w for w, t in tagged if t.startswith('NN') and 
                                      w.lower() != answer.lower() and w.isalpha() and len(w) >= 4]
                        
                        if len(other_nouns) >= 3:
                            distractors = random.sample(other_nouns, 3)
                            options = [answer] + distractors
                            random.shuffle(options)
                            
                            questions.append({
                                "type": "MCQ",
                                "question": question_text,
                                "options": [opt.capitalize() for opt in options],
                                "answer": answer.capitalize()
                            })
                            processed.add(question_text)
                except:
                    pass
            
            # Fallback to rule-based
            if len(questions) < num_questions:
                mcq = self._generate_rule_based_mcq(sentence)
                if mcq and mcq['question'] not in processed:
                    questions.append(mcq)
                    processed.add(mcq['question'])
        
        print(f"🟩 Generated {len(questions)} MCQs")
        return questions[:num_questions]
    
    def generate_fill_blank(self, sentences: List[str], num_questions: int) -> List[Dict]:
        """Generate Fill-in-the-Blank questions"""
        questions = []
        processed = set()
        
        for sentence in sentences:
            if len(questions) >= num_questions:
                break
            
            sentence = sentence.strip()
            if not sentence or len(sentence.split()) < 5:
                continue
            
            import nltk
            from nltk import pos_tag, word_tokenize
            
            try:
                words = word_tokenize(sentence)
                tagged = pos_tag(words)
                nouns = [w for w, t in tagged if t.startswith('NN') and w.isalpha() and len(w) >= 4]
                
                if not nouns:
                    continue
                
                answer = random.choice(nouns)
                pattern = r"\b" + re.escape(answer) + r"\b"
                question = re.sub(pattern, "_____", sentence, count=1, flags=re.IGNORECASE)
                
                if question != sentence and question not in processed:
                    questions.append({
                        "type": "Fill-in-the-Blank",
                        "question": question.capitalize(),
                        "answer": answer
                    })
                    processed.add(question)
            except Exception as e:
                continue
        
        print(f"🟨 Generated {len(questions)} Fill-in-the-Blanks")
        return questions[:num_questions]
    
    def generate_true_false(self, sentences: List[str], num_questions: int) -> List[Dict]:
        """Generate True/False questions"""
        # If optimized generator is present, use it for better performance
        if qgen_opt and hasattr(qgen_opt, 'generate_true_false'):
            try:
                raw_qs = qgen_opt.generate_true_false(sentences)
                # raw_qs contains TF questions; ensure correct slicing and format
                # The optimized function adds 'True or False: ' prefix already
                questions = []
                for q in raw_qs[:num_questions]:
                    if q.get('type') == 'True/False':
                        questions.append(q)
                print(f"🟦 Generated {len(questions)} True/False (optimized)")
                return questions[:num_questions]
            except Exception as e:
                print(f"⚠️ Optimized TF generator failed: {e}")
                # fall back to slower version below

        # Fallback to the internal slower method
        questions = []
        processed = set()
        valid_sentences = [s.strip() for s in sentences if len(s.strip().split()) > 6]
        false_count = num_questions // 2

        for i, sentence in enumerate(valid_sentences):
            if len(questions) >= num_questions:
                break
            if sentence in processed:
                continue

            make_false = i < false_count
            question_text = sentence

            if make_false:
                # Create false statement
                import nltk
                from nltk import pos_tag, word_tokenize
                try:
                    words = word_tokenize(sentence)
                    tagged = pos_tag(words)

                    # Try negating a verb
                    verbs = [(i, w) for i, (w, t) in enumerate(tagged) if t.startswith('VB')]
                    if verbs:
                        verb_idx, verb = verbs[0]
                        negation = random.choice(["not", "never"])
                        new_words = words[:verb_idx+1] + [negation] + words[verb_idx+1:]
                        question_text = " ".join(new_words)
                    else:
                        # Replace key noun
                        nouns = [w for w, t in tagged if t.startswith('NN') and len(w) > 3]
                        if nouns:
                            to_replace = random.choice(nouns)
                            replacement = random.choice(["X", "Y", "alternative"])
                            question_text = re.sub(rf"\b{re.escape(to_replace)}\b", replacement, sentence, count=1, flags=re.IGNORECASE)
                except Exception:
                    pass

            if question_text not in processed:
                questions.append({
                    "type": "True/False",
                    "question": f"True or False: {question_text.capitalize()}",
                    "answer": "False" if make_false else "True"
                })
                processed.add(question_text)

        print(f"🟦 Generated {len(questions)} True/False (fallback)")
        return questions[:num_questions]
    
    def generate_short_answer(self, sentences: List[str], num_questions: int) -> List[Dict]:
        """Generate Short Answer questions - Optimized version"""
        import nltk
        from nltk import pos_tag, word_tokenize
        
        questions = []
        processed = set()
        
        # Pre-filter valid sentences to avoid processing invalid ones
        valid_sentences = []
        for s in sentences:
            s = s.strip()
            if s and 6 <= len(s.split()) <= 30:  # Reasonable length range
                valid_sentences.append(s)
        
        # Limit processing to avoid slow model calls
        max_attempts = min(len(valid_sentences), num_questions * 3)
        use_model = self.qg_pipeline is not None
        
        for sentence in valid_sentences[:max_attempts]:
            if len(questions) >= num_questions:
                break
            
            # Fast fallback: Generate question without model if model is slow/unavailable
            question_text = None
            if use_model:
                try:
                    question_text = self._generate_with_model(sentence)
                except:
                    use_model = False  # Disable model if it fails
            
            # Fast fallback: Create question from sentence structure
            if not question_text:
                try:
                    words = word_tokenize(sentence)
                    tagged = pos_tag(words)
                    nouns = [w for w, t in tagged if t.startswith('NN') and w.isalpha() and len(w) >= 4]
                    
                    if nouns:
                        answer = random.choice(nouns)
                        # Create simple question format
                        question_templates = [
                            f"What is {answer}?",
                            f"Explain {answer}.",
                            f"Describe {answer}.",
                            f"What does {answer} refer to?"
                        ]
                        question_text = random.choice(question_templates)
                except:
                    continue
            
            if question_text and question_text not in processed:
                # Extract key term as answer
                try:
                    words = word_tokenize(sentence)
                    tagged = pos_tag(words)
                    nouns = [w for w, t in tagged if t.startswith('NN') and w.isalpha() and len(w) >= 4]
                    
                    if nouns:
                        answer = random.choice(nouns)
                        questions.append({
                            "type": "Short Answer",
                            "question": question_text,
                            "answer": f"{answer.capitalize()} - {sentence[:100]}..."
                        })
                        processed.add(question_text)
                except:
                    continue
        
        print(f"🟪 Generated {len(questions)} Short Answer")
        return questions[:num_questions]
    
    def generate_questions(self, text: str, question_types: List[str], num_questions: int) -> List[Dict]:
        """
        Main method to generate questions from text.
        
        Args:
            text: Input text to generate questions from
            question_types: List of question types (e.g., ["mcq", "fill_blanks"])
            num_questions: Total number of questions to generate
            
        Returns:
            List of question dictionaries
        """
        # Split text into sentences
        import nltk
        from nltk.tokenize import sent_tokenize
        
        try:
            # Download required NLTK data (only if not already present)
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                print("📥 Downloading NLTK punkt tokenizer...")
                nltk.download('punkt', quiet=True)
            
            try:
                nltk.data.find('taggers/averaged_perceptron_tagger')
            except LookupError:
                print("📥 Downloading NLTK POS tagger...")
                nltk.download('averaged_perceptron_tagger', quiet=True)
        except Exception as e:
            print(f"⚠️ NLTK setup warning: {e}")
            # Continue with basic sentence splitting
            pass
        
        sentences = sent_tokenize(text)
        sentences = [s.strip() for s in sentences if len(s.strip().split()) > 4]
        
        if not sentences:
            raise ValueError("No valid sentences found in text")
        
        # Calculate questions per type
        num_types = len(question_types)
        questions_per_type = max(1, num_questions // num_types)
        
        all_questions = []
        
        # Generate questions by type
        if "mcq" in question_types:
            all_questions.extend(self.generate_mcq(sentences, questions_per_type))
        
        if "fill_blanks" in question_types:
            all_questions.extend(self.generate_fill_blank(sentences, questions_per_type))
        
        if "true_false" in question_types:
            all_questions.extend(self.generate_true_false(sentences, questions_per_type))
        
        if "short_answer" in question_types:
            all_questions.extend(self.generate_short_answer(sentences, questions_per_type))
        
        # Randomize and limit to requested number
        random.shuffle(all_questions)
        return all_questions[:num_questions]


if __name__ == "__main__":
    # Test the generator
    sample_text = """
    Machine learning is a subset of artificial intelligence that focuses on the development of algorithms 
    that can learn from and make predictions or decisions based on data. Neural networks are computational 
    models inspired by the structure and function of biological neural networks. Deep learning uses 
    multiple layers of neural networks to analyze various factors of data.
    """
    
    generator = QuestionGenerator(difficulty="medium")
    questions = generator.generate_questions(
        sample_text,
        question_types=["mcq", "fill_blanks", "true_false"],
        num_questions=10
    )
    
    print(f"\n✅ Generated {len(questions)} questions:")
    for i, q in enumerate(questions, 1):
        print(f"\n{i}. {q['type']}: {q['question']}")
        if q['type'] == 'MCQ':
            print(f"   Options: {q['options']}")
        print(f"   Answer: {q['answer']}")

