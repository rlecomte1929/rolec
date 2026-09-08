/**
 * [P2-05] Roadmap success-probability scoring module.
 *
 * - successProbability(): pure scoring function (P2-05a)
 * - SuccessProbabilityDial: colour-coded dial with mandatory disclaimer (P2-05b)
 * - FactorsPanel: "Factors affecting your score" expandable panel (P2-05c)
 */
export {
  successProbability,
  CONFIDENCE_VALUE,
  HISTORY_WEIGHT,
} from './successProbability';
export type {
  ConfidenceLevel,
  ConfidenceBasis,
  ScoringStep,
  ScoringRoadmap,
  CaseOutcome,
  ScoreFactor,
  SuccessProbabilityResult,
} from './successProbability';
export { SuccessProbabilityDial } from './SuccessProbabilityDial';
export type { SuccessProbabilityDialProps } from './SuccessProbabilityDial';
export { FactorsPanel } from './FactorsPanel';
export type { FactorsPanelProps } from './FactorsPanel';
