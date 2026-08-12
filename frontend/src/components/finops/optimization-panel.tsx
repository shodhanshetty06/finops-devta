"use client";

import { useState } from "react";
import { Leaf, TrendingDown, TrendingUp } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/finops/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCurrency } from "@/contexts/currency-context";
import { apiErrorMessage, optimizationApi } from "@/lib/api-client";
import { REGIONS } from "@/lib/types";
import type {
  CarbonEstimate,
  CloudComparison,
  CommitmentRecommendation,
  CostForecast,
  CustomerRequirement,
  RegionComparison,
  RightsizingReport,
  WorkloadStability,
} from "@/lib/types";

const CLOUDS = ["gcp", "aws", "azure"] as const;

function RightsizingPanel({ requirement }: { requirement: CustomerRequirement }) {
  const { formatMoney } = useCurrency();
  const [avgCpu, setAvgCpu] = useState(35);
  const [peakCpu, setPeakCpu] = useState(60);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<RightsizingReport | null>(null);

  async function analyze() {
    setLoading(true);
    try {
      const result = await optimizationApi.rightsizing(
        requirement,
        { avg_cpu_utilization_percent: avgCpu, peak_cpu_utilization_percent: peakCpu },
        true,
      );
      setReport(result);
    } catch (err) {
      toast.error("Could not run rightsizing analysis", { description: apiErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        This platform has no live monitoring integration - enter observed CPU utilization (e.g. from Cloud
        Monitoring) and the existing RightsizingEngine will compare current vs. resized cost through the real
        pricing pipeline.
      </p>
      <div className="grid grid-cols-2 gap-4 sm:max-w-md">
        <Field label="Avg CPU utilization (%)" htmlFor="avg-cpu">
          <Input id="avg-cpu" type="number" min={0} max={100} value={avgCpu} onChange={(e) => setAvgCpu(Number(e.target.value))} />
        </Field>
        <Field label="Peak CPU utilization (%)" htmlFor="peak-cpu">
          <Input id="peak-cpu" type="number" min={0} max={100} value={peakCpu} onChange={(e) => setPeakCpu(Number(e.target.value))} />
        </Field>
      </div>
      <Button size="sm" className="self-start" onClick={analyze} disabled={loading || !requirement.compute}>
        {loading && <Spinner />}
        Analyze rightsizing
      </Button>
      {!requirement.compute && <p className="text-xs text-muted-foreground">No Compute Engine sizing on this estimate to analyze.</p>}

      {report && (
        report.findings.length === 0 ? (
          <EmptyState icon={TrendingDown} title="No rightsizing findings" description="Nothing to resize for this configuration." />
        ) : (
          <div className="flex flex-col gap-3">
            {report.findings.map((f, i) => (
              <Card key={i}>
                <CardContent className="flex flex-col gap-2 pt-5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-foreground">{f.resource_description}</p>
                    <Badge variant={f.action === "no_change" ? "secondary" : "warning"}>{f.action.replace("_", " ")}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{f.reason}</p>
                  <div className="flex flex-wrap items-center gap-4 text-sm">
                    <span>
                      Current: <span className="font-medium text-foreground">{f.current_machine_type}</span>{" "}
                      ({formatMoney(f.current_monthly_cost, f.currency)}/mo)
                    </span>
                    {f.recommended_machine_type && (
                      <span>
                        Recommended: <span className="font-medium text-foreground">{f.recommended_machine_type}</span>{" "}
                        ({formatMoney(f.recommended_monthly_cost ?? 0, f.currency)}/mo)
                      </span>
                    )}
                    {f.monthly_savings > 0 && (
                      <span className="font-medium text-success-700 dark:text-success-300">
                        Save {formatMoney(f.monthly_savings, f.currency)}/mo
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
            {report.total_monthly_savings > 0 && (
              <p className="text-sm font-semibold text-foreground">
                Total potential savings: {formatMoney(report.total_monthly_savings, report.currency)}/mo
              </p>
            )}
          </div>
        )
      )}
    </div>
  );
}

function CommitmentPanel({ requirement }: { requirement: CustomerRequirement }) {
  const { formatMoney } = useCurrency();
  const [stability, setStability] = useState<WorkloadStability>("steady");
  const [loading, setLoading] = useState(false);
  const [rec, setRec] = useState<CommitmentRecommendation | null>(null);

  async function analyze() {
    setLoading(true);
    try {
      setRec(await optimizationApi.commitmentRecommendation(requirement, stability, true));
    } catch (err) {
      toast.error("Could not run commitment analysis", { description: apiErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end gap-3">
        <Field label="Workload stability" htmlFor="stability">
          <Select id="stability" value={stability} onChange={(e) => setStability(e.target.value as WorkloadStability)}>
            <option value="steady">Steady (runs continuously)</option>
            <option value="variable">Variable (bursty/seasonal)</option>
          </Select>
        </Field>
        <Button size="sm" onClick={analyze} disabled={loading}>
          {loading && <Spinner />}
          Recommend
        </Button>
      </div>

      {rec && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-foreground">{rec.recommendation_reason}</p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Term</TableHead>
                <TableHead>Discount</TableHead>
                <TableHead>Monthly cost</TableHead>
                <TableHead className="text-right">Monthly savings</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rec.options.map((o) => (
                <TableRow key={o.term_years}>
                  <TableCell className={o.term_years === rec.recommended_term_years ? "font-semibold text-foreground" : ""}>
                    {o.term_years}-year {o.term_years === rec.recommended_term_years && <Badge variant="success" className="ml-1">Recommended</Badge>}
                  </TableCell>
                  <TableCell>{o.discount_percent}%</TableCell>
                  <TableCell>{formatMoney(o.monthly_cost_with_commitment, rec.currency)}</TableCell>
                  <TableCell className="text-right">{formatMoney(o.monthly_savings_vs_on_demand, rec.currency)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function ForecastPanel({ requirement }: { requirement: CustomerRequirement }) {
  const { formatMoney } = useCurrency();
  const [growth, setGrowth] = useState(0);
  const [months, setMonths] = useState(12);
  const [loading, setLoading] = useState(false);
  const [forecast, setForecast] = useState<CostForecast | null>(null);

  async function run() {
    setLoading(true);
    try {
      setForecast(await optimizationApi.forecast(requirement, { monthlyGrowthPercent: growth, months, force: true }));
    } catch (err) {
      toast.error("Could not run forecast", { description: apiErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Monthly growth (%)" htmlFor="growth">
          <Input id="growth" type="number" step="0.1" value={growth} onChange={(e) => setGrowth(Number(e.target.value))} className="w-32" />
        </Field>
        <Field label="Months" htmlFor="months">
          <Input id="months" type="number" min={1} max={60} value={months} onChange={(e) => setMonths(Number(e.target.value))} className="w-24" />
        </Field>
        <Button size="sm" onClick={run} disabled={loading}>
          {loading && <Spinner />}
          Project
        </Button>
      </div>

      {forecast && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">{forecast.methodology_note}</p>
          <p className="text-sm text-foreground">
            Starting at {formatMoney(forecast.starting_monthly_cost, forecast.currency)}/mo, projected total over{" "}
            {forecast.months} months: <span className="font-semibold">{formatMoney(forecast.total_projected_cost, forecast.currency)}</span>
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Month</TableHead>
                <TableHead>Projected cost</TableHead>
                <TableHead className="text-right">Cumulative</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {forecast.points.map((p) => (
                <TableRow key={p.month_index}>
                  <TableCell>{p.month_index}</TableCell>
                  <TableCell>{formatMoney(p.projected_monthly_cost, forecast.currency)}</TableCell>
                  <TableCell className="text-right">{formatMoney(p.cumulative_cost, forecast.currency)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function CarbonPanel({ requirement }: { requirement: CustomerRequirement }) {
  const [loading, setLoading] = useState(false);
  const [estimate, setEstimate] = useState<CarbonEstimate | null>(null);

  async function run() {
    setLoading(true);
    try {
      setEstimate(await optimizationApi.carbon(requirement, true));
    } catch (err) {
      toast.error("Could not estimate carbon footprint", { description: apiErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Button size="sm" className="self-start" onClick={run} disabled={loading || !requirement.compute}>
        {loading && <Spinner />}
        Estimate carbon footprint
      </Button>
      {!requirement.compute && <p className="text-xs text-muted-foreground">No Compute Engine sizing on this estimate to estimate.</p>}
      {estimate && (
        <Card>
          <CardContent className="flex flex-col gap-2 pt-5">
            <div className="flex items-center gap-2 text-lg font-semibold text-foreground">
              <Leaf className="size-5 text-success-600" />
              {estimate.estimated_kgco2e_per_month.toLocaleString()} kg CO2e / month
            </div>
            <p className="text-sm text-muted-foreground">
              {estimate.estimated_vcpu_hours_per_month.toLocaleString()} vCPU-hours/month in {estimate.region},{" "}
              {estimate.estimated_kwh_per_month.toLocaleString()} kWh at {estimate.grid_carbon_intensity_gco2e_per_kwh} gCO2e/kWh.
            </p>
            <p className="text-xs text-muted-foreground">{estimate.methodology_note}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ComparePanel({ requirement }: { requirement: CustomerRequirement }) {
  const { formatMoney } = useCurrency();
  const [selectedRegions, setSelectedRegions] = useState<Set<string>>(new Set([requirement.region]));
  const [selectedClouds, setSelectedClouds] = useState<Set<string>>(new Set(CLOUDS));
  const [regionLoading, setRegionLoading] = useState(false);
  const [cloudLoading, setCloudLoading] = useState(false);
  const [regionResult, setRegionResult] = useState<RegionComparison | null>(null);
  const [cloudResult, setCloudResult] = useState<CloudComparison | null>(null);

  function toggle(set: Set<string>, setSet: (s: Set<string>) => void, value: string) {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setSet(next);
  }

  async function runRegions() {
    setRegionLoading(true);
    try {
      setRegionResult(await optimizationApi.compareRegions(requirement, Array.from(selectedRegions)));
    } catch (err) {
      toast.error("Could not compare regions", { description: apiErrorMessage(err) });
    } finally {
      setRegionLoading(false);
    }
  }

  async function runClouds() {
    setCloudLoading(true);
    try {
      setCloudResult(await optimizationApi.compareClouds(requirement, Array.from(selectedClouds)));
    } catch (err) {
      toast.error("Could not compare clouds", { description: apiErrorMessage(err) });
    } finally {
      setCloudLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Label>Compare regions</Label>
        <div className="flex flex-wrap gap-2">
          {REGIONS.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => toggle(selectedRegions, setSelectedRegions, r)}
              className={`rounded-full border px-3 py-1 text-xs ${selectedRegions.has(r) ? "border-primary bg-primary-50 text-primary-800 dark:bg-primary-950" : "border-border text-muted-foreground"}`}
            >
              {r}
            </button>
          ))}
        </div>
        <Button size="sm" className="self-start" onClick={runRegions} disabled={regionLoading || selectedRegions.size < 2}>
          {regionLoading && <Spinner />}
          Compare {selectedRegions.size} region(s)
        </Button>
        {selectedRegions.size < 2 && <p className="text-xs text-muted-foreground">Pick at least 2 regions.</p>}
        {regionResult && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Region</TableHead>
                <TableHead className="text-right">Monthly cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {regionResult.options.map((o) => (
                <TableRow key={o.region}>
                  <TableCell className={o.region === regionResult.cheapest_region ? "font-semibold text-foreground" : ""}>
                    {o.region}
                    {o.region === regionResult.cheapest_region && <Badge variant="success" className="ml-1"><TrendingDown />Cheapest</Badge>}
                  </TableCell>
                  <TableCell className="text-right">{formatMoney(o.total_monthly, o.currency)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <Label>Compare clouds (GCP / AWS / Azure)</Label>
        <div className="flex flex-wrap gap-2">
          {CLOUDS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => toggle(selectedClouds, setSelectedClouds, c)}
              className={`rounded-full border px-3 py-1 text-xs uppercase ${selectedClouds.has(c) ? "border-primary bg-primary-50 text-primary-800 dark:bg-primary-950" : "border-border text-muted-foreground"}`}
            >
              {c}
            </button>
          ))}
        </div>
        <Button size="sm" className="self-start" onClick={runClouds} disabled={cloudLoading || selectedClouds.size < 2}>
          {cloudLoading && <Spinner />}
          Compare {selectedClouds.size} cloud(s)
        </Button>
        {cloudResult && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cloud</TableHead>
                <TableHead>Primary machine type</TableHead>
                <TableHead className="text-right">Monthly cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cloudResult.options.map((o) => (
                <TableRow key={o.cloud_provider}>
                  <TableCell className={`uppercase ${o.cloud_provider === cloudResult.cheapest_cloud ? "font-semibold text-foreground" : ""}`}>
                    {o.cloud_provider}
                    {o.cloud_provider === cloudResult.cheapest_cloud && <Badge variant="success" className="ml-1"><TrendingDown />Cheapest</Badge>}
                  </TableCell>
                  <TableCell>{o.primary_machine_type ?? "—"}</TableCell>
                  <TableCell className="text-right">{formatMoney(o.total_monthly, o.currency)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {cloudResult && (
          <p className="text-sm font-medium text-foreground">
            Max savings vs. most expensive: {formatMoney(cloudResult.max_savings_monthly, cloudResult.currency)}/mo
          </p>
        )}
      </div>
    </div>
  );
}

/** Surfaces the existing backend optimization engines
 * (app/optimization/{rightsizing,commitment,forecast,carbon,comparison,
 * cloud_comparison}_engine.py) for a given estimate's request - none of
 * these are rebuilt here, this is UI over already-working, tested
 * endpoints (see docs/ROADMAP.md Phase 8/9). */
export function OptimizationPanel({ requirement }: { requirement: CustomerRequirement }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <TrendingUp className="size-4" />
          Optimization
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="rightsizing">
          <TabsList>
            <TabsTrigger value="rightsizing">Rightsizing</TabsTrigger>
            <TabsTrigger value="commitment">Commitment</TabsTrigger>
            <TabsTrigger value="forecast">Forecast</TabsTrigger>
            <TabsTrigger value="carbon">Carbon</TabsTrigger>
            <TabsTrigger value="compare">Compare</TabsTrigger>
          </TabsList>
          <TabsContent value="rightsizing">
            <RightsizingPanel requirement={requirement} />
          </TabsContent>
          <TabsContent value="commitment">
            <CommitmentPanel requirement={requirement} />
          </TabsContent>
          <TabsContent value="forecast">
            <ForecastPanel requirement={requirement} />
          </TabsContent>
          <TabsContent value="carbon">
            <CarbonPanel requirement={requirement} />
          </TabsContent>
          <TabsContent value="compare">
            <ComparePanel requirement={requirement} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
