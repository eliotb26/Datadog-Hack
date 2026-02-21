import { cn, CHANNEL_CONFIG } from '@/lib/utils'

export default function ChannelBadge({ type, className }) {
  const config = CHANNEL_CONFIG[type]
  if (!config) return null

  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-semibold', className)}>
      <span className={cn('w-5 h-5 rounded grid place-items-center text-[10px] font-bold text-white', config.bg)}>
        {config.abbr}
      </span>
      {config.label}
    </span>
  )
}
