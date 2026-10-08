import React from 'react';
import { Link } from 'react-router-dom';
import { PageContainer } from '../components/layout/PageContainer';
import { Button } from '../components/common/Button';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <PageContainer>
      <div className="py-20 text-center space-y-4 max-w-md mx-auto">
        <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-500 flex items-center justify-center mx-auto">
          <ShieldAlert className="w-8 h-8 text-amber-500" />
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 dark:text-slate-100">
          Page Not Found
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          The requested page or video workspace does not exist in SafeScreen.
        </p>
        <div className="pt-2">
          <Link to="/dashboard">
            <Button variant="primary" icon={<ArrowLeft className="w-4 h-4" />}>
              Return to Dashboard
            </Button>
          </Link>
        </div>
      </div>
    </PageContainer>
  );
};
