import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react'

export const TOOL_MODES = [
  {
    mode: 'allow' as const,
    label: 'Auto-execute',
    icon: ShieldCheck,
    color: 'var(--green, #34c759)',
    bg: 'rgba(52, 199, 89, 0.10)',
  },
  {
    mode: 'require_approval' as const,
    label: 'Ask for approval',
    icon: ShieldAlert,
    color: 'var(--amber, #f5a623)',
    bg: 'rgba(245, 166, 35, 0.10)',
  },
  {
    mode: 'deny' as const,
    label: 'Always deny',
    icon: ShieldX,
    color: 'var(--red, #ff3b30)',
    bg: 'rgba(255, 59, 48, 0.10)',
  },
] as const
