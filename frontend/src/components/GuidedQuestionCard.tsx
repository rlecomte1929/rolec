import React, { useState, useEffect } from 'react';
import { Card, Button, Input } from './antigravity';
import type { Question } from '../types';

interface GuidedQuestionCardProps {
  question: Question;
  onAnswer: (answer: any, isUnknown: boolean) => void;
}

export const GuidedQuestionCard: React.FC<GuidedQuestionCardProps> = ({
  question,
  onAnswer,
}) => {
  const [answer, setAnswer] = useState<any>('');
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setAnswer('');
    setSelectedOptions([]);
    setIsSubmitting(false);
  }, [question.id]);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    
    let finalAnswer = answer;
    
    if (question.type === 'multi_select') {
      finalAnswer = selectedOptions;
    } else if (question.type === 'boolean') {
      finalAnswer = answer === 'true' || answer === true;
    } else if (question.type === 'single_select' && question.options && !answer) {
      return; // Require selection
    }
    
    await onAnswer(finalAnswer, false);
    setIsSubmitting(false);
  };

  const handleUnknown = async () => {
    setIsSubmitting(true);
    await onAnswer(null, true);
    setIsSubmitting(false);
  };

  const handleQuickOption = (value: string) => {
    if (question.type === 'multi_select') {
      if (selectedOptions.includes(value)) {
        setSelectedOptions(selectedOptions.filter(v => v !== value));
      } else {
        setSelectedOptions([...selectedOptions, value]);
      }
    } else {
      setAnswer(value);
    }
  };

  const canSubmit = () => {
    if (question.type === 'multi_select') {
      return selectedOptions.length > 0;
    }
    if (question.type === 'boolean') {
      return answer !== '';
    }
    return answer !== '' && answer !== null && answer !== undefined;
  };

  return (
    <Card padding="lg" className="max-w-3xl mx-auto">
      <div className="space-y-6">
        {/* Question Title */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {question.title}
          </h2>
          {question.required && (
            <span className="text-sm text-red-600">* Required</span>
          )}
        </div>

        {/* Why This Matters */}
        <div className="bg-indigo-50 border-l-4 border-indigo-500 p-4 rounded">
          <p className="text-sm text-indigo-900">
            <span className="font-semibold">Why we ask this: </span>
            {question.whyThisMatters}
          </p>
        </div>

        {/* Input Based on Type */}
        <div className="space-y-4">
          {question.type === 'single_select' && question.options && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {question.options.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleQuickOption(option.value)}
                  className={`p-4 border-2 rounded-lg text-left transition-all ${
                    answer === option.value
                      ? 'border-indigo-600 bg-indigo-50'
                      : 'border-gray-300 hover:border-indigo-400'
                  }`}
                >
                  <div className="font-medium text-gray-900">{option.label}</div>
                </button>
              ))}
            </div>
          )}

          {question.type === 'multi_select' && question.options && (
            <div className="space-y-2">
              {question.options.map((option) => (
                <label
                  key={option.value}
                  className="flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedOptions.includes(option.value)}
                    onChange={() => handleQuickOption(option.value)}
                    className="w-4 h-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <span className="ml-3 text-gray-900">{option.label}</span>
                </label>
              ))}
            </div>
          )}

          {question.type === 'text' && (
            <Input
              type="text"
              value={answer}
              onChange={setAnswer}
              placeholder="Enter your answer"
              fullWidth
            />
          )}

          {question.type === 'date' && (
            <Input
              type="date"
              value={answer}
              onChange={setAnswer}
              fullWidth
            />
          )}

          {question.type === 'number' && (
            <Input
              type="number"
              value={answer}
              onChange={setAnswer}
              placeholder="Enter a number"
              fullWidth
            />
          )}

          {question.type === 'boolean' && (
            <div className="flex gap-4">
              <button
                onClick={() => setAnswer('true')}
                className={`flex-1 p-4 border-2 rounded-lg transition-all ${
                  answer === 'true'
                    ? 'border-indigo-600 bg-indigo-50'
                    : 'border-gray-300 hover:border-indigo-400'
                }`}
              >
                <div className="font-medium text-gray-900">Yes</div>
              </button>
              <button
                onClick={() => setAnswer('false')}
                className={`flex-1 p-4 border-2 rounded-lg transition-all ${
                  answer === 'false'
                    ? 'border-indigo-600 bg-indigo-50'
                    : 'border-gray-300 hover:border-indigo-400'
                }`}
              >
                <div className="font-medium text-gray-900">No</div>
              </button>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit() || isSubmitting}
            fullWidth
          >
            {isSubmitting ? 'Saving...' : 'Continue'}
          </Button>
          {question.allowUnknown && (
            <Button
              onClick={handleUnknown}
              variant="outline"
              disabled={isSubmitting}
            >
              I don't know yet
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
};
