"use client";

import { useQuery } from "@tanstack/react-query";
import { Cpu, Database, HardDrive, MapPin, Server, Zap } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/finops/stat-card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { catalogApi } from "@/lib/api-client";
import { CLOUD_SQL_ENGINES, MACHINE_FAMILIES } from "@/lib/types";

const ALL_FAMILIES = "__all__";
const ALL_ENGINES = "__all__";

export default function PricingPage() {
  const [family, setFamily] = useState<string>(ALL_FAMILIES);
  const [engine, setEngine] = useState<string>(ALL_ENGINES);

  const machineTypesQuery = useQuery({
    queryKey: ["catalog-machine-types", family],
    queryFn: () => catalogApi.machineTypes(family === ALL_FAMILIES ? undefined : family),
  });
  const diskTypesQuery = useQuery({ queryKey: ["catalog-disk-types"], queryFn: catalogApi.diskTypes });
  const gpuTypesQuery = useQuery({ queryKey: ["catalog-gpu-types"], queryFn: catalogApi.gpuTypes });
  const regionsQuery = useQuery({ queryKey: ["catalog-regions"], queryFn: catalogApi.regions });
  const cloudSqlQuery = useQuery({
    queryKey: ["catalog-cloud-sql", engine],
    queryFn: () => catalogApi.cloudSqlTiers(engine === ALL_ENGINES ? undefined : engine),
  });
  const gkeQuery = useQuery({ queryKey: ["catalog-gke"], queryFn: catalogApi.gkeConfig });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Pricing catalog</h1>
        <p className="text-sm text-muted-foreground">
          Every configuration this platform currently considers supported - the same catalog the validation and pricing engines use.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Machine types" value={String(machineTypesQuery.data?.length ?? "—")} icon={Cpu} />
        <StatCard label="Disk types" value={String(diskTypesQuery.data?.length ?? "—")} icon={HardDrive} />
        <StatCard label="GPU types" value={String(gpuTypesQuery.data?.length ?? "—")} icon={Zap} />
        <StatCard label="Regions" value={String(regionsQuery.data?.length ?? "—")} icon={MapPin} />
        <StatCard label="Cloud SQL tiers" value={String(cloudSqlQuery.data?.length ?? "—")} icon={Database} />
        <StatCard label="GKE node ceiling" value={gkeQuery.data ? gkeQuery.data.max_node_count.toLocaleString() : "—"} icon={Server} />
      </div>

      <Card>
        <CardContent className="pt-5">
          <Tabs defaultValue="machine">
            <TabsList>
              <TabsTrigger value="machine">Machine types</TabsTrigger>
              <TabsTrigger value="disk">Disk types</TabsTrigger>
              <TabsTrigger value="gpu">GPUs</TabsTrigger>
              <TabsTrigger value="region">Regions</TabsTrigger>
              <TabsTrigger value="sql">Cloud SQL</TabsTrigger>
              <TabsTrigger value="gke">GKE</TabsTrigger>
            </TabsList>

            <TabsContent value="machine">
              <div className="mb-3 flex justify-end">
                <Select value={family} onChange={(e) => setFamily(e.target.value)} className="w-44">
                  <option value={ALL_FAMILIES}>All families</option>
                  {MACHINE_FAMILIES.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </Select>
              </div>
              {machineTypesQuery.isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Family</TableHead>
                      <TableHead>vCPU</TableHead>
                      <TableHead>RAM (GB)</TableHead>
                      <TableHead>GPU support</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {machineTypesQuery.data?.map((m) => (
                      <TableRow key={m.name}>
                        <TableCell className="font-mono text-[13px] text-foreground">{m.name}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{m.family}</Badge>
                        </TableCell>
                        <TableCell>{m.vcpu}</TableCell>
                        <TableCell>{m.ram_gb}</TableCell>
                        <TableCell>{m.supports_gpu ? <Badge variant="success">Yes</Badge> : <span className="text-muted-foreground">No</span>}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </TabsContent>

            <TabsContent value="disk">
              {diskTypesQuery.isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Min size</TableHead>
                      <TableHead>Max size</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {diskTypesQuery.data?.map((d) => (
                      <TableRow key={d.name}>
                        <TableCell className="font-mono text-[13px] text-foreground">{d.name}</TableCell>
                        <TableCell className="text-muted-foreground">{d.description}</TableCell>
                        <TableCell>{d.min_size_gb.toLocaleString()} GB</TableCell>
                        <TableCell>{d.max_size_gb.toLocaleString()} GB</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </TabsContent>

            <TabsContent value="gpu">
              {gpuTypesQuery.isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Max per instance</TableHead>
                      <TableHead>Compatible families</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {gpuTypesQuery.data?.map((g) => (
                      <TableRow key={g.name}>
                        <TableCell className="font-mono text-[13px] text-foreground">{g.name}</TableCell>
                        <TableCell>{g.max_per_instance}</TableCell>
                        <TableCell className="flex flex-wrap gap-1">
                          {g.compatible_families.map((f) => (
                            <Badge key={f} variant="secondary">
                              {f}
                            </Badge>
                          ))}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </TabsContent>

            <TabsContent value="region">
              {regionsQuery.isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Display name</TableHead>
                      <TableHead>Multi-zone</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {regionsQuery.data?.map((r) => (
                      <TableRow key={r.code}>
                        <TableCell className="font-mono text-[13px] text-foreground">{r.code}</TableCell>
                        <TableCell className="text-muted-foreground">{r.display_name}</TableCell>
                        <TableCell>{r.multi_zone ? <Badge variant="success">Yes</Badge> : <span className="text-muted-foreground">No</span>}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </TabsContent>

            <TabsContent value="sql">
              <div className="mb-3 flex justify-end">
                <Select value={engine} onChange={(e) => setEngine(e.target.value)} className="w-44">
                  <option value={ALL_ENGINES}>All engines</option>
                  {CLOUD_SQL_ENGINES.map((e) => (
                    <option key={e} value={e}>
                      {e}
                    </option>
                  ))}
                </Select>
              </div>
              {cloudSqlQuery.isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tier</TableHead>
                      <TableHead>vCPU</TableHead>
                      <TableHead>RAM (GB)</TableHead>
                      <TableHead>Engines</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cloudSqlQuery.data?.map((t) => (
                      <TableRow key={t.tier}>
                        <TableCell className="font-mono text-[13px] text-foreground">{t.tier}</TableCell>
                        <TableCell>{t.vcpu}</TableCell>
                        <TableCell>{t.ram_gb}</TableCell>
                        <TableCell className="flex flex-wrap gap-1">
                          {t.engines.map((e) => (
                            <Badge key={e} variant="secondary">
                              {e}
                            </Badge>
                          ))}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </TabsContent>

            <TabsContent value="gke">
              {gkeQuery.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                gkeQuery.data && (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <Card>
                      <CardHeader className="pb-1">
                        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Cluster modes</CardTitle>
                      </CardHeader>
                      <CardContent className="flex gap-2">
                        {gkeQuery.data.autopilot_available && <Badge variant="success">Autopilot</Badge>}
                        {gkeQuery.data.standard_available && <Badge variant="success">Standard</Badge>}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-1">
                        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Node count range</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-lg font-semibold text-foreground">
                          {gkeQuery.data.min_node_count.toLocaleString()} – {gkeQuery.data.max_node_count.toLocaleString()}
                        </p>
                        <CardDescription>nodes per cluster</CardDescription>
                      </CardContent>
                    </Card>
                  </div>
                )
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
