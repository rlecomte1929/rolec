import React, { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { CountryTable } from '../../components/admin/CountryTable';
import { listCountries } from '../../api/admin';
import type { CountryListDTO } from '../../types';
import { useNavigate } from 'react-router-dom';

export const CountriesPage: React.FC = () => {
  const [data, setData] = useState<CountryListDTO | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    listCountries().then(setData);
  }, []);

  return (
    <AppShell title="Country Requirements DB" subtitle="Browse destination requirements and research sources.">
      {!data && <div className="text-sm text-[#6b7280]">Loading countries...</div>}
      {data && <CountryTable data={data} onSelect={(code) => navigate(`/admin/countries/${code}`)} />}
    </AppShell>
  );
};
