import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { LegacyWizardRedirect } from './LegacyWizardRedirect';

afterEach(cleanup);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/employee/case/:caseId/wizard/:step" element={<LegacyWizardRedirect />} />
        <Route path="/employee/case/:caseId/wizard" element={<LegacyWizardRedirect />} />
        <Route path="/employee/case/:caseId/review" element={<LegacyWizardRedirect />} />
        <Route path="/employee/case/:caseId/intake" element={<div>V2 INTAKE</div>} />
        <Route path="/employee/intake" element={<div>BARE INTAKE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('LegacyWizardRedirect — staged wizard unification (C1)', () => {
  it('redirects /wizard/:step to the case-scoped v2 intake', () => {
    renderAt('/employee/case/abc-123/wizard/1');
    expect(screen.getByText('V2 INTAKE')).toBeInTheDocument();
  });

  it('redirects bare /wizard to the case-scoped v2 intake', () => {
    renderAt('/employee/case/abc-123/wizard');
    expect(screen.getByText('V2 INTAKE')).toBeInTheDocument();
  });

  it('redirects /review to the case-scoped v2 intake', () => {
    renderAt('/employee/case/abc-123/review');
    expect(screen.getByText('V2 INTAKE')).toBeInTheDocument();
  });
});
