import React from 'react';
import { CheckCircle, LayoutTemplate, Search, Upload } from 'lucide-react';
import { PolicyImportStepItem } from './PolicyImportStepItem';

const iconClass = 'h-4 w-4';

export const PolicyImportSteps: React.FC = () => (
  <div
    className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 lg:gap-0 lg:divide-x lg:divide-[#e8ecf1]"
    role="list"
    aria-label="Policy import steps"
  >
    <div className="lg:pr-4" role="listitem">
      <PolicyImportStepItem
        icon={<Upload className={iconClass} strokeWidth={1.75} />}
        title="Upload policy"
        description="Add your internal relocation or mobility policy document."
      />
    </div>
    <div className="lg:px-4" role="listitem">
      <PolicyImportStepItem
        icon={<Search className={iconClass} strokeWidth={1.75} />}
        title="Extract data"
        description="Relevant benefits, caps, and conditions are identified."
      />
    </div>
    <div className="lg:px-4" role="listitem">
      <PolicyImportStepItem
        icon={<LayoutTemplate className={iconClass} strokeWidth={1.75} />}
        title="Update draft"
        description="A structured draft is created or enriched with the extracted information."
      />
    </div>
    <div className="lg:pl-4" role="listitem">
      <PolicyImportStepItem
        icon={<CheckCircle className={iconClass} strokeWidth={1.75} />}
        title="Review and publish"
        description="Complete missing items, confirm the policy baseline, and publish the approved version."
      />
    </div>
  </div>
);
