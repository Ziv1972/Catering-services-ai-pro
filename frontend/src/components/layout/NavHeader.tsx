'use client';

import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import {
  CalendarDays, AlertTriangle, FileText, TrendingUp,
  Utensils, Home, ClipboardCheck, Building2,
  FolderKanban, ListTodo, Wrench, DollarSign, Tag,
  Menu, X
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
  { href: '/price-lists', label: 'Price Lists', icon: Tag },
  { href: '/proformas', label: 'Proformas', icon: FileText },
  { href: '/complaints', label: 'Complaints', icon: AlertTriangle },
  { href: '/analytics', label: 'Analytics', icon: TrendingUp },
];

export function NavHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navigate = (href: string) => {
    router.push(href);
    setMobileOpen(false);
  };

  return (
    <header className="bg-white border-b sticky top-0 z-20">
      <div className="max-w-7xl mx-auto px-4">
        {/* Top row */}
        <div className="flex justify-between items-center py-3">
          <div
            className="flex items-center gap-3 cursor-pointer"
            onClick={() => navigate('/')}
          >
            <Utensils className="w-6 h-6 text-blue-600" />
            <div>
              <h1 className="text-lg font-bold text-gray-900">
                <span className="hidden sm:inline">Catering Services AI Pro</span>
                <span className="sm:hidden">Catering AI</span>
              </h1>
              <p className="text-xs text-gray-500 hidden sm:block">HP Israel - Ziv Reshef</p>
            </div>
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-gray-100"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Desktop navigation tabs */}
        <nav className="hidden md:flex -mb-px pb-px">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href ||
              (item.href !== '/' && pathname.startsWith(item.href));

            return (
              <button
                key={item.href}
                onClick={() => navigate(item.href)}
                className={cn(
                  'flex items-center gap-1 px-2 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap',
                  isActive
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Mobile navigation drawer */}
      {mobileOpen && (
        <div className="md:hidden border-t bg-white">
          <nav className="grid grid-cols-3 gap-1 p-3">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href ||
                (item.href !== '/' && pathname.startsWith(item.href));

              return (
                <button
                  key={item.href}
                  onClick={() => navigate(item.href)}
                  className={cn(
                    'flex flex-col items-center gap-1 p-3 rounded-lg text-xs font-medium transition-colors',
                    isActive
                      ? 'bg-blue-50 text-blue-600'
                      : 'text-gray-600 hover:bg-gray-50'
                  )}
                >
                  <Icon className="w-5 h-5" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>
      )}
    </header>
  );
}
