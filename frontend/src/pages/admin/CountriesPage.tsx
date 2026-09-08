import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert } from '../../components/antigravity/Alert';
import { Button } from '../../components/antigravity/Button';
import { Skeleton } from '../../components/antigravity/Skeleton';
import { CountryTable } from '../../components/admin/CountryTable';
import { listCountries } from '../../api/admin';
import type { CountryListDTO } from '../../types';

export const CountriesPage: React.FC = () => {
  const [data, setData] = useState<CountryListDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(null);
    void listCountries()
      .then(setData)
      .catch((e) => {
        setData(null);
        setError(e instanceof Error ? e.message : 'Could not load country catalogs');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell
      title="Country requirements"
      subtitle="Scan destination coverage, then open a country to review and publish requirements."
    >
      <div data-testid="countries-page" className="space-y-4">
        {error && (
          <Alert variant="error" title="Could not load catalogs">
            <div className="mt-2 flex items-center gap-3">
              <span>{error}</span>
              <Button variant="outline" size="sm" onClick={load}>Try again</Button>
            </div>
          </Alert>
        )}
        {loading && (
          <div role="status" aria-live="polite" className="space-y-3">
            <span className="sr-only">Loading countries</span>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Skeleton variant="rect" height="h-16" />
              <Skeleton variant="rect" height="h-16" />
              <Skeleton variant="rect" height="h-16" />
              <Skeleton variant="rect" height="h-16" />
            </div>
            <Skeleton variant="rect" height="h-64" />
          </div>
        )}
        {data && !loading && (
          <CountryTable data={data} onSelect={(code) => navigate(`/admin/countries/${code}`)} />
        )}
      </div>
    </AppShell>
  );
};
