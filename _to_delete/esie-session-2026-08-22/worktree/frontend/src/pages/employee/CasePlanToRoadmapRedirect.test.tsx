import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { CasePlanToRoadmapRedirect } from './CasePlanToRoadmapRedirect';

afterEach(cleanup);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/employee/case/:caseId/plan" element={<CasePlanToRoadmapRedirect />} />
        <Route path="/employee/case/:caseId/roadmap" element={<div>ROADMAP</div>} />
        <Route path="/employee/dashboard" element={<div>DASHBOARD</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('CasePlanToRoadmapRedirect — Plan→Roadmap consolidation (AIQ-1259b)', () => {
  it('redirects /plan to the case-scoped roadmap, preserving caseId', () => {
    renderAt('/employee/case/abc-123/plan');
    expect(screen.getByText('ROADMAP')).toBeInTheDocument();
  });
});
