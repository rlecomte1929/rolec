export const EMPLOYEE_POLICY_ASSISTANT_TITLE = 'Policy Assistant';

export const EMPLOYEE_POLICY_ASSISTANT_SUBTITLE =
  'Questions use your company’s published relocation policy for this assignment.';

/** Same as subtitle; used where the sheet chrome repeats context. */
export const EMPLOYEE_POLICY_ASSISTANT_PANEL_INTRO = EMPLOYEE_POLICY_ASSISTANT_SUBTITLE;

export const EMPLOYEE_POLICY_ASSISTANT_PLACEHOLDER =
  'Example: What is my shipment allowance?';

export const EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER =
  'Answers are based on your company’s published relocation policy in ReloPass.';

export const EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER_SECONDARY = 'Not legal or immigration advice.';

export const EMPLOYEE_POLICY_ASSISTANT_NO_ASSIGNMENT =
  'Link an active assignment to use policy Q&A.';

export const EMPLOYEE_POLICY_ASSISTANT_SUBMIT = 'Get answer →';

/** Inline hint when submit is clicked with an empty question (clears on input or chip). */
export const EMPLOYEE_POLICY_ASSISTANT_EMPTY_HINT =
  'Enter a policy question or pick a sample below.';

export const EMPLOYEE_POLICY_ASSISTANT_SHORTCUTS_TITLE = 'Sample policy questions';

/** Max four shortcuts in UI; keep phrasing short for consistent chip layout. */
export const EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS: string[] = [
  'What housing support is included in my policy?',
  'What is my shipment allowance?',
  'Do any benefits need approval?',
  'Is school search support included?',
];

/** Shown under the answers heading when any Q&A is stored locally. */
export const EMPLOYEE_POLICY_ASSISTANT_SAVED_HINT =
  'Recent questions and answers are saved on this device for this assignment so you can reopen the assistant without starting over.';

export const EMPLOYEE_POLICY_ASSISTANT_CLEAR_HISTORY = 'Clear saved Q&A';

export const EMPLOYEE_POLICY_ASSISTANT_COPY_ANSWER = 'Copy answer';

export const EMPLOYEE_POLICY_ASSISTANT_COPIED = 'Copied';

/** When the API returns an unhelpful generic error string. */
export const EMPLOYEE_POLICY_ASSISTANT_ERROR_TITLE = 'We couldn’t get an answer right now.';

export const EMPLOYEE_POLICY_ASSISTANT_ERROR_DETAIL =
  'Check your connection and try again. If this keeps happening, contact HR.';
