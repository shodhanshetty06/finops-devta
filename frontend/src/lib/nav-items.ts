// Single source of truth for the app's primary navigation - consumed by
// both the persistent sidebar (components/app-sidebar.tsx) and the
// command-menu search palette (components/command-menu.tsx) so the two
// never drift out of sync.
import {
  BarChart3,
  FilePlus2,
  FileSpreadsheet,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  Network,
  PlusCircle,
  Scale,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Tags,
  Upload,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
  /** Only rendered/searchable for this role; omit to show for everyone. */
  requiresRole?: "admin";
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, description: "Spend overview & quick actions" },
      { label: "Projects", href: "/projects", icon: FileSpreadsheet, description: "Manage projects & versioned estimates" },
    ],
  },
  {
    label: "Build",
    items: [
      { label: "New Estimate", href: "/estimate/new", icon: PlusCircle, description: "Price a configuration in seconds" },
      { label: "Existing Estimate", href: "/estimate/existing", icon: FilePlus2, description: "Add or update services on a saved estimate" },
      { label: "Upload Excel", href: "/upload", icon: Upload, description: "Import a filled questionnaire workbook" },
      { label: "Questionnaire", href: "/questionnaire", icon: FileText, description: "Guided step-by-step requirement intake" },
    ],
  },
  {
    label: "Analyze",
    items: [
      { label: "Pricing", href: "/pricing", icon: Tags, description: "Browse the GCP catalog & compare regions" },
      { label: "Resource Optimization", href: "/optimization", icon: Scale, description: "Compare a saved resource's config against an upgrade/downgrade" },
      { label: "Validation", href: "/validation", icon: ShieldCheck, description: "Rule engine reference & live validator" },
      { label: "Normalization", href: "/normalization", icon: SlidersHorizontal, description: "How ambiguous input gets resolved" },
      { label: "Architecture", href: "/architecture", icon: Network, description: "Recommended service architecture" },
    ],
  },
  {
    label: "Reporting",
    items: [
      { label: "Reports", href: "/reports", icon: BarChart3, description: "Generate Excel & PDF proposals" },
      { label: "History", href: "/history", icon: History, description: "Every estimate version across projects" },
    ],
  },
  {
    label: "Workspace",
    items: [
      { label: "Settings", href: "/settings", icon: Settings, description: "Profile, appearance & preferences" },
      { label: "Admin", href: "/admin", icon: Gauge, description: "Organization-wide cost overview", requiresRole: "admin" },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);
