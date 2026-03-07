import React from 'react';
import { ServiceCard } from './ServiceCard';
import type { ServiceItem, ServiceGroup } from './serviceConfig';
import { GROUP_LABELS } from './serviceConfig';

interface ServiceGroupSectionProps {
  group: ServiceGroup;
  items: ServiceItem[];
  selectedKeys: Set<string>;
  onToggle: (key: string) => void;
}

export const ServiceGroupSection: React.FC<ServiceGroupSectionProps> = ({
  group,
  items,
  selectedKeys,
  onToggle,
}) => {
  const { title, subtitle } = GROUP_LABELS[group];

  return (
    <section className="mb-6">
      <h3 className="text-lg font-semibold text-[#0b2b43] mb-1">{title}</h3>
      <p className="text-sm text-[#6b7280] mb-4">{subtitle}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((item) => (
          <ServiceCard
            key={item.key}
            item={item}
            selected={selectedKeys.has(item.key) && item.enabled}
            onToggle={() => item.enabled && onToggle(item.key)}
          />
        ))}
      </div>
    </section>
  );
};
