'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, AlertTriangle, CheckCircle2, XCircle, FileText
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
              {check.site?.name || 'Unknown Site'} - {check.month} {check.year}
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
        {/* Summary Stats */}
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
                          <div
                            key={result.id}
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
                              <Badge
                                variant={result.severity === 'critical' ? 'destructive' : 'secondary'}
                                className={result.severity !== 'critical' ? 'bg-orange-100 text-orange-800' : ''}
                              >
                                {result.severity}
                              </Badge>
                            </div>

                            {result.finding_text && (
                              <p className="text-sm text-gray-700 mb-2">
                                {result.finding_text}
                              </p>
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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {passes.map((result: any) => (
                  <div
                    key={result.id}
                    className="p-3 bg-green-50 rounded-lg border border-green-200"
                  >
                    <p className="text-sm font-medium text-gray-900">
                      {result.rule_name}
                    </p>
                    {result.rule_category && (
                      <p className="text-xs text-gray-600 mt-1">
                        {result.rule_category}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

