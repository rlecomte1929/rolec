import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Card } from '../components/antigravity';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { getCaseDetailsByAssignmentId } from '../api/caseDetails';

const DEFAULT_RESOURCES = {
  emergency: [
    { label: 'Emergency', value: '112 / 911 (check local)' },
    { label: 'Police (non-emergency)', value: 'Local number (check local)' },
    { label: 'Ambulance', value: 'Local number (check local)' },
  ],
  checklist: [
    'Register your address',
    'Set up a local bank account',
    'Get a local SIM',
    'Arrange healthcare registration',
  ],
  registrations: [
    'Resident registration / ID card',
    'Tax registration (if required)',
    'Local driving rules and license exchange',
  ],
  communities: [
    { label: 'Expat communities (generic)', url: 'https://www.internations.org/' },
    { label: 'Meetup expat groups', url: 'https://www.meetup.com/' },
  ],
};

export const Resources: React.FC = () => {
  const { assignmentId } = useEmployeeAssignment();
  const [destination, setDestination] = useState<string | null>(null);

  useEffect(() => {
    if (!assignmentId) return;
    const load = async () => {
      const res = await getCaseDetailsByAssignmentId(assignmentId);
      const dest = res.data?.case?.destCountry || res.data?.case?.destination_country || null;
      setDestination(dest);
    };
    load();
  }, [assignmentId]);

  return (
    <AppShell title="Resources" subtitle="Practical tips for your first weeks in a new location.">
      {destination && (
        <Card padding="lg" className="mb-6">
          <div className="text-sm text-[#6b7280]">Destination</div>
          <div className="text-lg font-semibold text-[#0b2b43]">{destination}</div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card padding="lg">
          <div className="text-lg font-semibold text-[#0b2b43] mb-3">Emergency numbers</div>
          <div className="space-y-2 text-sm text-[#4b5563]">
            {DEFAULT_RESOURCES.emergency.map((item) => (
              <div key={item.label} className="flex items-center justify-between">
                <span>{item.label}</span>
                <span className="font-medium text-[#0b2b43]">{item.value}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card padding="lg">
          <div className="text-lg font-semibold text-[#0b2b43] mb-3">First-week checklist</div>
          <ul className="list-disc list-inside text-sm text-[#4b5563] space-y-1">
            {DEFAULT_RESOURCES.checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>

        <Card padding="lg">
          <div className="text-lg font-semibold text-[#0b2b43] mb-3">Useful registrations</div>
          <ul className="list-disc list-inside text-sm text-[#4b5563] space-y-1">
            {DEFAULT_RESOURCES.registrations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>

        <Card padding="lg">
          <div className="text-lg font-semibold text-[#0b2b43] mb-3">Expat communities</div>
          <div className="space-y-2 text-sm text-[#4b5563]">
            {DEFAULT_RESOURCES.communities.map((item) => (
              <a key={item.url} href={item.url} target="_blank" rel="noreferrer" className="text-[#1d4ed8] hover:underline">
                {item.label}
              </a>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
};
