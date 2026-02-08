import React from 'react';
import type { SourceRecordDTO } from '../../types';

interface CitationsProps {
  sources: SourceRecordDTO[];
}

export const Citations: React.FC<CitationsProps> = ({ sources }) => {
  if (!sources.length) return null;
  return (
    <div className="mt-2 space-y-1 text-xs text-[#6b7280]">
      {sources.slice(0, 3).map((source) => (
        <a
          key={source.id}
          href={source.url}
          target="_blank"
          rel="noreferrer"
          title={`Retrieved ${new Date(source.retrievedAt).toLocaleDateString('en-US')}`}
          className="block text-[#0b2b43] hover:underline"
        >
          {source.publisherDomain}
        </a>
      ))}
    </div>
  );
};
