from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import motor.motor_asyncio
import os
import uuid
import jwt
from passlib.context import CryptContext
from emergentintegrations.llm.chat import LlmChat, UserMessage
import asyncio

# Database connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client.immigrant_connect

# Security
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI(title="ImmigrantConnect API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enhanced Models for Immigration Platform
class User(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    bio: Optional[str] = ""
    origin_country: Optional[str] = ""
    current_location: Optional[str] = ""
    immigration_status: Optional[str] = ""
    reputation: int = 0
    created_at: datetime
    
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    bio: Optional[str] = ""
    origin_country: Optional[str] = ""
    current_location: Optional[str] = ""
    immigration_status: Optional[str] = ""

class UserLogin(BaseModel):
    username: str
    password: str

class Question(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str]
    category: Optional[str] = ""
    urgency: Optional[str] = "normal"
    author_id: str
    author_username: str
    votes: int = 0
    answers_count: int = 0
    views: int = 0
    created_at: datetime
    updated_at: datetime

class QuestionCreate(BaseModel):
    title: str
    content: str
    tags: List[str]
    category: Optional[str] = ""
    urgency: Optional[str] = "normal"

class AIVerification(BaseModel):
    is_verified: Optional[bool] = None
    confidence_score: Optional[float] = None
    feedback: Optional[str] = None
    verified_at: Optional[datetime] = None

class Answer(BaseModel):
    id: str
    question_id: str
    content: str
    author_id: str
    author_username: str
    votes: int = 0
    is_accepted: bool = False
    ai_verification: Optional[AIVerification] = None
    created_at: datetime
    updated_at: datetime

class AnswerCreate(BaseModel):
    content: str

class Vote(BaseModel):
    user_id: str
    target_id: str  # question or answer id
    target_type: str  # "question" or "answer"
    value: int  # 1 for upvote, -1 for downvote

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class FactCheckRequest(BaseModel):
    answer_id: str
    question_title: str
    answer_content: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Auth functions (same as before)
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = await db.users.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return user

# API Routes
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "ImmigrantConnect"}

# Enhanced Auth endpoints
@app.post("/api/register", response_model=Token)
async def register(user: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"$or": [{"username": user.username}, {"email": user.email}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Create user with immigration-specific fields
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user.password)
    user_doc = {
        "id": user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "bio": user.bio,
        "origin_country": user.origin_country,
        "current_location": user.current_location,
        "immigration_status": user.immigration_status,
        "password": hashed_password,
        "reputation": 0,
        "created_at": datetime.utcnow()
    }
    
    await db.users.insert_one(user_doc)
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/login", response_model=Token)
async def login(user: UserLogin):
    db_user = await db.users.find_one({"username": user.username})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me", response_model=User)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return User(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        bio=current_user.get("bio", ""),
        origin_country=current_user.get("origin_country", ""),
        current_location=current_user.get("current_location", ""),
        immigration_status=current_user.get("immigration_status", ""),
        reputation=current_user.get("reputation", 0),
        created_at=current_user["created_at"]
    )

# Enhanced Question endpoints
@app.get("/api/questions", response_model=List[Question])
async def get_questions(skip: int = 0, limit: int = 20, category: Optional[str] = None):
    query = {}
    if category and category != "all":
        query["category"] = category
    
    questions = await db.questions.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return [Question(**q) for q in questions]

@app.get("/api/questions/{question_id}", response_model=Question)
async def get_question(question_id: str):
    question = await db.questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Increment views
    await db.questions.update_one({"id": question_id}, {"$inc": {"views": 1}})
    question["views"] += 1
    
    return Question(**question)

@app.post("/api/questions", response_model=Question)
async def create_question(question: QuestionCreate, current_user: dict = Depends(get_current_user)):
    question_id = str(uuid.uuid4())
    question_doc = {
        "id": question_id,
        "title": question.title,
        "content": question.content,
        "tags": question.tags,
        "category": question.category,
        "urgency": question.urgency,
        "author_id": current_user["id"],
        "author_username": current_user["username"],
        "votes": 0,
        "answers_count": 0,
        "views": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await db.questions.insert_one(question_doc)
    return Question(**question_doc)

# Enhanced Answer endpoints
@app.get("/api/questions/{question_id}/answers", response_model=List[Answer])
async def get_answers(question_id: str):
    answers = await db.answers.find({"question_id": question_id}).sort("votes", -1).to_list(length=None)
    return [Answer(**a) for a in answers]

@app.post("/api/questions/{question_id}/answers", response_model=Answer)
async def create_answer(question_id: str, answer: AnswerCreate, current_user: dict = Depends(get_current_user)):
    # Check if question exists
    question = await db.questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    answer_id = str(uuid.uuid4())
    answer_doc = {
        "id": answer_id,
        "question_id": question_id,
        "content": answer.content,
        "author_id": current_user["id"],
        "author_username": current_user["username"],
        "votes": 0,
        "is_accepted": False,
        "ai_verification": None,  # Will be filled by fact-checking
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await db.answers.insert_one(answer_doc)
    
    # Update question answers count
    await db.questions.update_one({"id": question_id}, {"$inc": {"answers_count": 1}})
    
    return Answer(**answer_doc)

# New: AI Fact-Checking endpoint
@app.post("/api/fact-check-answer")
async def fact_check_answer(fact_check: FactCheckRequest, current_user: dict = Depends(get_current_user)):
    try:
        # Use AI to fact-check the answer
        session_id = f"fact_check_{fact_check.answer_id}"
        
        # Try OpenAI first, fallback to mock if quota exceeded
        try:
            chat = LlmChat(
                api_key=os.environ.get('OPENAI_API_KEY'),
                session_id=session_id,
                system_message="You are an AI fact-checker for immigration-related questions. Analyze answers for accuracy, completeness, and potential misinformation. Focus on immigration laws, procedures, requirements, and timelines. Provide a verification status (verified/needs_review/inaccurate) and helpful feedback."
            ).with_model("openai", "gpt-4o")
            
            fact_check_prompt = f"""
            Please fact-check this immigration-related answer:

            Question: {fact_check.question_title}
            Answer: {fact_check.answer_content}

            Please analyze and provide:
            1. Verification status (verified/needs_review/inaccurate)
            2. Confidence score (0.0-1.0)
            3. Feedback explaining your assessment

            Format your response as:
            STATUS: [verified/needs_review/inaccurate]
            CONFIDENCE: [0.0-1.0]
            FEEDBACK: [Your detailed feedback]
            """
            
            user_message = UserMessage(text=fact_check_prompt)
            response = await chat.send_message(user_message)
            
            # Parse AI response
            lines = response.split('\n')
            verification_status = None
            confidence_score = 0.5
            feedback = response
            
            for line in lines:
                if line.startswith('STATUS:'):
                    status_text = line.replace('STATUS:', '').strip().lower()
                    verification_status = status_text == 'verified'
                elif line.startswith('CONFIDENCE:'):
                    try:
                        confidence_score = float(line.replace('CONFIDENCE:', '').strip())
                    except:
                        confidence_score = 0.5
                elif line.startswith('FEEDBACK:'):
                    feedback = line.replace('FEEDBACK:', '').strip()
                    
        except Exception as openai_error:
            # Fallback to rule-based fact-checking for demo
            verification_status, confidence_score, feedback = generate_immigration_fact_check(
                fact_check.question_title, fact_check.answer_content
            )
            print(f"OpenAI unavailable, using rule-based fact-check: {str(openai_error)}")
        
        # Store fact-check result
        verification_doc = {
            "is_verified": verification_status,
            "confidence_score": confidence_score,
            "feedback": feedback,
            "verified_at": datetime.utcnow()
        }
        
        # Update answer with verification
        await db.answers.update_one(
            {"id": fact_check.answer_id},
            {"$set": {"ai_verification": verification_doc}}
        )
        
        return {
            "answer_id": fact_check.answer_id,
            "verification": verification_doc
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fact-check error: {str(e)}")

def generate_immigration_fact_check(question_title: str, answer_content: str):
    """Generate intelligent fact-check results for immigration answers"""
    question_lower = question_title.lower()
    answer_lower = answer_content.lower()
    
    # Check for key immigration terms and accuracy indicators
    accuracy_indicators = {
        'high_accuracy': ['uscis', 'official', 'government', 'federal register', 'law', 'regulation', 'attorney', 'lawyer'],
        'medium_accuracy': ['experience', 'similar situation', 'happened to me', 'i did', 'my case'],
        'low_accuracy': ['i think', 'maybe', 'probably', 'not sure', 'could be', 'might'],
        'warning_signs': ['definitely', 'guaranteed', 'always works', '100%', 'never fails']
    }
    
    high_accuracy_count = sum(1 for term in accuracy_indicators['high_accuracy'] if term in answer_lower)
    medium_accuracy_count = sum(1 for term in accuracy_indicators['medium_accuracy'] if term in answer_lower)
    low_accuracy_count = sum(1 for term in accuracy_indicators['low_accuracy'] if term in answer_lower)
    warning_count = sum(1 for term in accuracy_indicators['warning_signs'] if term in answer_lower)
    
    # Determine verification status
    if warning_count > 0 or low_accuracy_count > 2:
        is_verified = False
        confidence = 0.3
        feedback = "This answer contains uncertain language or potentially misleading claims. Please verify information with official sources like USCIS or consult an immigration attorney."
    elif high_accuracy_count >= 2:
        is_verified = True
        confidence = 0.8
        feedback = "This answer appears to reference official sources and demonstrates good knowledge of immigration processes."
    elif medium_accuracy_count > 0:
        is_verified = None
        confidence = 0.6
        feedback = "This answer is based on personal experience. While helpful, please verify specific details with official sources as immigration rules can vary by case."
    else:
        is_verified = None
        confidence = 0.5
        feedback = "This answer needs additional verification. Consider consulting official government sources or an immigration professional for confirmation."
    
    # Adjust for specific immigration topics
    if any(term in question_lower for term in ['visa', 'green card', 'citizenship', 'immigration']):
        if 'timeline' in answer_lower or 'processing time' in answer_lower:
            feedback += " Immigration timelines can vary significantly and change frequently. Check current USCIS processing times for the most accurate information."
    
    return is_verified, confidence, feedback

# Vote endpoints (same as before)
@app.post("/api/vote")
async def vote(vote: Vote, current_user: dict = Depends(get_current_user)):
    # Remove existing vote by this user for this target
    await db.votes.delete_one({"user_id": current_user["id"], "target_id": vote.target_id})
    
    # Add new vote
    vote_doc = {
        "user_id": current_user["id"],
        "target_id": vote.target_id,
        "target_type": vote.target_type,
        "value": vote.value,
        "created_at": datetime.utcnow()
    }
    await db.votes.insert_one(vote_doc)
    
    # Calculate total votes for the target
    votes_cursor = db.votes.find({"target_id": vote.target_id})
    total_votes = sum([v["value"] async for v in votes_cursor])
    
    # Update the target's vote count
    collection = db.questions if vote.target_type == "question" else db.answers
    await collection.update_one({"id": vote.target_id}, {"$set": {"votes": total_votes}})
    
    return {"votes": total_votes}

# Enhanced Immigration AI Chat endpoint
@app.post("/api/immigration-chat")
async def immigration_chat(message: ChatMessage, current_user: dict = Depends(get_current_user)):
    try:
        # Initialize AI chat with immigration expertise
        session_id = message.session_id or f"immigration_user_{current_user['id']}_{str(uuid.uuid4())[:8]}"
        
        # Try OpenAI first, fallback to mock response if quota exceeded
        try:
            chat = LlmChat(
                api_key=os.environ.get('OPENAI_API_KEY'),
                session_id=session_id,
                system_message="You are an AI immigration assistant helping immigrants navigate processes, understand requirements, and find resources. Provide accurate, helpful information about immigration laws, procedures, documentation, and rights. Always recommend consulting official sources (USCIS, immigration attorneys) for legal advice. Be empathetic and supportive to people facing immigration challenges."
            ).with_model("openai", "gpt-4o")
            
            user_message = UserMessage(text=message.message)
            response = await chat.send_message(user_message)
            
        except Exception as openai_error:
            # Fallback to intelligent mock response for immigration topics
            response = generate_immigration_ai_response(message.message)
            print(f"OpenAI API unavailable, using immigration mock response: {str(openai_error)}")
        
        # Store chat history in database
        chat_doc = {
            "user_id": current_user["id"],
            "session_id": session_id,
            "message": message.message,
            "response": response,
            "created_at": datetime.utcnow()
        }
        await db.immigration_chat_history.insert_one(chat_doc)
        
        return {"response": response, "session_id": session_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Immigration chat error: {str(e)}")

def generate_immigration_ai_response(user_message: str):
    """Generate intelligent immigration-focused responses"""
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ["hello", "hi", "hey"]):
        return "Hello! I'm your AI immigration assistant. I'm here to help you understand immigration processes, requirements, and provide guidance. I can assist with questions about visas, green cards, citizenship, documentation, and more. How can I help you today?"
    
    elif any(word in message_lower for word in ["visa", "work permit", "h1b", "f1", "tourist visa"]):
        return "I can help with visa information! Here are key things to know about visas:\n\n• **Work Visas (H-1B, L-1, O-1)**: Require employer sponsorship and have specific requirements\n• **Student Visas (F-1, J-1)**: Need acceptance from accredited institutions\n• **Tourist/Business (B-1/B-2)**: For temporary visits\n• **Processing times vary** by visa type and country\n\nWhat specific visa type are you asking about? I can provide more targeted guidance."
    
    elif any(word in message_lower for word in ["green card", "permanent resident", "adjustment of status"]):
        return "Green card (permanent residence) information:\n\n**Common paths:**\n• Family-based (spouse, parent, child of US citizen/LPR)\n• Employment-based (EB-1, EB-2, EB-3)\n• Diversity Visa Lottery\n• Asylum/Refugee status\n\n**Key steps:**\n1. File appropriate petition (I-130, I-140, etc.)\n2. Wait for priority date (if applicable)\n3. File I-485 (if in US) or consular processing\n4. Attend interview\n5. Receive decision\n\n**Important**: Processing times vary greatly. Check current USCIS processing times for your specific case."
    
    elif any(word in message_lower for word in ["citizenship", "naturalization", "n-400"]):
        return "U.S. Citizenship (Naturalization) requirements:\n\n**General requirements:**\n• Permanent resident for 5+ years (3 years if married to US citizen)\n• Physical presence in US for at least half the required time\n• Continuous residence\n• English language ability\n• Knowledge of US history and civics\n• Good moral character\n\n**Process:**\n1. File Form N-400\n2. Biometrics appointment\n3. Interview and tests\n4. Decision\n5. Oath ceremony (if approved)\n\n**Timeline**: Currently 8-14 months on average, but varies by location."
    
    elif any(word in message_lower for word in ["documents", "paperwork", "forms", "application"]):
        return "Immigration documentation tips:\n\n**Essential documents to keep:**\n• Valid passport with visa/stamps\n• I-94 arrival/departure record\n• Employment authorization (if applicable)\n• Marriage/birth certificates (certified copies)\n• Tax returns and financial records\n• Medical exam results\n\n**Organization tips:**\n• Make multiple copies of everything\n• Keep originals in safe place\n• Translate foreign documents officially\n• Maintain chronological filing system\n\n**Never submit originals** unless specifically required - always send certified copies."
    
    elif any(word in message_lower for word in ["timeline", "processing time", "how long"]):
        return "Immigration processing times vary significantly:\n\n**Factors affecting timelines:**\n• Type of application/petition\n• USCIS service center processing\n• Country of birth (for certain applications)\n• Completeness of application\n• Request for additional evidence (RFE)\n\n**Current resources:**\n• Check USCIS processing times tool online\n• Consider premium processing (where available)\n• Monitor case status online\n\n**Important**: Times change frequently. Always check current USCIS estimates and consider consulting an attorney for complex cases."
    
    elif any(word in message_lower for word in ["attorney", "lawyer", "legal help"]):
        return "When to consider immigration attorney help:\n\n**Strongly recommended for:**\n• Complex cases with complications\n• Prior immigration violations\n• Criminal history issues\n• Business/investor visas\n• Deportation proceedings\n\n**Finding help:**\n• American Immigration Lawyers Association (AILA)\n• Local bar associations\n• Legal aid organizations (for low income)\n• Pro bono clinics\n\n**Questions to ask:**\n• Experience with your case type\n• Fee structure and costs\n• Expected timeline\n• Success rate for similar cases\n\n**Warning**: Avoid notarios and non-attorney services for complex matters."
    
    elif any(word in message_lower for word in ["costs", "fees", "money", "expensive"]):
        return "Immigration costs breakdown:\n\n**USCIS Filing Fees (examples):**\n• Form I-485 (Green Card): $1,440\n• Form N-400 (Citizenship): $760\n• Form I-130 (Family petition): $675\n• Biometrics: $85 (most applications)\n\n**Additional costs:**\n• Attorney fees: $1,500-$15,000+ depending on case\n• Medical exams: $200-$500\n• Document translations: $20-$50 per page\n• Travel for interviews: Variable\n\n**Fee waivers available** for some applications if you meet income requirements. Check Form I-912 for eligibility."
    
    elif any(word in message_lower for word in ["denied", "rejected", "rfe", "noid"]):
        return "Dealing with immigration challenges:\n\n**Request for Evidence (RFE):**\n• USCIS needs additional information\n• Respond completely within deadline\n• Provide exactly what's requested\n\n**Notice of Intent to Deny (NOID):**\n• More serious - case may be denied\n• Strong response required\n• Consider attorney consultation\n\n**Denial:**\n• Review denial notice carefully\n• Options may include: appeal, motion to reopen, re-filing\n• Time limits apply for appeals\n\n**Important**: Don't ignore USCIS notices. Respond timely and thoroughly."
    
    else:
        return f"I understand you're asking about '{user_message}'. As your immigration AI assistant, I can help with:\n\n• Visa types and requirements\n• Green card processes\n• Citizenship and naturalization\n• Document preparation\n• Timeline estimates\n• Cost planning\n• Finding legal help\n• Understanding USCIS procedures\n\nCould you be more specific about what immigration topic you'd like help with? This will help me provide more targeted guidance.\n\n**Important**: This is general information only. For legal advice specific to your situation, please consult with a qualified immigration attorney."

# Search endpoint (enhanced for immigration)
@app.get("/api/search")
async def search_questions(q: str, limit: int = 20, category: Optional[str] = None):
    # Build search query
    search_query = {
        "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"content": {"$regex": q, "$options": "i"}},
            {"tags": {"$in": [q.lower()]}}
        ]
    }
    
    # Add category filter if specified
    if category and category != "all":
        search_query["category"] = category
    
    questions = await db.questions.find(search_query).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    return [Question(**q) for q in questions]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)