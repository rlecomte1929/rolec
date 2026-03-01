import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { RecommendationResponse } from '../recommendations/types';
import type { ServiceKey } from './serviceConfig';

interface ServicesFlowState {
  selectedServices: Set<ServiceKey>;
  setSelectedServices: (next: Set<ServiceKey>) => void;
  answers: Record<string, unknown>;
  setAnswers: (next: Record<string, unknown>) => void;
  recommendations: Record<string, RecommendationResponse> | null;
  setRecommendations: (next: Record<string, RecommendationResponse> | null) => void;
  shortlist: Map<string, string>;
  setShortlist: (next: Map<string, string>) => void;
}

const ServicesFlowContext = createContext<ServicesFlowState | null>(null);

export const ServicesFlowProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedServices, setSelectedServices] = useState<Set<ServiceKey>>(() => {
    try {
      const raw = localStorage.getItem('services_selected');
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [answers, setAnswers] = useState<Record<string, unknown>>(() => {
    try {
      const raw = localStorage.getItem('services_answers');
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });
  const [recommendations, setRecommendations] = useState<Record<string, RecommendationResponse> | null>(() => {
    try {
      const raw = localStorage.getItem('services_recommendations');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [shortlist, setShortlist] = useState<Map<string, string>>(() => {
    try {
      const raw = localStorage.getItem('services_shortlist');
      return raw ? new Map(JSON.parse(raw)) : new Map();
    } catch {
      return new Map();
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('services_selected', JSON.stringify(Array.from(selectedServices)));
    } catch {
      // ignore persistence failures
    }
  }, [selectedServices]);

  useEffect(() => {
    try {
      localStorage.setItem('services_answers', JSON.stringify(answers));
    } catch {
      // ignore
    }
  }, [answers]);

  useEffect(() => {
    try {
      localStorage.setItem('services_recommendations', JSON.stringify(recommendations));
    } catch {
      // ignore
    }
  }, [recommendations]);

  useEffect(() => {
    try {
      localStorage.setItem('services_shortlist', JSON.stringify(Array.from(shortlist.entries())));
    } catch {
      // ignore
    }
  }, [shortlist]);

  const value = useMemo(
    () => ({
      selectedServices,
      setSelectedServices,
      answers,
      setAnswers,
      recommendations,
      setRecommendations,
      shortlist,
      setShortlist,
    }),
    [selectedServices, answers, recommendations, shortlist]
  );

  return (
    <ServicesFlowContext.Provider value={value}>
      {children}
    </ServicesFlowContext.Provider>
  );
};

export const useServicesFlow = () => {
  const ctx = useContext(ServicesFlowContext);
  if (!ctx) {
    throw new Error('useServicesFlow must be used within ServicesFlowProvider');
  }
  return ctx;
};
