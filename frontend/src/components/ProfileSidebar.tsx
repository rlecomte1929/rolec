import React from 'react';
import { Card } from './antigravity';
import type { RelocationProfile } from '../types';

interface ProfileSidebarProps {
  profile: RelocationProfile;
}

export const ProfileSidebar: React.FC<ProfileSidebarProps> = ({ profile }) => {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Not set';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="space-y-4">
      <Card padding="md">
        <h3 className="font-semibold text-gray-900 mb-3">Your Profile</h3>
        
        <div className="space-y-3 text-sm">
          {/* Primary Applicant */}
          {profile.primaryApplicant?.fullName && (
            <div>
              <div className="text-xs text-gray-500 uppercase">Primary Applicant</div>
              <div className="font-medium">{profile.primaryApplicant.fullName}</div>
              {profile.primaryApplicant.nationality && (
                <div className="text-gray-600">{profile.primaryApplicant.nationality}</div>
              )}
            </div>
          )}

          {/* Spouse */}
          {profile.spouse?.fullName && (
            <div>
              <div className="text-xs text-gray-500 uppercase">Spouse</div>
              <div className="font-medium">{profile.spouse.fullName}</div>
            </div>
          )}

          {/* Children */}
          {profile.dependents?.some(d => d.firstName) && (
            <div>
              <div className="text-xs text-gray-500 uppercase">Children</div>
              {profile.dependents.map((child, idx) => (
                child.firstName && (
                  <div key={idx} className="font-medium">{child.firstName}</div>
                )
              ))}
            </div>
          )}

          <hr className="my-3 border-gray-200" />

          {/* Key Dates */}
          <div>
            <div className="text-xs text-gray-500 uppercase">Key Dates</div>
            
            {profile.movePlan?.targetArrivalDate && (
              <div className="flex justify-between items-center mt-1">
                <span className="text-gray-600">Arrival:</span>
                <span className="font-medium">{formatDate(profile.movePlan.targetArrivalDate)}</span>
              </div>
            )}
            
            {profile.primaryApplicant?.assignment?.startDate && (
              <div className="flex justify-between items-center mt-1">
                <span className="text-gray-600">Work starts:</span>
                <span className="font-medium">{formatDate(profile.primaryApplicant.assignment.startDate)}</span>
              </div>
            )}
            
            {profile.movePlan?.schooling?.schoolingStartDate && (
              <div className="flex justify-between items-center mt-1">
                <span className="text-gray-600">School starts:</span>
                <span className="font-medium">{formatDate(profile.movePlan.schooling.schoolingStartDate)}</span>
              </div>
            )}
          </div>

          <hr className="my-3 border-gray-200" />

          {/* Preferences */}
          {profile.movePlan?.housing?.preferredAreas && profile.movePlan.housing.preferredAreas.length > 0 && (
            <div>
              <div className="text-xs text-gray-500 uppercase">Preferred Areas</div>
              <div className="text-gray-700">
                {profile.movePlan.housing.preferredAreas.slice(0, 3).join(', ')}
              </div>
            </div>
          )}

          {profile.movePlan?.schooling?.curriculumPreference && (
            <div>
              <div className="text-xs text-gray-500 uppercase">Curriculum</div>
              <div className="text-gray-700">{profile.movePlan.schooling.curriculumPreference}</div>
            </div>
          )}
        </div>
      </Card>

      {/* Auto-save notice */}
      <div className="text-xs text-gray-500 text-center px-4">
        Your progress is saved automatically. You can finish later.
      </div>
    </div>
  );
};
