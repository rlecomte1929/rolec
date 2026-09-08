import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CountryTable } from '../../components/admin/CountryTable';
import { listCountries } from '../../api/admin';
import type { CountryListDTO } from '../../types';
import { AdminLayout } from './AdminLayout';

export const CountriesPage: React.FC = () => {
  const [data, setData] = useState<CountryListDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    void listCountries()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load countries'));
  }, []);

  return (
    <AdminLayout title="Country requirements" subtitle="Browse destination requirements and research sources.">
      <div data-testid="countries-page">
        {error && <div className="text-sm text-[#b91c1c] mb-4">{error}</div>}
        {!data && !error && <div className="text-sm text-slate-500">Loading countries…</div>}
        {data && (
          <CountryTable
            data={data}
            onSelect={(code) => navigate(`/admin/countries/${encodeURIComponent(code)}`)}
          />
        )}
      </div>
    </AdminLayout>
  );
};
