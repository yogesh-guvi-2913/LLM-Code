import { Lightbulb, X, CheckCircle } from 'lucide-react';
import DOMPurify from 'dompurify';
import { useTest } from '../../contexts/TestContext';

function ProblemModal() {
  const {
    testData,
    showProblemModal,
    setShowProblemModal,
    answers,
    handleAnswerChange
  } = useTest();

  if (!showProblemModal || !testData) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={() => setShowProblemModal(false)}>
      <div className="bg-[#0a0a0b] rounded-2xl border border-white/[0.1] w-full max-w-3xl max-h-[80vh] flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
              <Lightbulb size={20} className="text-violet-400" />
            </div>
            <h2 className="text-lg font-semibold text-white">Problem Statement</h2>
          </div>
          <button
            onClick={() => setShowProblemModal(false)}
            className="p-2 rounded-lg hover:bg-white/[0.05] transition-colors"
          >
            <X size={18} className="text-gray-400" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
          <h3 className="text-xl font-semibold text-white mb-4">{testData.name}</h3>
          <p className="text-sm leading-relaxed text-gray-400 mb-6">{testData.description}</p>

          {testData.details && Array.isArray(testData.details) && testData.details.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-white mb-3">Requirements</h4>
              {testData.details.map((item, index) => (
                <div
                  key={index}
                  className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]"
                >
                  <h5 className="font-semibold text-sm mb-2 text-violet-400">
                    {item.title}
                  </h5>
                  <div
                    className="text-sm leading-relaxed text-gray-400"
                    dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(item.description) }}
                  />
                </div>
              ))}
            </div>
          )}

          {testData.questions && testData.questions.length > 0 && (
            <div className="space-y-3 mt-6">
              <h4 className="text-sm font-semibold text-white mb-3">Questions</h4>
              {testData.questions.map((question, index) => (
                <div
                  key={question.id}
                  className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.02]"
                >
                  <div className="flex items-start gap-3 mb-3">
                    <div className="w-7 h-7 rounded-lg bg-violet-500/15 flex items-center justify-center text-sm font-semibold text-violet-400 flex-shrink-0">
                      {index + 1}
                    </div>
                    <p className="text-sm font-medium text-white flex-1">
                      {question.question}
                    </p>
                    {answers[question.id] && (
                      <CheckCircle size={16} className="text-emerald-400 flex-shrink-0" />
                    )}
                  </div>
                  <div className="space-y-2 ml-10">
                    {question.options?.map((option, optIndex) => (
                      <label
                        key={optIndex}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all border text-sm ${
                          answers[question.id] === option
                            ? 'bg-violet-500/10 border-violet-500/30 text-violet-300'
                            : 'bg-white/[0.02] border-white/[0.06] text-gray-400 hover:bg-white/[0.04]'
                        }`}
                      >
                        <input
                          type="radio"
                          name={`modal-question-${question.id}`}
                          value={option}
                          checked={answers[question.id] === option}
                          onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                          className="hidden"
                        />
                        <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                          answers[question.id] === option
                            ? 'border-violet-500'
                            : 'border-gray-500'
                        }`}>
                          {answers[question.id] === option && (
                            <div className="w-2 h-2 rounded-full bg-violet-500" />
                          )}
                        </div>
                        <span>{option}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t border-white/[0.06] flex justify-end">
          <button
            onClick={() => setShowProblemModal(false)}
            className="px-6 py-2.5 rounded-xl bg-violet-500 text-white text-sm font-medium hover:bg-violet-600 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default ProblemModal;