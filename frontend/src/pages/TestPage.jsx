import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { motion } from 'framer-motion';
import { ArrowLeft, FlaskConical, Clock, CheckCircle, Play, RefreshCw } from 'lucide-react';
import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import DOMPurify from 'dompurify';

const TestPage = () => {
  const { testId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [testData, setTestData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [answers, setAnswers] = useState({});

  useEffect(() => {
    const fetchTestData = async () => {
      if (!testId || !user?.authToken) return;

      setIsLoading(true);

      try {
        const response = await fetch('http://localhost:8000/test-details', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            authToken: user.authToken,
            testId: testId
          })
        });

        const data = await response.json();

        if (response.ok && data.success) {
          setTestData(data.test);
        } else if (data.detail === 'token_expired') {
          toast.error('Session Expired. Please Login again.');
          navigate('/login');
        } else {
          toast.error('Failed to load test details');
        }
      } catch (error) {
        console.error('Error fetching test data:', error);
        toast.error('Failed to load test details');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTestData();
  }, [testId, user?.authToken, navigate]);

  const handleAnswerChange = (questionId, answer) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: answer
    }));
  };

  const handleSubmitTest = async () => {
    if (!user?.authToken) return;

    setIsSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/submit-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          authToken: user.authToken,
          testId: testId,
          answers: answers
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        toast.success('Test submitted successfully!');
        navigate('/');
      } else {
        toast.error(data.detail || 'Failed to submit test');
      }
    } catch (error) {
      console.error('Error submitting test:', error);
      toast.error('Failed to submit test');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ backgroundColor: '#0A0A0A' }}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2" style={{ borderColor: '#8B5CF6' }}></div>
      </div>
    );
  }

  return (
    <div style={{ backgroundColor: '#0A0A0A', fontFamily: 'Satoshi, system-ui, -apple-system, sans-serif' }}>
      {/* Header */}
      <header
        className="h-20 px-8 flex items-center justify-between"
        style={{
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          backgroundColor: 'rgba(10,10,10,0.8)',
          backdropFilter: 'blur(20px)'
        }}
      >
        <div className="flex items-center gap-4">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => navigate('/')}
            className="p-2 rounded-xl transition-colors"
            style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: '#9CA3AF' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)';
              e.currentTarget.style.color = '#FFFFFF';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)';
              e.currentTarget.style.color = '#9CA3AF';
            }}
          >
            <ArrowLeft size={20} />
          </motion.button>
          <div>
            <h2 className="text-2xl font-bold" style={{ color: '#FFFFFF', fontWeight: 600 }}>
              Test Details
            </h2>
            <p className="text-sm" style={{ color: '#6B7280' }}>
              {testData?.name || 'Loading...'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div
            className="flex items-center gap-2.5 px-4 py-2 rounded-xl"
            style={{
              backgroundColor: 'rgba(139,92,246,0.1)',
              border: '1px solid rgba(139,92,246,0.2)'
            }}
          >
            <FlaskConical size={18} style={{ color: '#8B5CF6' }} />
            <span className="text-sm font-semibold" style={{ color: '#8B5CF6', fontWeight: 600 }}>
              AI Model Testing
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto p-8">
        {testData ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Test Info Card */}
            <div
              className="p-6 rounded-2xl"
              style={{
                background: 'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)',
                border: '1px solid rgba(255,255,255,0.06)'
              }}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-2xl font-bold mb-2" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                    {testData.name}
                  </h3>
                  <p className="text-base" style={{ color: '#9CA3AF', lineHeight: 1.6 }}>
                    {testData.description}
                  </p>
                </div>
                <div className="flex gap-2">
                  <div
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
                    style={{ backgroundColor: 'rgba(139,92,246,0.1)', color: '#8B5CF6' }}
                  >
                    <Clock size={14} />
                    <span className="text-sm font-medium">30 min</span>
                  </div>
                  <div
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
                    style={{ backgroundColor: 'rgba(16,185,129,0.1)', color: '#10B981' }}
                  >
                    <CheckCircle size={14} />
                    <span className="text-sm font-medium">Active</span>
                  </div>
                </div>
              </div>

              {/* Requirements List */}
              {testData.details && Array.isArray(testData.details) && testData.details.length > 0 && (
                <div className="mt-6 space-y-4">
                  <h4 className="text-lg font-semibold" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                    Requirements
                  </h4>
                  <div className="grid gap-4">
                    {testData.details.map((item, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className="p-4 rounded-lg"
                        style={{
                          background: 'linear-gradient(135deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0.01) 100%)',
                          border: '1px solid rgba(255,255,255,0.06)'
                        }}
                      >
                        <h5 className="text-sm font-semibold mb-2" style={{ color: '#A855F7', fontWeight: 600 }}>
                          {item.title}
                        </h5>
                        <div
                          className="text-sm"
                          style={{ color: '#9CA3AF', lineHeight: 1.6 }}
                          dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(item.description) }}
                        />
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Questions Section */}
            {testData.questions && testData.questions.length > 0 ? (
              <div className="space-y-4">
                <h4 className="text-xl font-bold" style={{ color: '#FFFFFF', fontWeight: 600 }}>
                  Questions
                </h4>

                {testData.questions.map((question, index) => (
                  <motion.div
                    key={question.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="p-5 rounded-xl"
                    style={{
                      background: 'linear-gradient(135deg, rgba(255,255,255,0.02) 0%, rgba(255,255,255,0.01) 100%)',
                      border: '1px solid rgba(255,255,255,0.06)'
                    }}
                  >
                    <div className="flex items-start gap-4 mb-4">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-semibold"
                        style={{
                          background: 'linear-gradient(135deg, rgba(139,92,246,0.2) 0%, rgba(168,85,247,0.1) 100%)',
                          color: '#8B5CF6'
                        }}
                      >
                        {index + 1}
                      </div>
                      <div className="flex-1">
                        <p className="text-base font-medium mb-3" style={{ color: '#FFFFFF', fontWeight: 500 }}>
                          {question.question}
                        </p>

                        {/* Answer Options */}
                        <div className="space-y-2">
                          {question.options?.map((option, optIndex) => (
                            <label
                              key={optIndex}
                              className="flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all"
                              style={{
                                backgroundColor: answers[question.id] === option ? 'rgba(139,92,246,0.15)' : 'rgba(255,255,255,0.02)',
                                border: answers[question.id] === option ? '1px solid rgba(139,92,246,0.3)' : '1px solid rgba(255,255,255,0.06)'
                              }}
                            >
                              <input
                                type="radio"
                                name={`question-${question.id}`}
                                value={option}
                                checked={answers[question.id] === option}
                                onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                                className="hidden"
                              />
                              <div
                                className="w-5 h-5 rounded-full flex items-center justify-center"
                                style={{
                                  border: '2px solid',
                                  borderColor: answers[question.id] === option ? '#8B5CF6' : '#6B7280'
                                }}
                              >
                                {answers[question.id] === option && (
                                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#8B5CF6' }} />
                                )}
                              </div>
                              <span className="text-sm" style={{ color: '#9CA3AF' }}>
                                {option}
                              </span>
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : null}

            {/* Submit Button */}
            <div className="flex justify-end gap-3 pt-4">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/')}
                className="px-6 py-3 rounded-xl font-medium"
                style={{
                  backgroundColor: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: '#9CA3AF'
                }}
              >
                Cancel
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleSubmitTest}
                disabled={isSubmitting}
                className="px-6 py-3 rounded-xl font-medium flex items-center gap-2"
                style={{
                  background: 'linear-gradient(90deg, #8B5CF6 0%, #A855F7 100%)',
                  color: '#FFFFFF',
                  opacity: isSubmitting ? 0.7 : 1
                }}
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <>
                    <Play size={18} />
                    <span>Submit Test</span>
                  </>
                )}
              </motion.button>
            </div>
          </motion.div>
        ) : (
          <div className="text-center py-20">
            <FlaskConical size={48} style={{ color: '#6B7280' }} />
            <p className="mt-4 text-lg" style={{ color: '#6B7280' }}>
              Test not found or failed to load
            </p>
          </div>
        )}
      </main>
    </div>
  );
};

export default TestPage;