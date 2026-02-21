import { cn, CHANNEL_CONFIG, confidenceBarColor } from '@/lib/utils'

export default function CampaignCard({ campaign, rank, selected, onSelect }) {
  const rankStyles = {
    1: 'bg-brand-50 text-brand',
    2: 'bg-teal-50 text-teal',
    3: 'bg-surface-alt text-gray-500',
  }

  return (
    <div
      onClick={() => onSelect(campaign.id)}
      className={cn(
        'bg-white border-[1.5px] rounded-card overflow-hidden cursor-pointer transition-all duration-200',
        selected
          ? 'border-brand shadow-[0_0_0_3px_rgba(0,102,255,0.1)] shadow-card-md'
          : 'border-gray-200 hover:border-brand/30 hover:shadow-card-md hover:-translate-y-px'
      )}
    >
      {/* Top section */}
      <div className="flex gap-5 p-5 px-6">
        <div className={cn('w-11 h-11 rounded-card grid place-items-center text-base font-extrabold shrink-0', rankStyles[rank] || rankStyles[3])}>
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          {/* Title */}
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-base font-bold text-gray-900">{campaign.title}</span>
            {campaign.recommended && (
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-brand-50 text-brand">
                Recommended
              </span>
            )}
          </div>
          {/* Description */}
          <p className="text-[13px] text-gray-500 leading-relaxed mb-3">{campaign.description}</p>

          {/* Signal tag */}
          <div className="inline-flex items-center gap-1.5 px-2.5 py-[5px] rounded-md bg-surface-alt text-[11px] font-semibold text-gray-500 mb-3">
            <span className={cn('w-1.5 h-1.5 rounded-full', campaign.signal.color === 'blue' ? 'bg-brand' : 'bg-teal')} />
            {campaign.signal.name} — <span className="font-bold text-gray-900">{campaign.signal.probability}% probability</span>
          </div>

          {/* Channels */}
          <div className="flex gap-2 flex-wrap">
            {campaign.channels.map((ch, i) => {
              const config = CHANNEL_CONFIG[ch.type]
              return (
                <div key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-100 bg-white text-xs font-semibold text-gray-500">
                  <span className={cn('w-[22px] h-[22px] rounded-[5px] grid place-items-center text-[11px] font-bold text-white', config?.bg || 'bg-gray-500')}>
                    {config?.abbr || '?'}
                  </span>
                  {config?.label || ch.type} {ch.format}
                  <span className="text-[11px] font-bold text-emerald-600">{ch.fit}%</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="flex items-center gap-2.5 px-6 py-3.5 border-t border-gray-100 bg-surface-alt">
        <span className="text-[11px] font-semibold text-gray-400">Confidence</span>
        <div className="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full progress-animate', confidenceBarColor(campaign.confidence))}
            style={{ width: `${campaign.confidence}%` }}
          />
        </div>
        <span className="text-xs font-bold text-gray-900">{campaign.confidence}%</span>
      </div>
    </div>
  )
}
