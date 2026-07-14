const LINKEDIN_DM_LIMIT = 300;

export function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`(.*?)`/g, '$1')
    .replace(/#{1,6}\s/g, '')
    .trim();
}

export function isOverLinkedInLimit(text: string): boolean {
  return text.length > LINKEDIN_DM_LIMIT;
}

export function linkedInCharCount(text: string): number {
  return text.length;
}
