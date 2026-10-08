import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  elevated?: boolean;
  className?: string;
}

export const Card: React.FC<CardProps> = ({
  children,
  elevated = false,
  className = '',
  ...props
}) => {
  return (
    <div
      className={`rounded-xl border transition-all duration-150 ${
        elevated
          ? 'bg-white dark:bg-slate-900 border-slate-200/90 dark:border-slate-800 shadow-sm hover:shadow-md'
          : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800'
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
