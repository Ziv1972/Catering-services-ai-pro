'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, CheckCircle2, XCircle, FileText,
  TrendingUp, TrendingDown, Equal, ArrowUpCircle, ArrowDownCircle, MinusCircle,
  RefreshCw, Calendar
} from 'lucide-react';
import { menuComplianceAPI } from '@/lib/api';
import { format } from 'date-fns';

type FilterType = 'all' | 'above' | 'under' | 'even';

export default function MenuCheckDetailPage() {
  const router = useRouter();
  const params = useParams();
  const checkId = parseInt(params.id as string);

  const [check, setCheck] = useState<any>(null);
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [filter, setFilter] = useState<FilterType>('all');

  useEffect(() => {
    loadCheckData();
  }, [checkId]);

  const loadCheckData = async () => {
    try {
      const [checkData, resultsData] = await Promise.all([
        menuComplianceAPI.getCheck(checkId),
        menuComplianceAPI.getResults(checkId),
      ]);
      setCheck(checkData);
      setResults(resultsData);
    } catch (error) {
      console.error('Failed to load check:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = async () => {
    setRerunning(true);
    try {
      await menuComplianceAPI.rerunCheck(checkId);
      await loadCheckData();
    } catch (error) {
      console.error('Failed to re-run check:', error);
    } finally {
      setRerunning(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  if (!check) {
    return <div className="flex items-center justify-center h-screen">Check not found</div>;
  }

  // Derive counts from results evidence
  const aboveResults = results.filter((r: any) => r.evidence?.comparison === 'above');
  const underResults = results.filter((r: any) => r.evidence?.comparison === 'under');
  const evenResults = results.filter((r: any) => r.evidence?.comparison === 'even');

  const dishesAbove = check.dishes_above || aboveResults.length;
  const dishesUnder = check.dishes_under || underResults.length;
  const dishesEven = check.dishes_even || evenResults.length;

  // Apply filter
  const filteredResults = filter === 'all'
    ? results
    : results.filter((r: any) => (r.evidence?.comparison || 'even') === filter);

  // Group filtered results by category
  const groupedFiltered: Record<string, any[]> = filteredResults.reduce(
    (acc: Record<string, any[]>, result: any) => {
      const cat = result.rule_category || 'Other';
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(result);
      return acc;
    }, {}
  );

  const toggleFilter = (f: FilterType) => {
    setFilter(filter === f ? 'all' : f);
  };

  return (
    <div>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Button
          variant="ghost"
          onClick={() => router.push('/menu-compliance')}
          className="mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Checks
        </Button>

        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {check.site_name || 'Unknown Site'} - {check.month} {check.year}
            </h2>
            {check.checked_at && (
              <p className="text-gray-500 text-sm mt-1">
                Checked on {format(new Date(check.checked_at), 'MMMM d, yyyy')}
                {' · '}{results.length} rules checked
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={handleRerun}
              disabled={rerunning}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${rerunning ? 'animate-spin' : ''}`} />
              {rerunning ? 'Re-running...' : 'Re-run Check'}
            </Button>
            {check.critical_findings > 0 ? (
              <Badge variant="destructive" className="text-lg px-4 py-2">
                {check.critical_findings} Critical
              </Badge>
            ) : (
              <Badge className="bg-green-100 text-green-800 text-lg px-4 py-2">
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Looking Good
              </Badge>
            )}
          </div>
        </div>

        {/* Summary Cards — clickable filters */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <button
            onClick={() => toggleFilter('above')}
            className={`rounded-xl p-5 border-2 text-left transition-all ${
              filter === 'above'
                ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200'
                : 'border-blue-200 bg-white hover:border-blue-300 hover:shadow-sm'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <ArrowUpCircle className="w-8 h-8 text-blue-500" />
              <span className="text-3xl font-bold text-blue-600">{dishesAbove}</span>
            </div>
            <p className="text-sm font-medium text-blue-700">Above Standard</p>
            <p className="text-xs text-gray-500 mt-0.5">Served more than required</p>
          </button>

          <button
            onClick={() => toggleFilter('under')}
            className={`rounded-xl p-5 border-2 text-left transition-all ${
              filter === 'under'
                ? 'border-red-500 bg-red-50 ring-2 ring-red-200'
                : 'border-red-200 bg-white hover:border-red-300 hover:shadow-sm'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <ArrowDownCircle className="w-8 h-8 text-red-500" />
              <span className="text-3xl font-bold text-red-600">{dishesUnder}</span>
            </div>
            <p className="text-sm font-medium text-red-700">Under Standard</p>
            <p className="text-xs text-gray-500 mt-0.5">Served less than required</p>
          </button>

          <button
            onClick={() => toggleFilter('even')}
            className={`rounded-xl p-5 border-2 text-left transition-all ${
              filter === 'even'
                ? 'border-green-500 bg-green-50 ring-2 ring-green-200'
                : 'border-green-200 bg-white hover:border-green-300 hover:shadow-sm'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <MinusCircle className="w-8 h-8 text-green-500" />
              <span className="text-3xl font-bold text-green-600">{dishesEven}</span>
            </div>
            <p className="text-sm font-medium text-green-700">Meets Standard</p>
            <p className="text-xs text-gray-500 mt-0.5">Exactly as required</p>
          </button>
        </div>

        {/* Active filter indicator */}
        {filter !== 'all' && (
          <div className="flex items-center gap-2 mb-4">
            <span className="text-sm text-gray-500">Showing:</span>
            <Badge
              className={`cursor-pointer ${
                filter === 'above' ? 'bg-blue-100 text-blue-700' :
                filter === 'under' ? 'bg-red-100 text-red-700' :
                'bg-green-100 text-green-700'
              }`}
              onClick={() => setFilter('all')}
            >
              {filter === 'above' ? 'Above Standard' :
               filter === 'under' ? 'Under Standard' : 'Meets Standard'}
              {' '}({filteredResults.length})
              <XCircle className="w-3 h-3 ml-1 inline" />
            </Badge>
          </div>
        )}

        {/* Results */}
        {filteredResults.length === 0 ? (
          <Card className="p-12 text-center">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No rules match this filter.</p>
          </Card>
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedFiltered).map(([category, categoryResults]) => (
              <Card key={category}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base text-gray-700">{category}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {categoryResults.map((result: any) => (
                      <ResultRow key={result.id} result={result} />
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}


function ComparisonBadge({ comparison }: { comparison: string }) {
  if (comparison === 'above') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
        <TrendingUp className="w-3 h-3" /> Above
      </span>
    );
  }
  if (comparison === 'under') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
        <TrendingDown className="w-3 h-3" /> Under
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
      <Equal className="w-3 h-3" /> Even
    </span>
  );
}


function formatDate(dateStr: string) {
  try {
    return format(new Date(dateStr), 'MMM d');
  } catch {
    return dateStr;
  }
}


function ResultRow({ result }: { result: any }) {
  const evidence = result.evidence || {};
  const hasComparison = evidence.expected_count !== undefined && evidence.actual_count !== undefined;
  const comparison = evidence.comparison || 'even';
  const expected = evidence.expected_count ?? null;
  const actual = evidence.actual_count ?? null;
  const deficit = expected !== null && actual !== null ? expected - actual : null;
  const foundDays: string[] = evidence.found_on_days || [];
  const missingDays: string[] = evidence.missing_on_days || [];

  const borderColor = comparison === 'under' ? 'border-red-400'
    : comparison === 'above' ? 'border-blue-400'
    : 'border-green-400';

  const bgColor = comparison === 'under' ? 'bg-red-50'
    : comparison === 'above' ? 'bg-blue-50'
    : 'bg-green-50';

  return (
    <div className={`p-4 rounded-lg border-l-4 ${borderColor} ${bgColor}`}>
      {/* Header row */}
      <div className="flex items-start justify-between mb-1">
        <h4 className="font-medium text-gray-900">{result.rule_name}</h4>
        <ComparisonBadge comparison={comparison} />
      </div>

      {/* Expected vs Actual inline */}
      {hasComparison && expected !== null && actual !== null && (
        <div className="flex items-center gap-4 text-sm text-gray-600 mb-2">
          <span>Expected: <strong className="text-gray-900">{expected}</strong></span>
          <span>Actual: <strong className="text-gray-900">{actual}</strong></span>
          {deficit !== null && deficit !== 0 && (
            <span className={deficit > 0 ? 'text-red-600 font-semibold' : 'text-blue-600 font-semibold'}>
              {deficit > 0 ? `Missing: ${deficit}` : `Extra: ${Math.abs(deficit)}`}
            </span>
          )}
        </div>
      )}

      {/* Progress bar */}
      {hasComparison && expected !== null && actual !== null && expected > 0 && (
        <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
          <div
            className={`h-2 rounded-full transition-all ${
              comparison === 'under' ? 'bg-red-500' :
              comparison === 'above' ? 'bg-blue-500' : 'bg-green-500'
            }`}
            style={{ width: `${Math.min((actual / expected) * 100, 100)}%` }}
          />
        </div>
      )}

      {/* Menu locations for UNDER standard items */}
      {comparison === 'under' && foundDays.length > 0 && (
        <div className="mt-2 p-2.5 bg-white/70 rounded-md">
          <div className="flex items-center gap-1.5 text-xs font-medium text-gray-700 mb-1.5">
            <Calendar className="w-3.5 h-3.5" />
            Found on {foundDays.length} day{foundDays.length !== 1 ? 's' : ''}:
          </div>
          <div className="flex flex-wrap gap-1.5">
            {foundDays.map((d: string) => (
              <span key={d} className="px-2 py-0.5 text-xs bg-green-100 text-green-800 rounded-md font-medium">
                {formatDate(d)}
              </span>
            ))}
          </div>
        </div>
      )}

      {comparison === 'under' && foundDays.length === 0 && actual === 0 && (
        <div className="mt-2 p-2.5 bg-white/70 rounded-md">
          <p className="text-xs text-red-600 font-medium">
            ⚠ Not found anywhere in the menu
          </p>
        </div>
      )}

      {comparison === 'under' && missingDays.length > 0 && missingDays.length <= 10 && (
        <div className="mt-2 p-2.5 bg-white/70 rounded-md">
          <div className="flex items-center gap-1.5 text-xs font-medium text-gray-700 mb-1.5">
            <Calendar className="w-3.5 h-3.5 text-red-500" />
            Missing on {missingDays.length} day{missingDays.length !== 1 ? 's' : ''}:
          </div>
          <div className="flex flex-wrap gap-1.5">
            {missingDays.map((d: string) => (
              <span key={d} className="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-md font-medium">
                {formatDate(d)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Above standard — show where found */}
      {comparison === 'above' && foundDays.length > 0 && (
        <div className="mt-2 p-2.5 bg-white/70 rounded-md">
          <div className="flex items-center gap-1.5 text-xs font-medium text-gray-700 mb-1.5">
            <Calendar className="w-3.5 h-3.5" />
            Found on {foundDays.length} day{foundDays.length !== 1 ? 's' : ''}:
          </div>
          <div className="flex flex-wrap gap-1.5">
            {foundDays.map((d: string) => (
              <span key={d} className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-md font-medium">
                {formatDate(d)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
