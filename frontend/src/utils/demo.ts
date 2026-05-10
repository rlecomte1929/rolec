export const getAuthItem = (key: string) => localStorage.getItem(key);

/** Normalize role from API/storage so ADMIN/HR/EMPLOYEE comparisons stay reliable. */
export const normalizeStoredRole = (raw: string | null | undefined): string =>
  (raw ?? '').trim().toUpperCase();

export const setAuthItem = (key: string, value: string) => {
  localStorage.setItem(key, value);
};

export const clearAuthItems = () => {
  Object.keys(localStorage)
    .filter((key) => key.startsWith('relopass_'))
    .forEach((key) => localStorage.removeItem(key));
};
