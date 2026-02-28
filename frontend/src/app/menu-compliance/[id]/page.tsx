'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, AlertTriangle, CheckCircle2, XCircle, FileText,
  TrendingUp, TrendingDown, Equal, ArrowUpCircle, ArrowDownCircle, MinusCircle
} from 'lucide-react';
import { menuComplianceAPI } from '@/lib/api';
import { format } from 'date-fns';

export default function MenuCheckDetailPage() {
  const router = useRouter();
  const params = useParams();
  const checkId = parseInt(params.id as string);

  const [check, setCheck] = useState<any>(null);
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

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

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  if (!check) {
    return <div className="flex items-center justify-center h-screen">Check not found</div>;
  }

  const groupedResults: Record<string, any[]> = results.reduce((acc: Record<string, any[]>, result: any) => {
    const cat = result.rule_category || 'Other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(result);
    return acc;
  }, {});

  const failures = results.filter((r: any) => !r.passed);
  const passes = results.filter((r: any) => r.passed);

  // Derive summary from results evidence (works even if check.dishes_* not yet populated)
  const aboveResults = results.filter((r: any) => r.evidence?.comparison === 'above');
  const underResults = results.filter((r: any) => r.evidence?.comparison === 'under');
  const evenResults = results.filter((r: any) => r.evidence?.comparison === 'even');

  const dishesAbove = check.dishes_above || aboveResults.length;
  const dishesUnder = check.dishes_under || underResults.length;
  const dishesEven = check.dishes_even || evenResults.length;

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

        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {check.site_name || 'Unknown Site'} - {check.month} {check.year}
            </h2>
            {check.checked_at && (
              <p className="text-gray-500 text-sm mt-1">
                Checked on {format(new Date(check.checked_at), 'MMMM d, yyyy')}
              </p>
            )}
          </div>

          <div className="text-right">
            {check.critical_findings > 0 ? (
              <Badge variant="destructive" className="text-lg px-4 py-2">
                {check.critical_findings} Critical Issues
              </Badge>
            ) : (
              <Badge className="bg-green-100 text-green-800 text-lg px-4 py-2">
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Looking Good
              </Badge>
            )}
          </div>
        </div>

        {/* Quantity Summary — Above / Under / Even */}
        <Card className="mb-6 border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg text-indigo-900 flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Quantity Summary
            </CardTitle>
            <p className="text-sm text-indigo-600">
              Dishes compared to standard requirements
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white rounded-xl p-4 border border-blue-200 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <ArrowUpCircle className="w-8 h-8 text-blue-500" />
                  <span className="text-3xl font-bold text-blue-600">{dishesAbove}</span>
                </div>
                <p className="text-sm font-medium text-blue-700">Above Standard</p>
                <p className="text-xs text-gray-500 mt-0.5">Served more than required</p>
              </div>

              <div className="bg-white rounded-xl p-4 border border-red-200 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <ArrowDownCircle className="w-8 h-8 text-red-500" />
                  <span className="text-3xl font-bold text-red-600">{dishesUnder}</span>
                </div>
                <p className="text-sm font-medium text-red-700">Under Standard</p>
                <p className="text-xs text-gray-500 mt-0.5">Served less than required</p>
              </div>

              <div className="bg-white rounded-xl p-4 border border-green-200 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <MinusCircle className="w-8 h-8 text-green-500" />
                  <span className="text-3xl font-bold text-green-600">{dishesEven}</span>
                </div>
                <p className="text-sm font-medium text-green-700">Meets Standard</p>
                <p className="text-xs text-gray-500 mt-0.5">Exactly as required</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Pass/Fail Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card className="p-6 bg-red-50 border-red-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-red-700 font-medium">Critical</p>
                <p className="text-4xl font-bold text-red-600 mt-1">
                  {check.critical_findings || 0}
                </p>
              </div>
              <XCircle className="w-10 h-10 text-red-500" />
            </div>
          </Card>

          <Card className="p-6 bg-orange-50 border-orange-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-orange-700 font-medium">Warnings</p>
                <p className="text-4xl font-bold text-orange-600 mt-1">
                  {check.warnings || 0}
                </p>
              </div>
              <AlertTriangle className="w-10 h-10 text-orange-500" />
            </div>
          </Card>

          <Card className="p-6 bg-green-50 border-green-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-green-700 font-medium">Passed</p>
                <p className="text-4xl font-bold text-green-600 mt-1">
                  {check.passed_rules || 0}
                </p>
              </div>
              <CheckCircle2 className="w-10 h-10 text-green-500" />
            </div>
          </Card>

          <Card className="p-6 bg-blue-50 border-blue-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-blue-700 font-medium">Total Rules</p>
                <p className="text-4xl font-bold text-blue-600 mt-1">
                  {results.length}
                </p>
              </div>
              <FileText className="w-10 h-10 text-blue-500" />
            </div>
          </Card>
        </div>

        {/* Failures First */}
        {failures.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-red-700">
                <XCircle className="w-5 h-5" />
                Issues Found ({failures.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(groupedResults).map(([category, categoryResults]) => {
                  const categoryFailures = categoryResults.filter((r: any) => !r.passed);
                  if (categoryFailures.length === 0) return null;

                  return (
                    <div key={category}>
                      <h3 className="font-semibold text-gray-900 mb-3">{category}</h3>
                      <div className="space-y-3">
                        {categoryFailures.map((result: any) => (
                          <ResultRow key={result.id} result={result} />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Passed Rules */}
        {passes.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-green-700">
                <CheckCircle2 className="w-5 h-5" />
                Passed Rules ({passes.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(groupedResults).map(([category, categoryResults]) => {
                  const categoryPasses = categoryResults.filter((r: any) => r.passed);
                  if (categoryPasses.length === 0) return null;

                  return (
                    <div key={category}>
                      <h3 className="font-semibold text-gray-900 mb-3">{category}</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {categoryPasses.map((result: any) => (
                          <ResultRow key={result.id} result={result} passed />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
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


function ResultRow({ result, passed }: { result: any; passed?: boolean }) {
  const evidence = result.evidence || {};
  const hasComparison = evidence.expected_count !== undefined && evidence.actual_count !== undefined;
  const comparison = evidence.comparison || 'even';
  const expected = evidence.expected_count ?? null;
  const actual = evidence.actual_count ?? null;
  const deficit = expected !== null && actual !== null ? expected - actual : null;

  if (passed) {
    return (
      <div className="p-3 bg-green-50 rounded-lg border border-green-200">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900">
              {result.rule_name}
            </p>
            {result.rule_category && (
              <p className="text-xs text-gray-600 mt-0.5">
                {result.rule_category}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {hasComparison && (
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <span>Exp: <strong>{expected}</strong></span>
                <span>Act: <strong>{actual}</strong></span>
                <ComparisonBadge comparison={comparison} />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`p-4 rounded-lg border-l-4 ${
        result.severity === 'critical'
          ? 'bg-red-50 border-red-500'
          : 'bg-orange-50 border-orange-500'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-medium text-gray-900">
          {result.rule_name}
        </h4>
        <div className="flex items-center gap-2">
          {hasComparison && <ComparisonBadge comparison={comparison} />}
          <Badge
            variant={result.severity === 'critical' ? 'destructive' : 'secondary'}
            className={result.severity !== 'critical' ? 'bg-orange-100 text-orange-800' : ''}
          >
            {result.severity}
          </Badge>
        </div>
      </div>

      {result.finding_text && (
        <p className="text-sm text-gray-700 mb-2">
          {result.finding_text}
        </p>
      )}

      {/* Expected vs Actual bar */}
      {hasComparison && expected !== null && actual !== null && expected > 0 && (
        <div className="mt-3 p-3 bg-white/60 rounded-lg">
          <div className="flex items-center justify-between text-xs text-gray-600 mb-1.5">
            <span>Expected: <strong className="text-gray-900">{expected}</strong></span>
            <span>Actual: <strong className="text-gray-900">{actual}</strong></span>
            {deficit !== null && deficit !== 0 && (
              <span className={deficit > 0 ? 'text-red-600 font-medium' : 'text-blue-600 font-medium'}>
                {deficit > 0 ? `Missing: ${deficit}` : `Extra: ${Math.abs(deficit)}`}
              </span>
            )}
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div
              className={`h-2.5 rounded-full transition-all ${
                comparison === 'under' ? 'bg-red-500' :
                comparison === 'above' ? 'bg-blue-500' : 'bg-green-500'
              }`}
              style={{ width: `${Math.min((actual / expected) * 100, 100)}%` }}
            />
          </div>
          {comparison === 'above' && (
            <div className="w-full bg-gray-200 rounded-full h-1 mt-0.5">
              <div
                className="h-1 rounded-full bg-blue-300"
                style={{ width: `${Math.min(((actual - expected) / expected) * 100, 100)}%` }}
              />
            </div>
          )}
        </div>
      )}

      {result.reviewed && (
        <div className="mt-2 flex items-center gap-2 text-sm text-gray-600">
          <CheckCircle2 className="w-4 h-4 text-green-600" />
          Reviewed: {result.review_status}
          {result.review_notes && (
            <span className="ml-2">- {result.review_notes}</span>
          )}
        </div>
      )}
    </div>
  );
}
