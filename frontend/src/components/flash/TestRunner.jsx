import React, { useState } from 'react';

const TestRunner = ({ testId, authToken, onSubmit }) => {
  const [status, setStatus] = useState('idle');
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  
  const handleSubmit = async () => {
    setStatus('running');
    setError(null);
    
    try {
      const mapperResponse = await fetch('/test-mapper', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          testId,
          authToken
        })
      });
      
      if (!mapperResponse.ok) {
        throw new Error('Failed to get session');
      }
      
      const mapperData = await mapperResponse.json();
      const sessionId = mapperData.flashSessionId;
      
      const submitResponse = await fetch('/submit-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          testId,
          authToken,
          chatHistory: []
        })
      });
      
      if (!submitResponse.ok) {
        throw new Error('Failed to submit test');
      }
      
      const pollResults = async () => {
        const resultsResponse = await fetch('/results', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify({
            testId,
            authToken
          })
        });
        
        if (!resultsResponse.ok) {
          throw new Error('Failed to get results');
        }
        
        const resultsData = await resultsResponse.json();
        
        if (resultsData.status === 'evaluating') {
          setTimeout(pollResults, 2000);
          return;
        }
        
        setResults(resultsData);
        setStatus('completed');
        onSubmit?.(resultsData);
      };
      
      setTimeout(pollResults, 2000);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test submission failed');
      setStatus('failed');
    }
  };
  
  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };
  
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Test Runner</h3>
      </div>
      
      <div className="p-4">
        {status === 'idle' && (
          <button
            onClick={handleSubmit}
            className="w-full px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded"
          >
            Submit Test
          </button>
        )}
        
        {status === 'running' && (
          <div className="flex items-center justify-center space-x-2">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600" />
            <span className="text-sm text-gray-600">Running tests...</span>
          </div>
        )}
        
        {error && (
          <div className="px-3 py-2 bg-red-100 text-red-700 text-sm rounded mb-3">
            {error}
          </div>
        )}
        
        {status === 'completed' && results && (
          <div className="space-y-4">
            <div className="text-center">
              <div className={`text-4xl font-bold ${getScoreColor(results.score)}`}>
                {results.score}/{results.maxScore}
              </div>
              <div className="text-sm text-gray-500 mt-1">
                {results.scoringMethod === 'hybrid' ? 'Hybrid Score' : 'LLM Score'}
              </div>
            </div>
            
            {results.scoringMethod === 'hybrid' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-3 bg-gray-50 rounded">
                  <div className="text-2xl font-bold text-blue-600">{results.flashScore}</div>
                  <div className="text-xs text-gray-500 mt-1">Automated Tests (70%)</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded">
                  <div className="text-2xl font-bold text-purple-600">{results.llmScore}</div>
                  <div className="text-xs text-gray-500 mt-1">Code Quality (30%)</div>
                </div>
              </div>
            )}
            
            {results.testResults && results.testResults.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-2">Test Results</h4>
                <div className="space-y-2">
                  {results.testResults.map((test, index) => (
                    <div key={index} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded">
                      <span className="text-sm text-gray-700">{test.name}</span>
                      <span className={`text-sm font-medium ${test.passed ? 'text-green-600' : 'text-red-600'}`}>
                        {test.passed ? '✓ Passed' : '✗ Failed'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {results.feedback && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-2">Feedback</h4>
                <div className="p-3 bg-gray-50 rounded text-sm text-gray-700 whitespace-pre-wrap">
                  {results.feedback}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TestRunner;