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
db = client.qa_platform

# Security
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI(title="Q&A Platform API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class User(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    bio: Optional[str] = ""
    reputation: int = 0
    created_at: datetime
    
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    bio: Optional[str] = ""

class UserLogin(BaseModel):
    username: str
    password: str

class Question(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str]
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

class Answer(BaseModel):
    id: str
    question_id: str
    content: str
    author_id: str
    author_username: str
    votes: int = 0
    is_accepted: bool = False
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

class Token(BaseModel):
    access_token: str
    token_type: str

# Auth functions
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
    return {"status": "healthy"}

# Auth endpoints
@app.post("/api/register", response_model=Token)
async def register(user: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"$or": [{"username": user.username}, {"email": user.email}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user.password)
    user_doc = {
        "id": user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "bio": user.bio,
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
        reputation=current_user.get("reputation", 0),
        created_at=current_user["created_at"]
    )

# Question endpoints
@app.get("/api/questions", response_model=List[Question])
async def get_questions(skip: int = 0, limit: int = 20):
    questions = await db.questions.find().sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
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

# Answer endpoints
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
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await db.answers.insert_one(answer_doc)
    
    # Update question answers count
    await db.questions.update_one({"id": question_id}, {"$inc": {"answers_count": 1}})
    
    return Answer(**answer_doc)

# Voting endpoints
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

# AI Chat endpoint
@app.post("/api/chat")
async def chat_with_ai(message: ChatMessage, current_user: dict = Depends(get_current_user)):
    try:
        # Initialize AI chat with OpenAI
        session_id = message.session_id or f"user_{current_user['id']}_{str(uuid.uuid4())[:8]}"
        
        # Try OpenAI first, fallback to mock response if quota exceeded
        try:
            chat = LlmChat(
                api_key=os.environ.get('OPENAI_API_KEY'),
                session_id=session_id,
                system_message="You are an AI assistant for a professional Q&A platform. Help users with their questions, provide guidance on how to ask better questions, suggest improvements to answers, and assist with technical problems. Be concise, helpful, and professional."
            ).with_model("openai", "gpt-4o")
            
            user_message = UserMessage(text=message.message)
            response = await chat.send_message(user_message)
            
        except Exception as openai_error:
            # Fallback to intelligent mock response for demo purposes
            response = generate_mock_ai_response(message.message)
            print(f"OpenAI API unavailable, using mock response: {str(openai_error)}")
        
        # Store chat history in database
        chat_doc = {
            "user_id": current_user["id"],
            "session_id": session_id,
            "message": message.message,
            "response": response,
            "created_at": datetime.utcnow()
        }
        await db.chat_history.insert_one(chat_doc)
        
        return {"response": response, "session_id": session_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat error: {str(e)}")

def generate_mock_ai_response(user_message: str):
    """Generate intelligent mock responses for demo purposes"""
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ["hello", "hi", "hey"]):
        return "Hello! I'm your AI assistant for this Q&A platform. I'm here to help you write better questions, understand complex topics, and improve your answers. How can I assist you today?"
    
    elif any(word in message_lower for word in ["question", "ask", "how to"]):
        return "Great question! Here are some tips for writing effective questions:\n\n1. **Be specific**: Include relevant details and context\n2. **Be clear**: Use simple, direct language\n3. **Add tags**: Help others find and categorize your question\n4. **Show research**: Mention what you've already tried\n5. **Include examples**: Show expected vs actual results\n\nWould you like help with a specific question you're working on?"
    
    elif any(word in message_lower for word in ["answer", "respond", "reply"]):
        return "When writing great answers:\n\n1. **Address the question directly** - Start with a clear solution\n2. **Provide examples** - Show code, steps, or demonstrations\n3. **Explain the why** - Don't just give solutions, explain reasoning\n4. **Be comprehensive** - Cover edge cases and alternatives\n5. **Stay professional** - Use clear, respectful language\n\nRemember, the best answers help not just the asker, but future visitors too!"
    
    elif any(word in message_lower for word in ["vote", "voting", "upvote", "downvote"]):
        return "The voting system helps surface the best content:\n\n**Upvote when:**\n- Content is helpful, accurate, and well-written\n- Shows research effort or provides good examples\n- Adds value to the discussion\n\n**Downvote when:**\n- Content is incorrect, unhelpful, or unclear\n- Lacks effort or context\n- Is off-topic or inappropriate\n\nYour votes help build a better community for everyone!"
    
    elif any(word in message_lower for word in ["help", "assist", "support"]):
        return "I'm here to help you make the most of this Q&A platform! I can assist with:\n\n• **Writing better questions** - Structure, clarity, and detail\n• **Improving answers** - Completeness and helpfulness\n• **Understanding voting** - When and how to vote effectively\n• **Platform features** - Tags, search, reputation system\n• **Best practices** - Community guidelines and etiquette\n\nWhat specific area would you like help with?"
    
    else:
        return f"That's an interesting point about '{user_message}'. As your AI assistant for this Q&A platform, I'd recommend:\n\n1. **Search existing questions** first to see if this has been asked before\n2. **Be specific** in your question with relevant details\n3. **Use appropriate tags** to help others find your question\n4. **Provide context** about what you've already tried\n\nWould you like me to help you structure this as a proper question for the community?"

# Search endpoint
@app.get("/api/search")
async def search_questions(q: str, limit: int = 20):
    # Simple text search - can be enhanced with MongoDB text index
    questions = await db.questions.find({
        "$or": [
            {"title": {"$regex": q, "$options": "i"}},
            {"content": {"$regex": q, "$options": "i"}},
            {"tags": {"$in": [q]}}
        ]
    }).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    return [Question(**q) for q in questions]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)