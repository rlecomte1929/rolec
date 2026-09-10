import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getDataSheet,
  patchDataSheetField,
  type DataSheet,
  type DataSheetQuery,
} from '../../api/datasheet';

/**
 * Data hook for the Document Data Sheet.
 *
 * Loads GET /api/cases/{caseId}/datasheet and exposes a `saveField` mutation that
 * PATCHes one field and writes the recomposed sheet straight back into the query
 * cache (no refetch round-trip). Normalised to `{ data, loading, error, refetch }`
 * to match the house hook shape (useCompaniesV2).
 */
export function useDataSheet(
  caseId: string | undefined,
  opts: DataSheetQuery = {},
): {
  data: DataSheet | undefined;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  saveField: (fieldId: string, value: string) => Promise<void>;
  saving: boolean;
  saveError: string | null;
} {
  const qc = useQueryClient();
  const audience = opts.audience ?? 'employee';
  const lang = opts.lang ?? 'en';
  const mode = opts.mode ?? 'full';
  const queryKey = ['datasheet', caseId, audience, lang, mode];

  const query = useQuery({
    queryKey,
    queryFn: () => getDataSheet(caseId as string, { audience, lang, mode }),
    enabled: !!caseId,
  });

  const mutation = useMutation({
    mutationFn: ({ fieldId, value }: { fieldId: string; value: string }) =>
      patchDataSheetField(caseId as string, fieldId, value, { audience, lang, mode }),
    onSuccess: (fresh) => {
      qc.setQueryData(queryKey, fresh);
    },
  });

  return {
    data: query.data,
    loading: query.isLoading,
    error: query.isError
      ? query.error instanceof Error
        ? query.error.message
        : 'Failed to load the data sheet'
      : null,
    refetch: async () => {
      await query.refetch();
    },
    saveField: async (fieldId, value) => {
      await mutation.mutateAsync({ fieldId, value });
    },
    saving: mutation.isPending,
    saveError: mutation.isError
      ? mutation.error instanceof Error
        ? mutation.error.message
        : 'Could not save your change'
      : null,
  };
}
