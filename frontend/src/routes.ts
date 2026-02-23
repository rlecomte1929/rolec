export const ROUTES = {
  EMP_DASH: "/employee/dashboard",
  CASE_WIZARD: "/employee/case/:caseId/wizard",
  CASE_WIZARD_STEP: "/employee/case/:caseId/wizard/:step",
  CASE_REVIEW: "/employee/case/:caseId/review",
  CASE_SUMMARY: "/employee/case/:caseId/summary",
  ADMIN_COUNTRIES: "/admin/countries",
  ADMIN_COUNTRY_DETAIL: "/admin/countries/:countryCode",
} as const;
