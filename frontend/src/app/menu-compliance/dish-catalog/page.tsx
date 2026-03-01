'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, Search, Check, X, Loader2,
  UtensilsCrossed, BookOpen, ShieldCheck, AlertTriangle
} from 'lucide-react';
import { dishCatalogAPI, menuComplianceAPI } from '@/lib/api';

interface DishEntry {
  id: number;
  dish_name: string;
  category: string | null;
  compliance_rule_id: number | null;
  rule_name: string | null;
  approved: boolean;
  source_check_id: number | null;
}

interface CategoryOption {
  value: string;
  label: string;
}

interface RuleOption {
  id: number;
  name: string;
  rule_type: string;
  category: string;
}

export default function DishCatalogPage() {
  const router = useRouter();
  const [dishes, setDishes] = useState<DishEntry[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [rules, setRules] = useState<RuleOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [filterSearch, setFilterSearch] = useState<string>('');
  const [showUnassigned, setShowUnassigned] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [stats, setStats] = useState<any>(null);

  const loadData = useCallback(async () => {
    try {
      const [dishData, catData, ruleData, statsData] = await Promise.all([
        dishCatalogAPI.list({
          category: filterCategory || undefined,
          unassigned: showUnassigned || undefined,
          search: filterSearch || undefined,
        }),
        dishCatalogAPI.getCategories(),
        menuComplianceAPI.listRules(),
        dishCatalogAPI.getStats().catch(() => null),
      ]);
      setDishes(dishData);
      setCategories(catData);
      setRules(ruleData);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  }, [filterCategory, filterSearch, showUnassigned]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCategoryChange = async (dishId: number, category: string) => {
    setSavingId(dishId);
    try {
      await dishCatalogAPI.update(dishId, {
        category: category || undefined,
      });
      setDishes(prev =>
        prev.map(d => d.id === dishId ? { ...d, category: category || null } : d)
      );
    } catch (error) {
      console.error('Failed to update category:', error);
    } finally {
      setSavingId(null);
    }
  };

  const handleRuleChange = async (dishId: number, ruleId: string) => {
    setSavingId(dishId);
    try {
      const numericId = ruleId ? parseInt(ruleId) : null;
      await dishCatalogAPI.update(dishId, {
        compliance_rule_id: numericId,
      });
      const matchedRule = rules.find(r => r.id === numericId);
      setDishes(prev =>
        prev.map(d => d.id === dishId ? {
          ...d,
          compliance_rule_id: numericId,
          rule_name: matchedRule?.name || null,
        } : d)
      );
    } catch (error) {
      console.error('Failed to update rule:', error);
    } finally {
      setSavingId(null);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  const categorized = dishes.filter(d => d.category).length;
  const linked = dishes.filter(d => d.compliance_rule_id).length;
  const approvedCount = dishes.filter(d => d.approved).length;

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Button
          variant="ghost"
          onClick={() => router.push('/menu-compliance')}
          className="mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Menu Compliance
        </Button>

        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <UtensilsCrossed className="w-6 h-6" />
              Dish Catalog
            </h2>
            <p className="text-gray-500 text-sm mt-1">
              Dishes are automatically extracted when running compliance checks.
              {dishes.length > 0 && (
                <> {dishes.length} dishes &middot; {approvedCount} approved &middot; {categorized} categorized &middot; {linked} linked to rules</>
              )}
            </p>
          </div>
        </div>

        {/* Filters */}
        {dishes.length > 0 && (
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search dishes..."
                value={filterSearch}
                onChange={(e) => setFilterSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                dir="rtl"
              />
            </div>

            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">All Categories</option>
              {categories.map(cat => (
                <option key={cat.value} value={cat.value}>{cat.label}</option>
              ))}
            </select>

            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={showUnassigned}
                onChange={(e) => setShowUnassigned(e.target.checked)}
                className="rounded"
              />
              Unassigned only
            </label>

            {(filterCategory || filterSearch || showUnassigned) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFilterCategory('');
                  setFilterSearch('');
                  setShowUnassigned(false);
                }}
              >
                <X className="w-3 h-3 mr-1" /> Clear
              </Button>
            )}
          </div>
        )}

        {/* Dish Table */}
        {dishes.length > 0 ? (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider w-[35%]">
                        Dish Name
                      </th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider w-[8%]">
                        Status
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider w-[22%]">
                        Category
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider w-[30%]">
                        Rule to Match
                      </th>
                      <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wider w-[5%]">
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {dishes.map((dish, idx) => (
                      <tr
                        key={dish.id}
                        className={`border-b hover:bg-gray-50 transition-colors ${
                          !dish.category && !dish.compliance_rule_id
                            ? 'bg-yellow-50/50'
                            : ''
                        } ${idx % 2 === 0 ? '' : 'bg-gray-50/30'}`}
                      >
                        <td className="px-4 py-2.5 text-right">
                          <span className="font-medium text-gray-900 text-sm" dir="rtl">
                            {dish.dish_name}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {dish.approved ? (
                            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 text-xs">
                              <ShieldCheck className="w-3 h-3 mr-1" />
                              Approved
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200 text-xs">
                              <AlertTriangle className="w-3 h-3 mr-1" />
                              Review
                            </Badge>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          <select
                            value={dish.category || ''}
                            onChange={(e) => handleCategoryChange(dish.id, e.target.value)}
                            disabled={savingId === dish.id}
                            className={`w-full border rounded px-2 py-1.5 text-sm bg-white ${
                              !dish.category
                                ? 'border-yellow-300 text-gray-400'
                                : 'border-gray-200 text-gray-800'
                            } ${savingId === dish.id ? 'opacity-50' : ''}`}
                          >
                            <option value="">-- Select --</option>
                            {categories.map(cat => (
                              <option key={cat.value} value={cat.value}>
                                {cat.label}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-2.5">
                          <select
                            value={dish.compliance_rule_id?.toString() || ''}
                            onChange={(e) => handleRuleChange(dish.id, e.target.value)}
                            disabled={savingId === dish.id}
                            className={`w-full border rounded px-2 py-1.5 text-sm bg-white ${
                              !dish.compliance_rule_id
                                ? 'border-yellow-300 text-gray-400'
                                : 'border-gray-200 text-gray-800'
                            } ${savingId === dish.id ? 'opacity-50' : ''}`}
                          >
                            <option value="">-- Select Rule --</option>
                            {rules.map((rule: RuleOption) => (
                              <option key={rule.id} value={rule.id.toString()}>
                                {rule.name}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          {savingId === dish.id ? (
                            <Loader2 className="w-4 h-4 animate-spin text-gray-400 mx-auto" />
                          ) : dish.category && dish.compliance_rule_id ? (
                            <Check className="w-4 h-4 text-green-500 mx-auto" />
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="p-12 text-center">
            <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-lg mb-2">No dishes in catalog yet</p>
            <p className="text-gray-400 text-sm">
              Dishes are automatically extracted when you upload and run a compliance check.
            </p>
          </Card>
        )}

        {/* Stats */}
        {stats && stats.total > 0 && (
          <div className="mt-6 grid grid-cols-5 gap-4">
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
              <p className="text-xs text-gray-500">Total Dishes</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold text-green-600">{approvedCount}</p>
              <p className="text-xs text-gray-500">Approved</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold text-green-600">{stats.categorized}</p>
              <p className="text-xs text-gray-500">Categorized</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold text-yellow-600">{stats.uncategorized}</p>
              <p className="text-xs text-gray-500">Uncategorized</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{stats.rule_linked}</p>
              <p className="text-xs text-gray-500">Linked to Rules</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
