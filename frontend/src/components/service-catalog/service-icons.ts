// Explicit icon-name -> lucide-react component lookup, keyed by the plain
// kebab-case strings the backend catalog uses (GCPServiceDefinition.icon).
// Deliberately a fixed map (not a dynamic `lucide[name]` lookup) so an
// unrecognized/typo'd icon string from the backend degrades to a generic
// fallback glyph instead of crashing the page.
import {
  Activity,
  BarChart3,
  Box,
  Brain,
  Container,
  Cpu,
  Database,
  GitBranch,
  HardDrive,
  Network,
  Plug,
  Send,
  Shield,
  Zap,
  type LucideIcon,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  cpu: Cpu,
  container: Container,
  zap: Zap,
  "hard-drive": HardDrive,
  database: Database,
  network: Network,
  send: Send,
  "bar-chart": BarChart3,
  brain: Brain,
  shield: Shield,
  activity: Activity,
  "git-branch": GitBranch,
  plug: Plug,
  box: Box,
};

export function serviceIcon(name: string): LucideIcon {
  return ICONS[name] ?? Box;
}
