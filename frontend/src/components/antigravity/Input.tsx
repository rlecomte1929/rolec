import React from 'react';

interface InputProps {
  type?: string;
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  error?: string;
  disabled?: boolean;
  fullWidth?: boolean;
}

export const Input: React.FC<InputProps> = ({
  type = 'text',
  value,
  onChange,
  placeholder,
  label,
  error,
  disabled = false,
  fullWidth = false,
}) => {
  const widthClass = fullWidth ? 'w-full' : '';
  const errorClass = error ? 'border-[#7a2a2a] focus:ring-[#7a2a2a]' : 'border-[#d1d5db] focus:ring-[#0b2b43]';
  
  return (
    <div className={widthClass}>
      {label && (
        <label className="block text-sm font-medium text-[#374151] mb-1">
          {label}
        </label>
      )}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={`px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-all ${widthClass} ${errorClass} ${
          disabled ? 'bg-[#f3f4f6] cursor-not-allowed' : 'bg-white'
        }`}
      />
      {error && <p className="text-sm text-[#7a2a2a] mt-1">{error}</p>}
    </div>
  );
};
