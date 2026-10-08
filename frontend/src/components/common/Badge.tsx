import React from 'react';
import type { ModerationDecision, RiskLevel, VideoStatus } from '../../types/api';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple';
  size?: 'sm' | 'md';
  className?: string;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  icon,
}) => {
  const variantStyles = {
    default: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800',
    warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 border-amber-200 dark:border-amber-800',
    danger: 'bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-400 border-red-200 dark:border-red-800',
    info: 'bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400 border-blue-200 dark:border-blue-800',
    purple: 'bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-400 border-purple-200 dark:border-purple-800',
  };

  const sizeStyles = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
};

export const DecisionBadge: React.FC<{ decision: ModerationDecision; size?: 'sm' | 'md' }> = ({
  decision,
  size = 'md',
}) => {
  switch (decision) {
    case 'APPROVED':
      return (
        <Badge variant="success" size={size}>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          APPROVED (SAFE)
        </Badge>
      );
    case 'REVIEW_REQUIRED':
      return (
        <Badge variant="warning" size={size}>
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
          REVIEW REQUIRED
        </Badge>
      );
    case 'REJECTED':
      return (
        <Badge variant="danger" size={size}>
          <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
          VIOLATION DETECTED
        </Badge>
      );
    default:
      return <Badge size={size}>{decision}</Badge>;
  }
};

export const RiskBadge: React.FC<{ riskLevel: RiskLevel; size?: 'sm' | 'md' }> = ({
  riskLevel,
  size = 'md',
}) => {
  switch (riskLevel) {
    case 'LOW':
      return <Badge variant="success" size={size}>LOW RISK</Badge>;
    case 'MEDIUM':
      return <Badge variant="warning" size={size}>MEDIUM RISK</Badge>;
    case 'HIGH':
      return <Badge variant="danger" size={size}>HIGH RISK</Badge>;
    case 'CRITICAL':
      return (
        <Badge variant="danger" size={size} className="bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-200 font-bold border-red-300">
          CRITICAL RISK
        </Badge>
      );
    default:
      return <Badge size={size}>{riskLevel}</Badge>;
  }
};

export const StatusBadge: React.FC<{ status: VideoStatus; size?: 'sm' | 'md' }> = ({
  status,
  size = 'md',
}) => {
  switch (status) {
    case 'COMPLETED':
      return (
        <Badge variant="success" size={size}>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          COMPLETED
        </Badge>
      );
    case 'PROCESSING':
    case 'ANALYZING':
      return (
        <Badge variant="info" size={size}>
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
          {status}
        </Badge>
      );
    case 'QUEUED':
    case 'UPLOADED':
      return (
        <Badge variant="default" size={size}>
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
          {status}
        </Badge>
      );
    case 'FAILED':
      return (
        <Badge variant="danger" size={size}>
          <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
          FAILED
        </Badge>
      );
    default:
      return <Badge size={size}>{status}</Badge>;
  }
};
