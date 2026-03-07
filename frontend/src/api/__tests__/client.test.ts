import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock axios before importing client
vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  
  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

// Import after mock
import { authAPI, profileAPI, recommendationsAPI, dashboardAPI } from '../client';

describe('API Client', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('authAPI', () => {
    it('should have login method', () => {
      expect(authAPI.login).toBeDefined();
      expect(typeof authAPI.login).toBe('function');
    });
  });

  describe('profileAPI', () => {
    it('should have all profile methods', () => {
      expect(profileAPI.getCurrent).toBeDefined();
      expect(profileAPI.getNextQuestion).toBeDefined();
      expect(profileAPI.submitAnswer).toBeDefined();
      expect(profileAPI.complete).toBeDefined();
    });
  });

  describe('recommendationsAPI', () => {
    it('should have all recommendation methods', () => {
      expect(recommendationsAPI.getHousing).toBeDefined();
      expect(recommendationsAPI.getSchools).toBeDefined();
      expect(recommendationsAPI.getMovers).toBeDefined();
    });
  });

  describe('dashboardAPI', () => {
    it('should have get method', () => {
      expect(dashboardAPI.get).toBeDefined();
    });
  });
});
