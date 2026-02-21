import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function ChecklistItem({ label, done }) {
  return (
    <div
      className={cn(
        'flex items-center gap-2.5 px-3.5 py-2.5 rounded-[10px] border text-[13px] font-medium transition-all duration-200',
        done
          ? 'border-emerald-200/50 bg-emerald-50 text-emerald-600'
          : 'border-gray-100 bg-white text-gray-500'
      )}
    >
      <div
        className={cn(
          'w-5 h-5 rounded-full border-2 grid place-items-center shrink-0 transition-all duration-200',
          done ? 'bg-emerald-600 border-emerald-600' : 'border-gray-200'
        )}
      >
        <Check
          size={11}
          className={cn('text-white transition-opacity duration-200', done ? 'opacity-100' : 'opacity-0')}
        />
      </div>
      {label}
    </div>
  )
}
