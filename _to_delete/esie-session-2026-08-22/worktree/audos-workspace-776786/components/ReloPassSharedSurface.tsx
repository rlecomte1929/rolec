/**
 * Shared ReloPass product surface — imported by EmailGate (signed-out) and Main (signed-in)
 * so both surfaces stay aligned on landing + unavailable-route UI.
 */
import { ReloPassLanding, type ReloPassLandingProps } from './ReloPassLanding';
import { UnavailableFeature } from './UnavailableFeature';
export { UnavailableFeature };
export type { UnavailableFeatureProps } from './UnavailableFeature';

export type ReloPassMarketingLandingProps = ReloPassLandingProps;

/** Faithful imported marketing homepage used in EmailGate and Main `#/` route. */
export function ReloPassMarketingLanding(props: ReloPassMarketingLandingProps) {
  return <ReloPassLanding {...props} />;
}

/** Surface sync marker — both EmailGate and Main must import from this module. */
export const ReloPassSharedSurface = {
  Landing: ReloPassMarketingLanding,
  UnavailableFeature,
} as const;
