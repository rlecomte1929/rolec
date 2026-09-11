import React, { useState } from 'react';
import { Alert, Button, Card, FileInput, Input } from '../../components/antigravity';
import { expenseClaimsAPI } from '../../api/expenseClaims';
import api from '../../api/client';

type Prefill = {
  vendor_name?: string;
  amount?: number;
  currency?: string;
  date?: string;
};

export const ExpenseClaimForm: React.FC<{
  caseId: string;
  benefitKey?: string;
  onSubmitted?: () => void;
}> = ({ caseId, benefitKey = 'installation_allowance', onSubmitted }) => {
  const [vendor, setVendor] = useState('');
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('EUR');
  const [expenseDate, setExpenseDate] = useState('');
  const [ocrId, setOcrId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const applyPrefill = (fields: Prefill, id?: string) => {
    if (fields.vendor_name) setVendor(String(fields.vendor_name));
    if (fields.amount != null) setAmount(String(fields.amount));
    if (fields.currency) setCurrency(String(fields.currency).toUpperCase());
    if (fields.date) setExpenseDate(String(fields.date).slice(0, 10));
    if (id) setOcrId(id);
  };

  const onReceipt = async (file: File | null) => {
    if (!file) return;
    setError(null);
    const body = new FormData();
    body.append('file', file);
    body.append('document_type', 'expense_receipt');
    try {
      const { data } = await api.post<{
        id?: string;
        extracted_fields?: Prefill;
      }>('/api/ocr/process', body);
      applyPrefill(data?.extracted_fields || {}, data?.id);
    } catch {
      setError('Receipt could not be read. Enter the line manually.');
    }
  };

  const submit = async (status: 'draft' | 'submitted') => {
    const amt = Number(amount);
    if (!Number.isFinite(amt) || amt <= 0) {
      setError('Enter a positive amount.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await expenseClaimsAPI.create(caseId, {
        status,
        lines: [
          {
            benefit_key: benefitKey,
            amount: amt,
            currency,
            cap_currency: 'EUR',
            vendor_name: vendor || null,
            expense_date: expenseDate || null,
            receipt_ocr_id: ocrId,
          },
        ],
      });
      onSubmitted?.();
      setVendor('');
      setAmount('');
      setOcrId(null);
    } catch {
      setError('Claim could not be saved.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card padding="lg" className="mb-6">
      <p className="text-sm font-semibold text-navy-900 mb-3">Submit an expense claim</p>
      {error && (
        <Alert variant="error" className="mb-3">
          {error}
        </Alert>
      )}
      <label className="block text-sm text-navy-800 mb-2">
        Receipt
        <FileInput
          className="mt-1 block"
          accept="image/*,.pdf"
          onChange={(e) => onReceipt(e.target.files?.[0] ?? null)}
        />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Vendor" value={vendor} onChange={setVendor} />
        <Input label="Amount" value={amount} onChange={setAmount} />
        <Input label="Currency" value={currency} onChange={setCurrency} />
        <Input label="Date" type="date" value={expenseDate} onChange={setExpenseDate} />
      </div>
      <div className="mt-4 flex gap-2">
        <Button variant="outline" disabled={busy} onClick={() => submit('draft')}>
          Save draft
        </Button>
        <Button disabled={busy} onClick={() => submit('submitted')}>
          Submit for approval
        </Button>
      </div>
    </Card>
  );
};
