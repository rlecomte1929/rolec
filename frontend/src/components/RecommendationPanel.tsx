import React from 'react';
import { Card, Badge, Button } from './antigravity';
import type { HousingRecommendation, SchoolRecommendation, MoverRecommendation } from '../types';

interface RecommendationPanelProps {
  housing?: HousingRecommendation[];
  schools?: SchoolRecommendation[];
  movers?: MoverRecommendation[];
}

export const RecommendationPanel: React.FC<RecommendationPanelProps> = ({
  housing,
  schools,
  movers,
}) => {
  if (!housing?.length && !schools?.length && !movers?.length) {
    return (
      <Card padding="lg">
        <div className="text-center py-8">
          <p className="text-gray-600">
            Complete more of your profile to see personalized recommendations.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      {/* Housing Recommendations */}
      {housing && housing.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Housing Options</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {housing.slice(0, 6).map((house) => (
              <Card key={house.id} padding="md" className="hover:shadow-lg transition-shadow">
                <div className="space-y-3">
                  <div>
                    <h3 className="font-semibold text-lg text-gray-900">{house.name}</h3>
                    <p className="text-sm text-gray-600">{house.area}</p>
                  </div>
                  
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="neutral" size="sm">{house.bedrooms} beds</Badge>
                    {house.furnished && <Badge variant="info" size="sm">Furnished</Badge>}
                    {house.nearMRT && <Badge variant="success" size="sm">Near MRT</Badge>}
                  </div>
                  
                  <div className="text-sm text-gray-700">
                    SGD {house.estMonthlySGDMin.toLocaleString()} - {house.estMonthlySGDMax.toLocaleString()}/month
                  </div>
                  
                  <p className="text-sm text-gray-600 italic">{house.rationale}</p>
                  
                  <p className="text-sm text-gray-700">{house.notes}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* School Recommendations */}
      {schools && schools.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">School Options</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {schools.slice(0, 6).map((school) => (
              <Card key={school.id} padding="md" className="hover:shadow-lg transition-shadow">
                <div className="space-y-3">
                  <div>
                    <h3 className="font-semibold text-lg text-gray-900">{school.name}</h3>
                    <p className="text-sm text-gray-600">{school.area}</p>
                  </div>
                  
                  <div className="flex flex-wrap gap-2">
                    {school.curriculumTags.map(tag => (
                      <Badge key={tag} variant="info" size="sm">{tag}</Badge>
                    ))}
                    <Badge variant="neutral" size="sm">{school.ageRange}</Badge>
                  </div>
                  
                  <div className="text-sm text-gray-700">
                    SGD {school.estAnnualSGDMin.toLocaleString()} - {school.estAnnualSGDMax.toLocaleString()}/year
                  </div>
                  
                  <p className="text-sm text-gray-600 italic">{school.rationale}</p>
                  
                  <p className="text-sm text-gray-700">{school.notes}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Mover Recommendations */}
      {movers && movers.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Moving Companies</h2>
          <div className="space-y-4">
            {movers.map((mover) => (
              <Card key={mover.id} padding="md">
                <div className="space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-semibold text-lg text-gray-900">{mover.name}</h3>
                      <p className="text-sm text-gray-600 italic">{mover.rationale}</p>
                    </div>
                    <Button size="sm">{mover.nextAction}</Button>
                  </div>
                  
                  <div className="flex flex-wrap gap-2">
                    {mover.serviceTags.map(tag => (
                      <Badge key={tag} variant="success" size="sm">{tag}</Badge>
                    ))}
                  </div>
                  
                  <p className="text-sm text-gray-700">{mover.notes}</p>
                  
                  <div className="bg-gray-50 p-3 rounded text-sm text-gray-800">
                    <strong>RFQ Template:</strong> {mover.rfqTemplate}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
