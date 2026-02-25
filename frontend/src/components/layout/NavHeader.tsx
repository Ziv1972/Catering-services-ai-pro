'use client';

import { useRouter, usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import {
  CalendarDays, AlertTriangle, FileText, TrendingUp,
  Utensils, Home, ClipboardCheck, Shield, Building2,
  FolderKanban, ListTodo, Wrench, DollarSign
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: Home },
  { href: '/budget', label: 'Budget', icon: DollarSign },
  { href: '/projects', label: 'Projects', icon: FolderKanban },
  { href: '/maintenance', label: 'Maintenance', icon: Wrench },
  { href: '/meetings', label: 'Meetings', icon: CalendarDays },
  { href: '/todos', label: 'Tasks', icon: ListTodo },
  { href: '/menu-compliance', label: 'Menu Checks', icon: ClipboardCheck },
  { href: '/suppliers', label: 'Suppliers', icon: Building2 },
  { href: '/proformas', label: 'Proformas', icon: FileText },
  { href: '/complaints', label: 'Complaints', icon: AlertTriangle },
  { href: '/analytics', label: 'Analytics', icon: TrendingUp },
];

export function NavHeader() {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <header className="bg-white border-b sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4">
        {/* Top row */}
        <div className="flex justify-between items-center py-3">
          <div
            className="flex items-center gap-3 cursor-pointer"
            onClick={() => router.push('/')}
          >
            <Utensils className="w-6 h-6 text-blue-600" />
            <div>
              <h1 className="text-lg font-bold text-gray-900">
                Catering Services AI Pro
              </h1>
              <p className="text-xs text-gray-500">HP Israel - Ziv Reshef</p>
            </div>
          </div>
        </div>

        {/* Navigation tabs */}
        <nav className="flex gap-1 -mb-px overflow-x-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href ||
              (item.href !== '/' && pathname.startsWith(item.href));

            return (
              <button
                key={item.href}
                onClick={() => router.push(item.href)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                  isActive
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                )}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
