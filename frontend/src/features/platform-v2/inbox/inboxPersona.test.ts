import { describe, expect, it } from 'vitest';
import {
  inboxPathForRole,
  isEmployeeInboxPath,
  isHrInboxPath,
  roleSwitchInboxPath,
} from './inboxPersona';

describe('inboxPersona', () => {
  it('treats /hr/messages as HR regardless of stored role', () => {
    expect(isHrInboxPath('/hr/messages')).toBe(true);
    expect(isHrInboxPath('/hr/messages/')).toBe(true);
    expect(isEmployeeInboxPath('/hr/messages')).toBe(false);
  });

  it('treats /messages as the employee inbox', () => {
    expect(isEmployeeInboxPath('/messages')).toBe(true);
    expect(isEmployeeInboxPath('/messages-v2')).toBe(true);
    expect(isHrInboxPath('/messages')).toBe(false);
  });

  it('maps inbox-to-inbox on role switch', () => {
    expect(roleSwitchInboxPath('HR', '/messages')).toBe('/hr/messages');
    expect(roleSwitchInboxPath('EMPLOYEE', '/hr/messages')).toBe('/messages');
    expect(roleSwitchInboxPath('HR', '/hr/dashboard')).toBeNull();
    expect(inboxPathForRole('EMPLOYEE')).toBe('/messages');
    expect(inboxPathForRole('HR')).toBe('/hr/messages');
  });
});
