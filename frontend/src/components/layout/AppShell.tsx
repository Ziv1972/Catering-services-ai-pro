'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { NavHeader } from './NavHeader';

const EXCLUDED_PATHS = ['/login'];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!EXCLUDED_PATHS.includes(pathname)) {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.replace('/login');
        return;
      }
    }
    setChecked(true);
  }, [pathname, router]);

  if (EXCLUDED_PATHS.includes(pathname)) {
    return <>{children}</>;
  }

  if (!checked) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <NavHeader />
      <div className="flex-1">{children}</div>
      <footer className="border-t bg-white py-4 text-center text-xs text-gray-400">
        by Ziv Reshef Simchoni
      </footer>
    </div>
  );
}
