import type { LinkedInProspect, MessageTemplate } from '../types/outreach';

export function personaliseMessage(
  template: string,
  prospect: Pick<LinkedInProspect, 'full_name' | 'company_name' | 'job_title' | 'corridor_relevance'>
): string {
  const firstName: string = prospect.full_name.split(' ')[0] ?? prospect.full_name;
  const corridor: string = prospect.corridor_relevance ?? 'your corridor';
  return template
    .replace(/\{\{full_name\}\}/g, firstName)
    .replace(/\{\{company_name\}\}/g, prospect.company_name)
    .replace(/\{\{job_title\}\}/g, prospect.job_title)
    .replace(/\{\{corridor_relevance\}\}/g, corridor);
}

export function pickBestTemplate(
  templates: MessageTemplate[],
  messageType: 'initial' | 'follow_up' | 'reply_response'
): MessageTemplate | null {
  const active = templates.filter((t) => t.is_active && t.message_type === messageType);
  return active[0] ?? null;
}
