import React from 'react';
import { Card } from './Card';

interface StatCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  description?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  icon,
  description,
  variant = 'default',
}) => {
  const iconBgStyles = {
    default: 'bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-400',
    success: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400',
    warning: 'bg-amber-50 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400',
    danger: 'bg-red-50 text-red-600 dark:bg-red-950/60 dark:text-red-400',
  };

  return (
    <Card elevated className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
        <div className={`p-2.5 rounded-lg ${iconBgStyles[variant]}`}>
          {icon}
        </div>
      </div>
      <div className="mt-3">
        <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          {value}
        </p>
        {description && (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{description}</p>
        )}
      </div>
    </Card>
  );
};
