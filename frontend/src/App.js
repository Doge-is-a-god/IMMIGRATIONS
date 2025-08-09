import React, { useState, useEffect } from 'react';
import { Search, MessageCircle, Plus, ThumbsUp, ThumbsDown, User, Bot, X, Send, Eye, Clock, Tag, CheckCircle, AlertTriangle, Globe, Users } from 'lucide-react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Textarea } from './components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Avatar, AvatarFallback } from './components/ui/avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Separator } from './components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Immigration categories for better organization
const IMMIGRATION_CATEGORIES = [
  'visa-immigration', 'legal-rights', 'employment', 'healthcare', 'housing', 
  'education', 'taxes-finance', 'cultural-adaptation', 'family-immigration', 
  'citizenship', 'documents', 'social-services', 'language-learning', 'emergency-help'
];

function App() {
  const [questions, setQuestions] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [authMode, setAuthMode] = useState('login');
  const [loading, setLoading] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  // Auth forms
  const [loginData, setLoginData] = useState({ username: '', password: '' });
  const [registerData, setRegisterData] = useState({ 
    username: '', email: '', password: '', full_name: '', bio: '', 
    origin_country: '', current_location: '', immigration_status: ''
  });
  
  // Question form
  const [questionData, setQuestionData] = useState({ title: '', content: '', tags: '', category: '', urgency: 'normal' });
  const [answerContent, setAnswerContent] = useState('');

  useEffect(() => {
    if (token) {
      fetchUser();
      fetchQuestions();
    } else {
      fetchQuestions();
    }
  }, [token]);

  const apiRequest = async (url, options = {}) => {
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(`${API_BASE_URL}${url}`, config);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Network error' }));
      throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
  };

  const fetchUser = async () => {
    try {
      const userData = await apiRequest('/api/me');
      setUser(userData);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      localStorage.removeItem('token');
      setToken(null);
    }
  };

  const fetchQuestions = async () => {
    try {
      const questionsData = await apiRequest('/api/questions');
      setQuestions(questionsData);
    } catch (error) {
      console.error('Failed to fetch questions:', error);
    }
  };

  const fetchQuestion = async (questionId) => {
    try {
      const [questionData, answersData] = await Promise.all([
        apiRequest(`/api/questions/${questionId}`),
        apiRequest(`/api/questions/${questionId}/answers`)
      ]);
      setCurrentQuestion(questionData);
      setAnswers(answersData);
    } catch (error) {
      console.error('Failed to fetch question details:', error);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const endpoint = authMode === 'login' ? '/api/login' : '/api/register';
      const data = authMode === 'login' ? loginData : registerData;
      
      const response = await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(data),
      });
      
      setToken(response.access_token);
      localStorage.setItem('token', response.access_token);
      setLoginData({ username: '', password: '' });
      setRegisterData({ 
        username: '', email: '', password: '', full_name: '', bio: '',
        origin_country: '', current_location: '', immigration_status: ''
      });
    } catch (error) {
      alert(error.message);
    }
    setLoading(false);
  };

  const handleCreateQuestion = async (e) => {
    e.preventDefault();
    if (!token) return;
    
    setLoading(true);
    try {
      const tags = questionData.tags.split(',').map(tag => tag.trim()).filter(tag => tag);
      await apiRequest('/api/questions', {
        method: 'POST',
        body: JSON.stringify({
          title: questionData.title,
          content: questionData.content,
          tags: [...tags, questionData.category],
          category: questionData.category,
          urgency: questionData.urgency
        }),
      });
      
      setQuestionData({ title: '', content: '', tags: '', category: '', urgency: 'normal' });
      fetchQuestions();
    } catch (error) {
      alert(error.message);
    }
    setLoading(false);
  };

  const handleCreateAnswer = async (e) => {
    e.preventDefault();
    if (!token || !currentQuestion) return;
    
    setLoading(true);
    try {
      const answer = await apiRequest(`/api/questions/${currentQuestion.id}/answers`, {
        method: 'POST',
        body: JSON.stringify({ content: answerContent }),
      });
      
      // Trigger AI fact-checking
      try {
        await apiRequest('/api/fact-check-answer', {
          method: 'POST',
          body: JSON.stringify({
            answer_id: answer.id,
            question_title: currentQuestion.title,
            answer_content: answerContent
          }),
        });
      } catch (factCheckError) {
        console.error('Fact-check failed:', factCheckError);
      }
      
      setAnswerContent('');
      fetchQuestion(currentQuestion.id);
    } catch (error) {
      alert(error.message);
    }
    setLoading(false);
  };

  const handleVote = async (targetId, targetType, value) => {
    if (!token) return;
    
    try {
      await apiRequest('/api/vote', {
        method: 'POST',
        body: JSON.stringify({
          user_id: user.id,
          target_id: targetId,
          target_type: targetType,
          value: value
        }),
      });
      
      if (currentQuestion) {
        fetchQuestion(currentQuestion.id);
      }
      fetchQuestions();
    } catch (error) {
      console.error('Vote failed:', error);
    }
  };

  const handleChatMessage = async () => {
    if (!chatInput.trim() || !token) return;
    
    const userMessage = { text: chatInput, sender: 'user' };
    setChatMessages(prev => [...prev, userMessage]);
    setChatInput('');
    
    try {
      const response = await apiRequest('/api/immigration-chat', {
        method: 'POST',
        body: JSON.stringify({ message: chatInput }),
      });
      
      const aiMessage = { text: response.response, sender: 'ai' };
      setChatMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Chat failed:', error);
      const errorMessage = { text: 'Sorry, I encountered an error. Please try again.', sender: 'ai' };
      setChatMessages(prev => [...prev, errorMessage]);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      fetchQuestions();
      return;
    }
    
    try {
      const results = await apiRequest(`/api/search?q=${encodeURIComponent(searchQuery)}`);
      setQuestions(results);
    } catch (error) {
      console.error('Search failed:', error);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    setCurrentQuestion(null);
    setAnswers([]);
  };

  const getUrgencyColor = (urgency) => {
    switch (urgency) {
      case 'urgent': return 'text-red-600 border-red-200 bg-red-50';
      case 'high': return 'text-orange-600 border-orange-200 bg-orange-50';
      default: return 'text-blue-600 border-blue-200 bg-blue-50';
    }
  };

  const getAnswerVerificationStatus = (answer) => {
    if (answer.ai_verification?.is_verified === true) {
      return { icon: CheckCircle, color: 'text-green-600', text: 'AI Verified' };
    } else if (answer.ai_verification?.is_verified === false) {
      return { icon: AlertTriangle, color: 'text-yellow-600', text: 'Needs Review' };
    }
    return null;
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-md mx-auto">
            <div className="text-center mb-8">
              <div className="flex items-center justify-center mb-4">
                <Globe className="h-12 w-12 text-indigo-600 mr-3" />
                <Users className="h-10 w-10 text-blue-600" />
              </div>
              <h1 className="text-4xl font-bold text-slate-800 mb-2">ImmigrantConnect</h1>
              <p className="text-slate-600">Trusted Q&A Community for Immigrants with AI Fact-Checking</p>
              <p className="text-sm text-slate-500 mt-2">Get reliable answers to your immigration questions from the community, verified by AI</p>
            </div>
            
            <Card>
              <CardHeader>
                <Tabs value={authMode} onValueChange={setAuthMode}>
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="login">Login</TabsTrigger>
                    <TabsTrigger value="register">Join Community</TabsTrigger>
                  </TabsList>
                </Tabs>
              </CardHeader>
              <CardContent>
                {authMode === 'login' ? (
                  <form onSubmit={handleAuth} className="space-y-4">
                    <Input
                      placeholder="Username"
                      value={loginData.username}
                      onChange={(e) => setLoginData({...loginData, username: e.target.value})}
                      required
                    />
                    <Input
                      type="password"
                      placeholder="Password"
                      value={loginData.password}
                      onChange={(e) => setLoginData({...loginData, password: e.target.value})}
                      required
                    />
                    <Button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700" disabled={loading}>
                      {loading ? 'Logging in...' : 'Login'}
                    </Button>
                  </form>
                ) : (
                  <form onSubmit={handleAuth} className="space-y-4">
                    <Input
                      placeholder="Username"
                      value={registerData.username}
                      onChange={(e) => setRegisterData({...registerData, username: e.target.value})}
                      required
                    />
                    <Input
                      type="email"
                      placeholder="Email"
                      value={registerData.email}
                      onChange={(e) => setRegisterData({...registerData, email: e.target.value})}
                      required
                    />
                    <Input
                      placeholder="Full Name"
                      value={registerData.full_name}
                      onChange={(e) => setRegisterData({...registerData, full_name: e.target.value})}
                      required
                    />
                    <Input
                      placeholder="Origin Country"
                      value={registerData.origin_country}
                      onChange={(e) => setRegisterData({...registerData, origin_country: e.target.value})}
                    />
                    <Input
                      placeholder="Current Location"
                      value={registerData.current_location}
                      onChange={(e) => setRegisterData({...registerData, current_location: e.target.value})}
                    />
                    <Input
                      placeholder="Immigration Status (optional)"
                      value={registerData.immigration_status}
                      onChange={(e) => setRegisterData({...registerData, immigration_status: e.target.value})}
                    />
                    <Textarea
                      placeholder="Brief bio - How long have you been in your new country? What's your background?"
                      value={registerData.bio}
                      onChange={(e) => setRegisterData({...registerData, bio: e.target.value})}
                      rows={3}
                    />
                    <Input
                      type="password"
                      placeholder="Password"
                      value={registerData.password}
                      onChange={(e) => setRegisterData({...registerData, password: e.target.value})}
                      required
                    />
                    <Button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700" disabled={loading}>
                      {loading ? 'Creating account...' : 'Join Community'}
                    </Button>
                  </form>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-slate-200">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2 cursor-pointer" onClick={() => {
                setCurrentQuestion(null);
                fetchQuestions();
              }}>
                <Globe className="h-8 w-8 text-indigo-600" />
                <h1 className="text-2xl font-bold text-slate-800">ImmigrantConnect</h1>
              </div>
              <div className="hidden md:flex items-center space-x-2">
                <Input
                  placeholder="Search immigration questions..."
                  className="w-64"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                />
                <Button variant="outline" size="sm" onClick={handleSearch}>
                  <Search className="h-4 w-4" />
                </Button>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <Dialog>
                <DialogTrigger asChild>
                  <Button className="bg-indigo-600 hover:bg-indigo-700">
                    <Plus className="h-4 w-4 mr-2" />
                    Ask Question
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl">
                  <DialogHeader>
                    <DialogTitle>Ask the Immigration Community</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleCreateQuestion} className="space-y-4">
                    <Input
                      placeholder="What's your immigration question?"
                      value={questionData.title}
                      onChange={(e) => setQuestionData({...questionData, title: e.target.value})}
                      required
                    />
                    <Textarea
                      placeholder="Provide detailed context about your situation, location, and any specific requirements..."
                      rows={6}
                      value={questionData.content}
                      onChange={(e) => setQuestionData({...questionData, content: e.target.value})}
                      required
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <Select 
                        value={questionData.category} 
                        onValueChange={(value) => setQuestionData({...questionData, category: value})}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select category" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="visa-immigration">Visa & Immigration</SelectItem>
                          <SelectItem value="legal-rights">Legal Rights</SelectItem>
                          <SelectItem value="employment">Employment</SelectItem>
                          <SelectItem value="healthcare">Healthcare</SelectItem>
                          <SelectItem value="housing">Housing</SelectItem>
                          <SelectItem value="education">Education</SelectItem>
                          <SelectItem value="taxes-finance">Taxes & Finance</SelectItem>
                          <SelectItem value="cultural-adaptation">Cultural Adaptation</SelectItem>
                          <SelectItem value="family-immigration">Family Immigration</SelectItem>
                          <SelectItem value="citizenship">Citizenship</SelectItem>
                          <SelectItem value="documents">Documents</SelectItem>
                          <SelectItem value="social-services">Social Services</SelectItem>
                          <SelectItem value="language-learning">Language Learning</SelectItem>
                          <SelectItem value="emergency-help">Emergency Help</SelectItem>
                        </SelectContent>
                      </Select>
                      <Select 
                        value={questionData.urgency} 
                        onValueChange={(value) => setQuestionData({...questionData, urgency: value})}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Urgency level" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="normal">Normal</SelectItem>
                          <SelectItem value="high">High Priority</SelectItem>
                          <SelectItem value="urgent">Urgent</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <Input
                      placeholder="Additional tags (comma-separated, e.g. H1B, green-card, work-permit)"
                      value={questionData.tags}
                      onChange={(e) => setQuestionData({...questionData, tags: e.target.value})}
                    />
                    <div className="flex justify-end space-x-2">
                      <Button type="submit" disabled={loading || !questionData.category}>
                        {loading ? 'Posting...' : 'Post Question'}
                      </Button>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
              
              <div className="flex items-center space-x-2">
                <Avatar>
                  <AvatarFallback>
                    {user?.full_name?.charAt(0) || 'U'}
                  </AvatarFallback>
                </Avatar>
                <div className="hidden md:block">
                  <div className="text-sm font-medium text-slate-800">{user?.full_name}</div>
                  <div className="text-xs text-slate-600">
                    {user?.reputation || 0} reputation • {user?.origin_country || 'Community Member'}
                  </div>
                </div>
                <Button variant="outline" size="sm" onClick={logout}>
                  Logout
                </Button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        {!currentQuestion ? (
          /* Questions List */
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-800">
                Recent Questions ({questions.length})
              </h2>
            </div>
            
            {questions.length === 0 ? (
              <Card>
                <CardContent className="text-center py-12">
                  <MessageCircle className="h-12 w-12 mx-auto text-slate-400 mb-4" />
                  <h3 className="text-lg font-medium text-slate-600 mb-2">No questions yet</h3>
                  <p className="text-slate-500">Be the first to ask the community for help!</p>
                </CardContent>
              </Card>
            ) : (
              questions.map((question) => (
                <Card key={question.id} className="hover:shadow-md transition-shadow cursor-pointer card-interactive">
                  <CardContent className="p-6">
                    <div className="flex justify-between items-start">
                      <div className="flex-1 mr-4">
                        <div className="flex items-start justify-between mb-2">
                          <h3 
                            className="text-lg font-medium text-slate-800 hover:text-indigo-600 mr-4"
                            onClick={() => fetchQuestion(question.id)}
                          >
                            {question.title}
                          </h3>
                          {question.urgency && question.urgency !== 'normal' && (
                            <Badge className={`${getUrgencyColor(question.urgency)} border`}>
                              {question.urgency}
                            </Badge>
                          )}
                        </div>
                        <p className="text-slate-600 mb-3 line-clamp-2">
                          {question.content}
                        </p>
                        <div className="flex items-center space-x-4 text-sm text-slate-500 mb-3">
                          <div className="flex items-center">
                            <User className="h-4 w-4 mr-1" />
                            {question.author_username}
                          </div>
                          <div className="flex items-center">
                            <Clock className="h-4 w-4 mr-1" />
                            {formatDate(question.created_at)}
                          </div>
                          <div className="flex items-center">
                            <Eye className="h-4 w-4 mr-1" />
                            {question.views}
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          {question.tags.map((tag, index) => (
                            <Badge key={index} variant="secondary" className="immigration-tag">
                              <Tag className="h-3 w-3 mr-1" />
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      
                      <div className="flex flex-col items-center space-y-4">
                        <div className="text-center">
                          <div className="text-lg font-semibold text-slate-700">{question.votes}</div>
                          <div className="text-xs text-slate-500">votes</div>
                        </div>
                        <div className="text-center">
                          <div className="text-lg font-semibold text-indigo-600">{question.answers_count}</div>
                          <div className="text-xs text-slate-500">answers</div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        ) : (
          /* Question Detail */
          <div className="space-y-6">
            <Button 
              variant="outline" 
              onClick={() => {
                setCurrentQuestion(null);
                fetchQuestions();
              }}
            >
              ← Back to Questions
            </Button>
            
            {/* Question */}
            <Card>
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <h1 className="text-2xl font-bold text-slate-800 flex-1">
                    {currentQuestion.title}
                  </h1>
                  {currentQuestion.urgency && currentQuestion.urgency !== 'normal' && (
                    <Badge className={`${getUrgencyColor(currentQuestion.urgency)} border ml-4`}>
                      {currentQuestion.urgency}
                    </Badge>
                  )}
                </div>
                <div className="flex items-center space-x-4 text-sm text-slate-500 mb-4">
                  <div className="flex items-center">
                    <User className="h-4 w-4 mr-1" />
                    {currentQuestion.author_username}
                  </div>
                  <div className="flex items-center">
                    <Clock className="h-4 w-4 mr-1" />
                    {formatDate(currentQuestion.created_at)}
                  </div>
                  <div className="flex items-center">
                    <Eye className="h-4 w-4 mr-1" />
                    {currentQuestion.views} views
                  </div>
                </div>
                <p className="text-slate-700 mb-4 whitespace-pre-wrap">
                  {currentQuestion.content}
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {currentQuestion.tags.map((tag, index) => (
                      <Badge key={index} variant="secondary" className="immigration-tag">
                        <Tag className="h-3 w-3 mr-1" />
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => handleVote(currentQuestion.id, 'question', 1)}
                    >
                      <ThumbsUp className="h-4 w-4 mr-1" />
                      {currentQuestion.votes}
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => handleVote(currentQuestion.id, 'question', -1)}
                    >
                      <ThumbsDown className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Answers */}
            <div>
              <h2 className="text-xl font-semibold text-slate-800 mb-4">
                {answers.length} Answer{answers.length !== 1 ? 's' : ''}
              </h2>
              
              <div className="space-y-4">
                {answers.map((answer) => {
                  const verificationStatus = getAnswerVerificationStatus(answer);
                  return (
                    <Card key={answer.id}>
                      <CardContent className="p-6">
                        <div className="flex justify-between items-start">
                          <div className="flex-1 mr-4">
                            <div className="flex items-center space-x-2 mb-3">
                              {verificationStatus && (
                                <div className={`flex items-center space-x-1 ${verificationStatus.color}`}>
                                  <verificationStatus.icon className="h-4 w-4" />
                                  <span className="text-sm font-medium">{verificationStatus.text}</span>
                                </div>
                              )}
                            </div>
                            <p className="text-slate-700 mb-3 whitespace-pre-wrap">
                              {answer.content}
                            </p>
                            {answer.ai_verification?.feedback && (
                              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-3">
                                <div className="flex items-start space-x-2">
                                  <Bot className="h-4 w-4 text-indigo-600 mt-0.5" />
                                  <div>
                                    <div className="text-sm font-medium text-slate-700 mb-1">AI Verification Notes:</div>
                                    <div className="text-sm text-slate-600">{answer.ai_verification.feedback}</div>
                                  </div>
                                </div>
                              </div>
                            )}
                            <div className="flex items-center space-x-4 text-sm text-slate-500">
                              <div className="flex items-center">
                                <User className="h-4 w-4 mr-1" />
                                {answer.author_username}
                              </div>
                              <div className="flex items-center">
                                <Clock className="h-4 w-4 mr-1" />
                                {formatDate(answer.created_at)}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => handleVote(answer.id, 'answer', 1)}
                            >
                              <ThumbsUp className="h-4 w-4 mr-1" />
                              {answer.votes}
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => handleVote(answer.id, 'answer', -1)}
                            >
                              <ThumbsDown className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              {/* Answer Form */}
              <Card className="mt-6">
                <CardContent className="p-6">
                  <h3 className="text-lg font-medium text-slate-800 mb-4">Share Your Knowledge</h3>
                  <p className="text-sm text-slate-600 mb-4">
                    Help a fellow immigrant by sharing your experience. Our AI will verify the accuracy of your answer.
                  </p>
                  <form onSubmit={handleCreateAnswer} className="space-y-4">
                    <Textarea
                      placeholder="Share your experience and knowledge... Be specific about processes, requirements, and any helpful details."
                      rows={6}
                      value={answerContent}
                      onChange={(e) => setAnswerContent(e.target.value)}
                      required
                    />
                    <Button type="submit" disabled={loading} className="bg-indigo-600 hover:bg-indigo-700">
                      {loading ? 'Posting & Fact-checking...' : 'Post Answer (Will be AI-verified)'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>

      {/* AI Immigration Assistant Button */}
      <Button
        className="fixed bottom-6 right-6 rounded-full w-14 h-14 shadow-lg bg-indigo-600 hover:bg-indigo-700"
        onClick={() => setIsChatOpen(true)}
      >
        <Bot className="h-6 w-6" />
      </Button>

      {/* AI Immigration Assistant Dialog */}
      {isChatOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="w-full max-w-md h-96 flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center">
                <Bot className="h-5 w-5 mr-2 text-indigo-600" />
                Immigration AI Assistant
              </CardTitle>
              <Button variant="outline" size="sm" onClick={() => setIsChatOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col">
              <div className="flex-1 overflow-y-auto space-y-3 mb-4">
                {chatMessages.length === 0 && (
                  <div className="text-center text-slate-500 py-8">
                    <Bot className="h-8 w-8 mx-auto mb-2 text-indigo-600" />
                    <p className="text-sm">Hi! I'm your immigration AI assistant. I can help with:</p>
                    <ul className="text-xs mt-2 space-y-1">
                      <li>• Immigration processes and requirements</li>
                      <li>• Document preparation guidance</li>
                      <li>• Timeline estimates</li>
                      <li>• General immigration advice</li>
                    </ul>
                  </div>
                )}
                {chatMessages.map((message, index) => (
                  <div key={index} className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-xs px-3 py-2 rounded-lg ${
                      message.sender === 'user' 
                        ? 'bg-indigo-500 text-white' 
                        : 'bg-slate-100 text-slate-800'
                    }`}>
                      <div className="text-sm whitespace-pre-wrap">{message.text}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center space-x-2">
                <Input
                  placeholder="Ask about immigration..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleChatMessage()}
                />
                <Button size="sm" onClick={handleChatMessage}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

export default App;