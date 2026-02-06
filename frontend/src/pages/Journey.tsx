import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ProgressHeader } from '../components/ProgressHeader';
import { GuidedQuestionCard } from '../components/GuidedQuestionCard';
import { ProfileSidebar } from '../components/ProfileSidebar';
import { Container, Button, Alert } from '../components/antigravity';
import { profileAPI } from '../api/client';
import type { Question, RelocationProfile, NextQuestionResponse } from '../types';

export const Journey: React.FC = () => {
  const [profile, setProfile] = useState<RelocationProfile | null>(null);
  const [nextQuestion, setNextQuestion] = useState<NextQuestionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showSidebar, setShowSidebar] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [profileData, questionData] = await Promise.all([
        profileAPI.getCurrent(),
        profileAPI.getNextQuestion(),
      ]);
      
      setProfile(profileData);
      setNextQuestion(questionData);
      
      // If complete, redirect to dashboard
      if (questionData.isComplete) {
        navigate('/dashboard');
      }
    } catch (err: any) {
      if (err.response?.status === 401) {
        navigate('/');
      } else {
        setError('Failed to load profile. Please refresh.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnswer = async (answer: any, isUnknown: boolean) => {
    if (!nextQuestion?.question) return;

    try {
      const response = await profileAPI.submitAnswer({
        questionId: nextQuestion.question.id,
        answer,
        isUnknown,
      });

      // Update state with new question
      setNextQuestion(response.nextQuestion);
      
      // Reload profile
      const updatedProfile = await profileAPI.getCurrent();
      setProfile(updatedProfile);

      // If complete, navigate to dashboard
      if (response.nextQuestion.isComplete) {
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError('Failed to save answer. Please try again.');
    }
  };

  const handleFinishLater = () => {
    navigate('/dashboard');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your profile...</p>
        </div>
      </div>
    );
  }

  if (!profile || !nextQuestion) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Alert variant="error">{error || 'Failed to load data'}</Alert>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Progress Header */}
      <ProgressHeader
        answeredCount={nextQuestion.progress.answeredCount}
        totalQuestions={nextQuestion.progress.totalQuestions}
        percentComplete={nextQuestion.progress.percentComplete}
      />

      {/* Main Content */}
      <Container maxWidth="xl" className="py-8">
        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}

        <div className="flex flex-col lg:flex-row gap-8">
          {/* Main Question Area */}
          <div className="flex-1">
            {nextQuestion.question ? (
              <div className="space-y-4">
                <GuidedQuestionCard
                  question={nextQuestion.question}
                  onAnswer={handleAnswer}
                />
                
                <div className="text-center">
                  <button
                    onClick={handleFinishLater}
                    className="text-sm text-gray-600 hover:text-gray-900 underline"
                  >
                    Save and finish later
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Profile Complete! 🎉
                </h2>
                <p className="text-gray-600 mb-6">
                  You've provided enough information. Let's see your recommendations.
                </p>
                <Button onClick={() => navigate('/dashboard')}>
                  View Dashboard
                </Button>
              </div>
            )}
          </div>

          {/* Sidebar */}
          {showSidebar && (
            <div className="lg:w-80">
              <div className="sticky top-8">
                <ProfileSidebar profile={profile} />
              </div>
            </div>
          )}
        </div>
      </Container>
    </div>
  );
};
