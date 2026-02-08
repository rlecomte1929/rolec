export const getAuthItem = (key: string) => localStorage.getItem(key);

export const setAuthItem = (key: string, value: string) => {
  localStorage.setItem(key, value);
};

export const clearAuthItems = () => {
  Object.keys(localStorage)
    .filter((key) => key.startsWith('relopass_'))
    .forEach((key) => localStorage.removeItem(key));
};
