import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { FormProceedBriefing } from '../FormProceedBriefing';
import type { FormProceedBriefingModel } from '../formEditorCopy';

afterEach(cleanup);

const model: FormProceedBriefingModel = {
  title: 'How to finish this registration',
  filledLine: 'ReloPass already filled 2 fields from your intake and documents. Check those values; only change what is wrong.',
  youDoLine: 'Add the remaining answers below — then mark the pack ready.',
  missingLabels: ['Norwegian address'],
  missingOverflow: 0,
  submitLine: 'When the pack is ready, submit on the official site (Politiet). ReloPass does not file this for you.',
  authorityName: 'Politiet',
  hasFields: true,
};

describe('FormProceedBriefing', () => {
  it('shows remaining fields and the official site link', () => {
    render(
      <FormProceedBriefing
        model={model}
        officialUrl="https://www.politiet.no/en/services/residence/"
      />,
    );
    expect(screen.getByTestId('form-proceed-briefing')).toHaveTextContent(
      'How to finish this registration',
    );
    expect(screen.getByText('Norwegian address')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /open official site/i });
    expect(link).toHaveAttribute(
      'href',
      'https://www.politiet.no/en/services/residence/',
    );
  });
});
