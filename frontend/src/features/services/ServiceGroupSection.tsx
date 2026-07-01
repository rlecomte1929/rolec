import React from 'react';
import { ServiceCard, type ServicePolicyHint } from './ServiceCard';
import type { ServiceItem, ServiceGroup } from './serviceConfig';
import { GROUP_LABELS } from './serviceConfig';

interface ServiceGroupSectionProps {
  group: ServiceGroup;
  items: ServiceItem[];
  selectedKeys: Set<string>;
  onToggle: (key: string) => void;
  /** Layer-2 policy line per service (backendKey → hint). */
  policyHintForItem?: (item: ServiceItem) => ServicePolicyHint | null | undefined;
  /** Availability per service key for `requiresCuration` tiles (Pets). Missing/true =
   *  available; false = locked until HR curates a vendor for the employee's destination. */
  availabilityByKey?: Record<string, boolean>;
}

export const ServiceGroupSection: React.FC<ServiceGroupSectionProps> = ({
  group,
  items,
  selectedKeys,
  onToggle,
  policyHintForItem,
  availabilityByKey,
}) => {
  const { title, subtitle } = GROUP_LABELS[group];

  return (
    <section className="mb-6">
      <h3 className="text-lg font-semibold text-[#0b2b43] mb-1">{title}</h3>
      <p className="text-sm text-[#6b7280] mb-4">{subtitle}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((item) => {
          const available = availabilityByKey?.[item.key] ?? true;
          const locked = !!item.requiresCuration && !available;
          const interactive = item.enabled && !locked;
          return (
            <ServiceCard
              key={item.key}
              item={item}
              locked={locked}
              selected={selectedKeys.has(item.key) && interactive}
              onToggle={() => interactive && onToggle(item.key)}
              policyHint={policyHintForItem ? policyHintForItem(item) : undefined}
            />
          );
        })}
      </div>
    </section>
  );
};
